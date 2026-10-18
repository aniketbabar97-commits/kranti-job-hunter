"""Weekly gap check: Google (Serper) searches for SAP Commerce openings, compared with data/jobs_log.csv.
Postings Google knows about but the hunter never sent show where a source is missing. Needs SERPER_API_KEY
(skipped without it)."""
import logging
import os
import re

from . import report, sources

log = logging.getLogger(__name__)

GAP_QUERIES = [
    '("SAP Commerce" OR Hybris) Stellenangebot Baden-Württemberg',
    '("SAP Commerce" OR Hybris) (Entwickler OR Developer OR Consultant) (Stuttgart OR Karlsruhe OR Mannheim OR Walldorf OR Heidelberg OR Freiburg OR Ulm)',
    '("SAP Commerce Cloud" OR "SAP CX") job Germany (m/w/d)',
    '(Hybris OR "SAP Commerce") remote Deutschland Stelle',
]
BOARD_TAIL = re.compile(r"\s*[-|–:]\s*(Jobs?|Stellenangebot|Karriere|Careers?|StepStone|Indeed|LinkedIn|XING|Glassdoor|bei|at)\b.*$", re.I)
CORE = re.compile(r"(?i)hybris|sap commerce|commerce cloud|sap cx|spartacus")


def _norm(s):
    return re.sub(r"\(.*?\)|[^a-z0-9]", "", (s or "").lower())


def find_gaps(limit=20):
    if not os.getenv("SERPER_API_KEY"):
        log.info("gapcheck skipped: no SERPER_API_KEY")
        return []
    logged = report.read_log()
    titles = {_norm(r["title"]) for r in logged}
    urls = {r["url"] for r in logged}
    gaps, seen = [], set()
    for q in GAP_QUERIES:
        try:
            results = sources._serper(q, 7)
        except Exception as e:  # noqa: BLE001
            log.warning("gapcheck %r failed: %s", q, e)
            continue
        for it in results:
            title = BOARD_TAIL.sub("", it.get("title", "")).strip()
            t = _norm(title)
            link = it.get("link", "")
            if not CORE.search(f"{title} {it.get('snippet', '')}") or link in urls or t in seen or "linkedin.com/posts" in link:
                continue
            # Same title already logged (title is the reliable part of a Google result; company usually is not).
            if t and any(t in x or x in t for x in titles if len(x) > 12):
                continue
            seen.add(t)
            gaps.append({"title": title, "url": link, "snippet": it.get("snippet", "")[:160]})
    return gaps[:limit]


def html_block(gaps):
    import html
    if not gaps:
        return ""
    e = html.escape
    return ("<h3>🔍 Found on Google but not by the hunter</h3><p style='font-size:13px;color:#57606a'>"
            "Check these by hand; if many come from one site, that site needs a source.</p><ul>"
            + "".join(f"<li><a href='{e(g['url'])}' style='color:#0969da'>{e(g['title'])}</a>"
                      f"<br><span style='font-size:12px;color:#57606a'>{e(g['snippet'])}</span></li>" for g in gaps)
            + "</ul>")
