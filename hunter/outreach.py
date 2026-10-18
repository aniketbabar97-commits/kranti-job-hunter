"""Email applications from Kranti's own Gmail.

For strong jobs whose posting names an application email address, an application email (short cover note +
tailored CV + cover letter PDFs) is prepared in her Gmail account:
  mode "draft" (default): saved to her Gmail Drafts. She reads it, then presses Send herself.
  mode "send": sent directly (switch only once the drafts have earned her trust).

Ledger data/applications.json remembers every company we wrote to, so a company is never contacted twice.
Each run also checks her Sent folder (draft was sent -> logged in APPLIED.md) and her inbox for replies.
"""
import imaplib
import json
import logging
import os
import re
import smtplib
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, formatdate
from pathlib import Path

from . import applied, kit
from .documents import contact_info

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "applications.json"
log = logging.getLogger(__name__)

HOST = "imap.gmail.com"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
# Addresses in postings that are not for applications.
BAD_LOCAL = re.compile(r"^(no-?reply|do-?not-?reply|datenschutz|privacy|dsb|dpo|data-?protection|abuse|webmaster|"
                       r"newsletter|presse|press|marketing|sales|vertrieb|support|service|billing|rechnung|invoice|"
                       r"buchhaltung|info-?datenschutz)\b", re.I)
BAD_DOMAIN = re.compile(r"(arbeitsagentur\.de|example\.(com|org|de)|sentry|wixpress|linkedin\.com|indeed\.com|"
                        r"\.(png|jpe?g|gif|svg|webp)$)", re.I)
FREEMAIL = re.compile(r"^(gmail|googlemail|outlook|hotmail|live|yahoo|gmx|web|t-online|icloud|aol|freenet|posteo)\.", re.I)
GENERIC = re.compile(r"^(info|kontakt|contact|office|mail|hallo|hello|hi|team|welcome|zentrale)$", re.I)
GOOD_LOCAL = re.compile(r"(bewerb|career|karriere|jobs?|recruit|talent|hr|personal|people|apply|application)", re.I)


def _settings(cfg):
    a = (cfg or {}).get("applications", {})
    return {"mode": a.get("mode", "draft"), "max_per_day": int(a.get("max_per_day", 8)),
            "min_score": int(a.get("min_score", 80))}


def credentials():
    user = os.getenv("CANDIDATE_EMAIL", "").strip()
    pw = os.getenv("KRANTI_GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    return (user, pw) if user and pw else (None, None)


def load():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}


def save(ledger):
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False, sort_keys=True))


def pick_email(job):
    """Best application address named in the posting, or None."""
    found = list(dict.fromkeys(EMAIL_RE.findall(f"{job.get('contact', '')} {job.get('description', '')}")))
    ok = [e.strip(".").lower() for e in found
          if not BAD_LOCAL.match(e.split("@")[0]) and not BAD_DOMAIN.search(e.split("@")[1])]
    if not ok:
        return None
    good = [e for e in ok if GOOD_LOCAL.search(e.split("@")[0])]
    person = [e for e in ok if not GENERIC.match(e.split("@")[0])]  # a named recruiter beats info@
    return (good or person or ok)[0]


GENDER = re.compile(r"\s*[(\[](?:[mwfdx*]\s*/\s*)+[mwfdx*]\s*[)\]]|\s*\((?:all genders?|alle geschlechter|gn\*?)\)", re.I)


def clean_title(title):
    """'SAP CX Consultant (m/w/d)' -> 'SAP CX Consultant' (gender tags read oddly in a subject line)."""
    title = GENDER.sub("", title or "")
    title = re.sub(r"\s*[|–-]\s*[^|–-]*\b(remote|hybrid|vollzeit|teilzeit|full[- ]?time|homeoffice)\b.*$", "", title, flags=re.I)
    return re.sub(r"\s{2,}", " ", title).strip(" -–|")


