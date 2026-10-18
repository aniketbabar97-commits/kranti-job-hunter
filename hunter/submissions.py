"""Hunter-side view of helper submissions (data/submissions.json): match pending ones against confirmation-of-receipt
mails, move the confirmed ones into APPLIED.md (+ ATS trust), and list the ones she should check herself."""
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "submissions.json"
CHECK = ROOT / "data" / "check.json"
WINDOW = timedelta(hours=24)
LEGAL = re.compile(r"\b(gmbh|ag|se|kg|co|mbh|ltd|inc|llc|group|gruppe|deutschland|germany|holding|& co)\b", re.I)
log = logging.getLogger(__name__)


def _key(name):
    return re.sub(r"[^a-z0-9]", "", LEGAL.sub("", (name or "").lower()))


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []
    except Exception:
        return []


def save(items):
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")


def _ts(s):
    try:
        return datetime.fromisoformat(s["ts"])
    except Exception:
        return datetime.min


def _same_company(a, b):
    ka, kb = _key(a), _key(b)
    return bool(ka and kb) and (ka == kb or (len(ka) >= 4 and ka in kb) or (len(kb) >= 4 and kb in ka))


def reconcile(receipts, now=None):
    """receipts: iterable of {"date": iso, "company": str} with category 'received'.
    A pending submission whose company got a receipt within 24 h -> proof 'mail', APPLIED.md line, trust ok.
    Pending older than 24 h without mail -> data/check.json. Returns (confirmed, to_check)."""
    from helper import proof, trust
    now = now or datetime.now()
    items = load()
    confirmed, check = [], []
    changed = False
    for s in items:
        if s.get("status") != "pending":
            continue
        ts = _ts(s)
        hit = None
        for r in receipts:
            if r.get("category", "received") != "received" or not _same_company(r.get("company"), s.get("company")):
                continue
            try:
                when = datetime.fromisoformat(r["date"]).date()  # mail dates are day-granular
            except Exception:
                continue
            if ts.date() <= when <= (ts + WINDOW).date():
                hit = r
                break
        if hit:
            s.update({"proof": "mail", "status": "confirmed", "confirmed_ts": now.isoformat(timespec="seconds")})
            proof.applied_line({"url": s["url"], "company": s["company"], "title": s.get("title", "")}, "confirmed")
            trust.record(s.get("ats", "own"), True)
            confirmed.append(s)
            changed = True
        elif now - ts > WINDOW:
            check.append({"url": s["url"], "company": s["company"], "title": s.get("title", ""), "ts": s["ts"],
                          "screenshot": s.get("screenshot", "")})
    if changed:
        save(items)
    CHECK.parent.mkdir(exist_ok=True)
    CHECK.write_text(json.dumps(check, indent=1, ensure_ascii=False), encoding="utf-8")
    if confirmed or check:
        log.info("submissions: %d confirmed by mail, %d to check", len(confirmed), len(check))
    return confirmed, check


def load_check():
    try:
        return json.loads(CHECK.read_text(encoding="utf-8")) if CHECK.exists() else []
    except Exception:
        return []


def check_block(items=None):
    """Digest block: submissions older than 24 h with neither thank-you page nor receipt mail."""
    import html
    items = load_check() if items is None else items
    if not items:
        return ""
    rows = "".join(f"<li><a href='{html.escape(s['url'])}' style='color:#0969da'>{html.escape(s.get('title') or s['url'])}</a>"
                   f" — {html.escape(s['company'])} <span style='color:#57606a'>(submitted {html.escape(s['ts'][:16])})</span></li>"
                   for s in items)
    return ("<div style='border:2px solid #9a6700;border-radius:8px;padding:10px 14px;margin:14px 0'>"
            "<div style='font-weight:bold;margin-bottom:6px'>⚠️ Please check</div>"
            "<div style='font-size:13px;color:#57606a;margin-bottom:6px'>The helper submitted these, but neither a thank-you page "
            "nor a confirmation mail was seen. Open the job and check whether the application went through; "
            "if it did, add it to APPLIED.md.</div>"
            f"<ul style='margin:4px 0;font-size:14px'>{rows}</ul></div>")
