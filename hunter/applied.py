"""Applications the user tracks by hand in APPLIED.md (job links or company names, optional date)."""
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "APPLIED.md"
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+")
LEGAL = re.compile(r"\b(gmbh|ag|se|kg|co|mbh|ltd|inc|llc|group|gruppe|deutschland|germany|industries|holding)\b")


def _company(name):
    return re.sub(r"[^a-z0-9]", "", LEGAL.sub("", (name or "").lower()))


def _url(u):
    return re.sub(r"[?#].*$", "", (u or "").strip().lower()).rstrip("/")

# an APPLIED.md line counts as a website application when it says so ("website", "via form", "via Claude")
WEBSITE = re.compile(r"website|webseite|via form|via claude|online", re.I)
NOT_DONE = re.compile(r"not submitted|nicht gesendet|parked|skip|pending|closed|error", re.I)


def load():
    """Return {'urls': set, 'companies': set, 'entries': [(date|None, text)]}."""
    urls, companies, entries, web = set(), set(), [], set()
    if not FILE.exists():
        return {"urls": urls, "companies": companies, "entries": entries, "web": web}
    started = False
    for raw in FILE.read_text(encoding="utf-8").splitlines():
        if raw.strip().lower().startswith("## my applications"):
            started = True
            continue
        line = raw.strip().lstrip("-*").strip()
        if not started or not line or line.startswith(("#", ">")):
            continue
        when = None
        m = DATE.match(line)
        if m:
            when, line = m.group(1), line[m.end():].strip()
        entries.append((when, line))
        link = re.search(r"https?://\S+", line)
        if link:
            urls.add(_url(link.group(0)))
            if WEBSITE.search(line) and not NOT_DONE.search(line):
                web.add(_url(link.group(0)))
        elif _company(line):
            companies.add(_company(line))
    return {"urls": urls, "companies": companies, "entries": entries, "web": web}


def website_done(job, data):
    """True once the website application for this job is logged — only then may the HR email go out.
    Jobs that can only be applied to by email (no web form anywhere) are always ready."""
    if job.get("channel") == "email":
        return True
    return bool({_url(job.get("url")), _url(job.get("direct_url"))} & data["web"])


def status(job, data):
    """'applied' if this exact job is listed, 'company' if the company is, else ''."""
    if _url(job.get("url")) in data["urls"]:
        return "applied"
    company = _company(job.get("company"))
    if company and any(c == company or (len(c) >= 4 and c in company) for c in data["companies"]):
        return "company"
    return ""


def count_since(data, since):
    return sum(1 for when, _ in data["entries"] if when and when >= since.isoformat())