def backfill(cfg, days=21):
    """One-off: email applications for strong jobs already in the record (found before this feature existed)."""
    import csv
    from . import sources
    master_cv = (ROOT / "cv.md").read_text()
    data = applied.load()
    since = (date.today() - timedelta(days=days)).isoformat()
    jobs, urls = [], set()
    for r in csv.DictReader(open(ROOT / "data" / "jobs_log.csv")):
        if r["url"] in urls:
            continue
        urls.add(r["url"])
        if r["source"] != "Arbeitsagentur" or r["found"] < since or int(r["score"] or 0) < _settings(cfg)["min_score"]:
            continue
        job = {**r, "score": int(r["score"]), "remote": r["remote"] == "True", "contact": "", "description": "",
               "salary": ""}
        try:
            sources.arbeitsagentur_details(job)  # 404 / empty -> posting closed
        except Exception as ex:
            log.info("skip %s: %s", r["title"], ex)
            continue
        if not job["description"] or not pick_email(job):
            continue
        job["applied"] = applied.status(job, data)
        jobs.append(job)
    log.info("backfill: %d strong open jobs with an application email", len(jobs))
    kit.make_kits(jobs, master_cv)
    return prepare(jobs, cfg), jobs


def _company_key(job):
    return applied._company(job.get("company")) or job.get("company", "").lower()


def _first_sentence(text):
    m = re.match(r"(.+?[.!?])(\s|$)", (text or "").strip(), re.S)
    return (m.group(1) if m else (text or "")).strip()


SIGNATURE = {
    "de": "Mit freundlichen Grüßen\nKranti Chavan\n\n{phone} · {email}\nlinkedin.com/in/kranti-chavan-84a155191\nKarlsruhe",
    "en": "Kind regards,\nKranti Chavan\n\n{phone} · {email}\nlinkedin.com/in/kranti-chavan-84a155191\nKarlsruhe, Germany",
}


def compose_body(job, letter, lang):
    """Short, fixed-structure cover note. Facts come only from the master CV / validated letter."""
    c = contact_info()
    hook = _first_sentence(letter.get("hook", ""))
    if lang == "de":
        lines = [letter["salutation"], "",
                 f"anbei sende ich Ihnen meine Bewerbung als {clean_title(job['title'])}. {hook}".strip(), "",
                 "Ich bringe über fünf Jahre Erfahrung mit SAP Commerce Cloud (Hybris), Java und Spring bei Rockwell "
                 "Automation und Shell mit und bin SAP Certified Commerce Cloud Developer. Meinen Lebenslauf und mein "
                 "Anschreiben finden Sie im Anhang.", "",
                 "Ich lebe in Karlsruhe und habe eine gültige Arbeitserlaubnis für Deutschland. Aktuell befinde ich mich "
                 "in der Kündigungsfrist, mein letzter Arbeitstag ist der 15.12.2026. Über eine Einladung zu einem "
                 "persönlichen Gespräch freue ich mich sehr.", ""]
    else:
        lines = [letter["salutation"], "",
                 f"Please find attached my application for the {clean_title(job['title'])} position. {hook}".strip(), "",
                 "I bring 5+ years of hands-on experience with SAP Commerce Cloud (Hybris), Java and Spring at Rockwell "
                 "Automation and Shell, and I am an SAP Certified Commerce Cloud Developer. My CV and cover letter are "
                 "attached.", "",
                 "I live in Karlsruhe and hold a valid German residence and work permit. I am serving my notice period; "
                 "my last working day is 15 December 2026. I would welcome the opportunity to discuss the role with you.", ""]
    return "\n".join(lines + [SIGNATURE[lang].format(**c)]) + "\n"


def build_message(job, to, lang, letter, files, sender):
    msg = EmailMessage()
    msg["From"] = formataddr(("Kranti Chavan", sender))
    msg["To"] = to
    msg["Subject"] = (f"Bewerbung als {clean_title(job['title'])} – Kranti Chavan" if lang == "de"
                      else f"Application: {clean_title(job['title'])} – Kranti Chavan")
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[1])
    msg.set_content(compose_body(job, letter, lang))
    names = ({"cv": "Kranti_Chavan_Lebenslauf.pdf", "cl": "Kranti_Chavan_Anschreiben.pdf"} if lang == "de"
             else {"cv": "Kranti_Chavan_CV.pdf", "cl": "Kranti_Chavan_Cover_Letter.pdf"})
    for kind, path in files:
        msg.add_attachment(Path(path).read_bytes(), maintype="application", subtype="pdf", filename=names[kind])
    return msg


