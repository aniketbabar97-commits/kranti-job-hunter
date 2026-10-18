"""Track company replies in Kranti's Gmail (read-only): interview invitations, rejections, other replies.

Matches each recent inbox mail against the companies she applied to (application kits, email ledger, APPLIED.md)
by sender domain or company name, classifies it by keywords, and stores a short record in data/responses.json
(date, company, category, subject — no mail bodies). The digest shows new replies; the weekly summary shows rates.
"""
import email
import json
import logging
import re
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from . import applied, outreach

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "responses.json"
log = logging.getLogger(__name__)

INTERVIEW = re.compile(r"vorstellungsgespräch|kennenlern|einladung|interview|termin(vorschlag|e)?\b|gespräch vereinbaren|"
                       r"telefonat|video ?call|teams-|zoom|calendly|next steps?|nächste[nr]? schritt|availability|"
                       r"verfügbarkeit|schedule a (call|chat)|meet you", re.I)
REJECT = re.compile(r"leider|absage|nicht berücksichtig|nicht weiter berücksichtig|anderen? (kandidat|bewerber)|"
                    r"entschieden,? (uns )?für|unfortunately|regret|not (to )?(move|proceed)|other candidates?|"
                    r"decided to (pursue|move forward with)|position has been filled|stelle (ist )?bereits besetzt", re.I)
RECEIPT = re.compile(r"eingangsbestätigung|eingang ihrer bewerbung|bewerbung erhalten|received your application|"
                     r"thank you for (your )?appl|vielen dank für ihre bewerbung|application (has been )?received", re.I)
SKIP_FROM = re.compile(r"linkedin\.com|indeed\.|xing\.com|stepstone|glassdoor|noreply@github|google\.com|"
                       r"arbeitsagentur|newsletter|marketing", re.I)
LEGAL = re.compile(r"\b(gmbh|ag|se|kg|co|mbh|ltd|inc|llc|group|gruppe|deutschland|germany|holding|& co)\b", re.I)


def load():
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}


def _companies():
    """{search key: company name} for everything she applied to or has a kit for."""
    names = set()
    for f in (ROOT / "applications").glob("*.json"):
        try:
            names.add(json.loads(f.read_text(encoding="utf-8"))["job"]["company"])
        except Exception:
            pass
    domains = {}
    for v in outreach.load().values():
        names.add(v["company"])
        domains[v["to"].split("@")[-1].lower()] = v["company"]
    for _, line in applied.load()["entries"]:
        m = re.search(r"\(([^,)]+)", line)
        if m:
            names.add(m.group(1))
    keys = {}
    for n in names:
        core = re.sub(r"[^a-z0-9äöüß ]", " ", LEGAL.sub(" ", n.lower())).split()
        if core and len(core[0]) >= 4:
            keys[core[0]] = n
    return keys, domains


def _text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    return (msg.get_payload(decode=True) or b"").decode(msg.get_content_charset() or "utf-8", "ignore")


def classify(subject, body):
    text = f"{subject}\n{body[:3000]}"
    if INTERVIEW.search(text) and not REJECT.search(text):
        return "interview"
    if REJECT.search(text):
        return "rejection"
    if RECEIPT.search(text):
        return "received"
    return "other"


def scan(days=60):
    """Read new company replies from Gmail into data/responses.json. Returns the new records."""
    user, pw = outreach.credentials()
    if not user or not outreach.login_ok():
        return []
    keys, domains = _companies()
    if not keys and not domains:
        return []
    known = load()
    new = []
    try:
        imap = outreach._imap(user, pw)
        box = outreach._special_folder(imap, "\\All") or "[Gmail]/All Mail"
        imap.select(f'"{box}"', readonly=True)
        since = (date.today() - timedelta(days=days)).strftime("%Y/%m/%d")
        typ, data = imap.search(None, "X-GM-RAW", f'"after:{since} -in:sent -in:drafts -category:promotions"')
        for num in (data[0].split() if typ == "OK" and data and data[0] else [])[-400:]:
            typ, hdr = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID FROM SUBJECT DATE)])")
            h = email.message_from_bytes(hdr[0][1])
            mid = h.get("Message-ID", "").strip()
            if not mid or mid in known:
                continue
            sender = parseaddr(h.get("From", ""))[1].lower()
            if not sender or SKIP_FROM.search(sender) or sender == user.lower():
                continue
            subject = str(make_header(decode_header(h.get("Subject", ""))))
            domain = sender.split("@")[-1]
            company = domains.get(domain) or next((n for k, n in keys.items() if k in domain), None)
            if not company:
                company = next((n for k, n in keys.items() if re.search(rf"\b{re.escape(k)}\b", subject.lower())), None)
            if not company:
                continue
            typ, full = imap.fetch(num, "(BODY.PEEK[])")
            body = _text(email.message_from_bytes(full[0][1]))
            try:
                when = parsedate_to_datetime(h.get("Date")).date().isoformat()
            except Exception:
                when = date.today().isoformat()
            rec = {"date": when, "company": company, "category": classify(subject, body), "subject": subject[:140]}
            known[mid] = rec
            new.append(rec)
        imap.logout()
    except Exception as ex:
        log.warning("inbox scan failed: %s", ex)
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(known, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    log.info("inbox: %d new company replies", len(new))
    try:  # receipt mails prove pending helper submissions; older ones without mail go to data/check.json
        from . import submissions
        submissions.reconcile([r for r in known.values() if r.get("category") == "received"])
    except Exception as ex:
        log.warning("submission reconcile failed: %s", ex)
    return new


ICON = {"interview": "🎉 Interview invitation", "rejection": "✖ Rejection", "received": "📨 Confirmation of receipt",
        "other": "💬 Reply"}


def digest_block(new):
    """New replies since the last run, interviews first."""
    import html
    if not new:
        return ""
    order = {"interview": 0, "other": 1, "rejection": 2, "received": 3}
    rows = "".join(f"<li><b>{ICON[r['category']]}</b> — {html.escape(r['company'])}: {html.escape(r['subject'])}</li>"
                   for r in sorted(new, key=lambda r: order[r["category"]]))
    return ("<div style='border:2px solid #8250df;border-radius:8px;padding:10px 14px;margin:14px 0'>"
            "<div style='font-weight:bold;margin-bottom:6px'>📬 Replies in Kranti's inbox</div>"
            f"<ul style='margin:4px 0;font-size:14px'>{rows}</ul></div>")


def weekly_stats():
    """Totals and rates for the weekly summary: what works, where rejections come from."""
    recs = list(load().values())
    if not recs:
        return ""
    count = {c: sum(r["category"] == c for r in recs) for c in ICON}
    decided = count["interview"] + count["rejection"]
    rate = f"{100 * count['interview'] // decided}%" if decided else "–"
    recent = sorted((r for r in recs if r["category"] in ("interview", "rejection")), key=lambda r: r["date"])[-8:]
    return ("<h3>📬 Replies so far</h3>"
            f"<p>🎉 Interviews: <b>{count['interview']}</b> · ✖ Rejections: {count['rejection']} · "
            f"💬 Other: {count['other']} · 📨 Receipts: {count['received']} · Interview rate of decided: <b>{rate}</b></p>"
            "<ul>" + "".join(f"<li>{r['date']} — {ICON[r['category']]} — {r['company']}</li>" for r in recent) + "</ul>")