def _files(job, lang):
    """(kind, path) for the CV and the letter in the posting's language; None unless all are real PDFs."""
    pdfs = [a for a in job.get("attachments", []) if a.endswith(".pdf")]
    cv = next((a for a in pdfs if a.endswith("_CV.pdf")), None)
    cl = next((a for a in pdfs if a.endswith(f"_Cover_Letter_{lang.upper()}.pdf")), None)
    return [("cv", cv), ("cl", cl)] if cv and cl else None


def _special_folder(imap, flag):
    typ, data = imap.list()
    for line in data or []:
        s = line.decode(errors="ignore")
        if flag in s:
            return s.rsplit(' "/" ', 1)[-1].strip().strip('"')
    return None


def _imap(user, pw):
    imap = imaplib.IMAP4_SSL(HOST)
    imap.login(user, pw)
    return imap


def prepare(jobs, cfg, today=None):
    """Draft (or send) email applications for eligible jobs. Returns list of ledger entries made this run."""
    s = _settings(cfg)
    user, pw = credentials()
    if not user:
        log.info("email applications off: CANDIDATE_EMAIL / KRANTI_GMAIL_APP_PASSWORD not set")
        return []
    if "[phone]" in compose_body({"title": ""}, {"salutation": "", "hook": ""}, "en"):
        log.warning("email applications skipped: CANDIDATE_PHONE secret missing (signature would be incomplete)")
        return []
    today = today or date.today().isoformat()
    ledger = load()
    done_companies = {v["company_key"] for v in ledger.values()}
    left = s["max_per_day"] - sum(1 for v in ledger.values() if v["created"] == today)
    made, imap, drafts = [], None, None
    for job in sorted(jobs, key=lambda j: -j["score"]):
        if left <= 0:
            break
        if job["score"] < s["min_score"] or job.get("applied") or not job.get("letters"):
            continue
        ck = _company_key(job)
        to = pick_email(job)
        if not to or ck in done_companies:
            continue
        lang = "de" if job.get("lang") == "de" else "en"
        letter = job["letters"].get(lang)
        files = _files(job, lang)
        if not letter or not files:
            log.info("no email application for %s: %s letter/PDF missing", job["title"], lang)
            continue
        msg = build_message(job, to, lang, letter, files, user)
        try:
            if s["mode"] == "send":
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                    smtp.login(user, pw)
                    smtp.send_message(msg)
                status = "sent"
            else:
                if imap is None:
                    imap = _imap(user, pw)
                    drafts = _special_folder(imap, "\\Drafts") or "[Gmail]/Drafts"
                typ, _ = imap.append(f'"{drafts}"', "(\\Draft)", imaplib.Time2Internaldate(time.time()),
                                     msg.as_bytes())
                if typ != "OK":
                    raise RuntimeError(f"IMAP append returned {typ}")
                status = "draft"
        except Exception as ex:
            log.warning("email application for %s failed: %s", job["title"], ex)
            continue
        entry = {"company": job["company"], "company_key": ck, "title": job["title"], "url": job["url"],
                 "to": to, "lang": lang, "score": job["score"], "subject": msg["Subject"],
                 "status": status, "created": today, "sent": today if status == "sent" else ""}
        ledger[msg["Message-ID"]] = entry
        done_companies.add(ck)
        job["email_application"] = entry
        made.append(entry)
        left -= 1
        if status == "sent":
            _log_applied(entry)
    if imap:
        imap.logout()
    save(ledger)
    log.info("email applications: %d prepared (%s mode)", len(made), s["mode"])
    return made


def _log_applied(entry):
    """Append to APPLIED.md so the digest marks the job as applied."""
    line = f"- {entry['sent']} {entry['url']} ({entry['company']}, emailed to {entry['to']})\n"
    text = applied.FILE.read_text() if applied.FILE.exists() else "# Applied\n\n## My applications\n"
    if entry["url"] not in text:
        applied.FILE.write_text(text.rstrip("\n") + "\n" + line)


def sync():
    """Update the ledger from Gmail: drafts she has sent, and replies from companies. Returns ledger."""
    ledger = load()
    user, pw = credentials()
    open_ = {k: v for k, v in ledger.items() if v["status"] in ("draft", "sent")}
    if not user or not open_:
        return ledger
    try:
        imap = _imap(user, pw)
        sent_box = _special_folder(imap, "\\Sent") or "[Gmail]/Sent Mail"
        all_box = _special_folder(imap, "\\All") or "[Gmail]/All Mail"
        for mid, v in open_.items():
            since = datetime.fromisoformat(v["created"]).strftime("%Y/%m/%d")
            if v["status"] == "draft":
                imap.select(f'"{sent_box}"', readonly=True)
                typ, data = imap.search(None, "X-GM-RAW", f'"to:{v["to"]} after:{since}"')
                if typ == "OK" and data and data[0].split():
                    v["status"], v["sent"] = "sent", date.today().isoformat()
                    _log_applied(v)
                elif date.today() - date.fromisoformat(v["created"]) > timedelta(days=14):
                    v["status"] = "not sent"  # she decided against it; company stays blocked
            if v["status"] == "sent":
                imap.select(f'"{all_box}"', readonly=True)
                domain = v["to"].split("@")[1]
                who = v["to"] if FREEMAIL.search(domain) else domain  # gmail.com etc.: only that person
                typ, data = imap.search(None, "X-GM-RAW", f'"from:{who} after:{since} -in:sent"')
                if typ == "OK" and data and data[0].split():
                    v["status"], v["replied"] = "replied", date.today().isoformat()
        imap.logout()
    except Exception as ex:
        log.warning("Gmail sync failed: %s", ex)
    save(ledger)
    return ledger


def digest_block(made, ledger, mode):
    """HTML block for the digest email."""
    import html
    e = html.escape
    if not made and not ledger:
        return ""
    waiting = [v for v in ledger.values() if v["status"] == "draft"]
    sent = [v for v in ledger.values() if v["status"] in ("sent", "replied")]
    replied = [v for v in ledger.values() if v["status"] == "replied"]
    out = ["<div style='border:2px solid #0969da;border-radius:8px;padding:10px 14px;margin:14px 0'>",
           "<div style='font-weight:bold;margin-bottom:6px'>✉️ Email applications</div>"]
    if made:
        verb = "sent" if mode == "send" else "ready in your Gmail Drafts — open Gmail → Drafts, read, press Send"
        out.append(f"<div style='font-size:14px'>New this run ({len(made)}), {verb}:</div><ul style='margin:4px 0;font-size:14px'>"
                   + "".join(f"<li><b>{v['score']}</b> · {e(v['title'])} — {e(v['company'])} → {e(v['to'])}</li>" for v in made)
                   + "</ul>")
    out.append(f"<div style='font-size:13px;color:#57606a'>Waiting in Drafts: {len(waiting)} · Sent: {len(sent)} · "
               f"Replies received: <b>{len(replied)}</b></div>")
    if replied:
        out.append("<div style='font-size:14px;margin-top:6px'>📬 Replies from: "
                   + ", ".join(e(v["company"]) for v in replied) + " — check your inbox!</div>")
    return "".join(out) + "</div>"


if __name__ == "__main__":  # python -m hunter.outreach  (workflow input "email_backfill")
    import yaml
    from . import digest
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    made, jobs = backfill(cfg)
    body = ("<div style='font-family:Arial,sans-serif;max-width:640px;margin:0 auto'>"
            f"<h2>Email applications for jobs already found</h2>"
            f"<p>{len(jobs)} strong open jobs name an application email address.</p>"
            + digest_block(made, load(), _settings(cfg)["mode"]) + "</div>")
    digest.send(f"✉️ {len(made)} email applications ready in Kranti's Gmail Drafts", body,
                [a for j in jobs if j.get("email_application") for a in j.get("attachments", [])])
