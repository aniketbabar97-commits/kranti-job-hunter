"""Job sources. Each returns a list of normalized job dicts."""
import html
import logging
import os
import re
import time
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

AA_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
AA_HEADERS = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "Jobsuche/2.9.2"}


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _job(source, title, company, location, url, posted="", remote=False, description="", salary="", contact=""):
    contact = contact or ", ".join(dict.fromkeys(EMAIL.findall(description or "")))[:120]
    return {
        "contact": contact,
        "source": source,
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip(),
        "url": url,
        "posted": str(posted or "")[:10],
        "remote": bool(remote),
        "description": (description or "")[:4000],
        "salary": salary,
    }


def arbeitsagentur_details(job):
    """Full posting text + application email for an Arbeitsagentur job (the search API returns neither)."""
    import base64
    ref = job["url"].rstrip("/").split("/")[-1]
    r = requests.get("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
                     + base64.b64encode(ref.encode()).decode(), headers=AA_HEADERS, timeout=30)
    r.raise_for_status()
    d = r.json()
    text = d.get("stellenangebotsBeschreibung") or ""
    if text:
        job["description"] = text[:4000]
    emails = [e for e in EMAIL.findall(r.text) if "arbeitsagentur" not in e.lower()]
    if emails:
        job["contact"] = ", ".join(dict.fromkeys(emails))[:200]
    return job


def arbeitsagentur(query, days=2, max_pages=3):
    """Federal employment agency (Bundesagentur für Arbeit) - all of Germany."""
    jobs = []
    for page in range(1, max_pages + 1):
        params = {"was": query, "size": 100, "page": page, "angebotsart": 1}
        if days:  # None = every posting still open, however old
            params["veroeffentlichtseit"] = days
        r = requests.get(AA_URL, params=params, headers=AA_HEADERS, timeout=30)
        r.raise_for_status()
        items = r.json().get("ergebnisliste") or []
        for it in items:
            loc = (it.get("stellenlokationen") or [{}])[0].get("adresse", {})
            salary = ""
            if it.get("gehaltsspanneVon"):
                salary = f"€{int(it['gehaltsspanneVon']):,}–{int(it.get('gehaltsspanneBis') or 0):,}"
            jobs.append(_job(
                "Arbeitsagentur",
                it.get("stellenangebotsTitel") or it.get("titel"),
                it.get("firma"),
                f"{loc.get('ort', '')}, {loc.get('region', '').replace('_', '-').title()}".strip(", "),
                f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{it['referenznummer']}",
                it.get("datumErsteVeroeffentlichung") or it.get("aktuelleVeroeffentlichungsdatum"),
                it.get("homeofficemoeglich", False),
                " ".join(it.get("alleBerufe") or []),
                salary,
            ))
        if len(items) < 100:
            break
        time.sleep(1)
    return jobs


def jobspy(query, location, hours_old, results, remote_only=False):
    """LinkedIn + Indeed via the JobSpy library."""
    from jobspy import scrape_jobs

    df = scrape_jobs(
        site_name=["linkedin", "indeed"],
        search_term=query,
        location=location,
        country_indeed="germany",
        is_remote=remote_only,
        results_wanted=results,
        hours_old=hours_old,
        linkedin_fetch_description=False,
        verbose=0,
    )
    jobs = []
    for row in df.fillna("").to_dict("records"):
        salary = ""
        if row.get("min_amount"):
            salary = f"{row.get('currency', '')} {row['min_amount']}–{row.get('max_amount', '')} {row.get('interval', '')}".strip()
        jobs.append(_job(
            row["site"].title(), row["title"], row["company"], row["location"],
            row["job_url"], row["date_posted"], row.get("is_remote") is True,
            row.get("description", ""), salary,
            ", ".join(row["emails"]) if isinstance(row.get("emails"), list) else str(row.get("emails") or ""),
        ))
    return jobs


def _relative_date(text):
    """'4 days ago' / '3 hours ago' / 'Oct 6, 2026' -> ISO date ('' if unknown)."""
    m = re.match(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", text or "")
    if not m:
        return ""
    n, unit = int(m.group(1)), m.group(2)
    days = {"minute": 0, "hour": 0, "day": n, "week": 7 * n, "month": 30 * n}[unit]
    return (date.today() - timedelta(days=days)).isoformat()


def linkedin_posts(query, days=7):
    """Recruiter/hiring posts on LinkedIn, found through Google via Serper.dev (needs SERPER_API_KEY)."""
    key = os.environ["SERPER_API_KEY"]
    tbs = {1: "qdr:d", 7: "qdr:w"}.get(days, "qdr:w")
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    r = None
    # Free Serper accounts reject "num" ("Query pattern not allowed"); fall back to a bare query if tbs is refused too.
    for payload in ({"q": query, "tbs": tbs}, {"q": query}):
        r = requests.post("https://google.serper.dev/search", timeout=30, headers=headers, json=payload)
        if r.status_code != 400:
            break
        log.warning("serper 400 for %s: %s", sorted(payload), r.text[:200])
    if not r.ok:
        raise RuntimeError(f"serper {r.status_code}: {r.text[:200]}")
    jobs = []
    for it in r.json().get("organic", []):
        if "linkedin.com/posts" not in it.get("link", "") and "linkedin.com/feed" not in it.get("link", ""):
            continue
        title = it.get("title", "")
        # Google titles look like "#hiring SAP Commerce Architect ... | Jane Doe" or "Jane Doe's Post - LinkedIn"
        author = ""
        m = re.search(r"\|\s*([^|]+?)\s*(?:- LinkedIn)?$", title) or re.match(r"(.+?)'s Post", title)
        if m:
            author = m.group(1).strip()
        snippet = it.get("snippet", "")
        headline = re.sub(r"\s*\|[^|]*$|'s Post.*$|\s*- LinkedIn$|\s*posted (on|this).*$", "", title).strip()
        # Titles that are just a person's name or a hashtag say nothing; use the post text instead.
        if not re.search(r"(?i)developer|engineer|consultant|architect|analyst|owner|lead|manager|entwickler|berater|hiring|sap|hybris|commerce", headline) or headline == author:
            headline = re.sub(r"\s+", " ", snippet)[:90].rstrip(" .,") + ("…" if len(snippet) > 90 else "")
        jobs.append(_job("LinkedIn post", f"[Post] {headline}", author or "LinkedIn recruiter post", "",
                         it["link"], _relative_date(it.get("date", "")), "remote" in snippet.lower(), snippet))
    return jobs


# ---- Company career sites -------------------------------------------------------------
# Direct feeds of known SAP Commerce / e-commerce employers (free, no API key).

def _strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def personio(slug, company):
    import xml.etree.ElementTree as ET
    r = requests.get(f"https://{slug}.jobs.personio.de/xml", timeout=30)
    r.raise_for_status()
    jobs = []
    for p in ET.fromstring(r.content).iter("position"):
        desc = " ".join(_strip_html(d.findtext("value")) for d in p.iter("jobDescription"))
        office = p.findtext("office") or ""
        jobs.append(_job(f"{company} careers", p.findtext("name"), company, office,
                         f"https://{slug}.jobs.personio.de/job/{p.findtext('id')}",
                         (p.findtext("createdAt") or "")[:10], "remote" in f"{office} {desc}".lower(), desc))
    return jobs


def greenhouse(slug, company):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"}, timeout=30)
    r.raise_for_status()
    return [_job(f"{company} careers", j["title"], company, (j.get("location") or {}).get("name", ""),
                 j["absolute_url"], (j.get("first_published") or j.get("updated_at") or "")[:10],
                 "remote" in str(j.get("location")).lower(), _strip_html(html.unescape(j.get("content") or "")))
            for j in r.json().get("jobs", [])]


def lever(slug, company):
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=30)
    r.raise_for_status()
    out = []
    for j in r.json():
        created = j.get("createdAt")
        posted = date.fromtimestamp(created / 1000).isoformat() if created else ""
        loc = (j.get("categories") or {}).get("location", "")
        out.append(_job(f"{company} careers", j.get("text"), company, loc, j.get("hostedUrl"), posted,
                        (j.get("workplaceType") == "remote") or "remote" in loc.lower(), j.get("descriptionPlain", "")))
    return out


COMPANY_FEEDS = {"personio": personio, "greenhouse": greenhouse, "lever": lever}


def company_feed(entry):
    if entry["ats"] == "smartrecruiters":  # huge companies: search their feed instead of downloading all of it
        jobs = []
        for q in entry.get("search", ["hybris", "SAP Commerce", "e-commerce"]):
            jobs += smartrecruiters(entry["slug"], entry["name"], q)
        return jobs
    return COMPANY_FEEDS[entry["ats"]](entry["slug"], entry["name"])


# Google "X-ray" search across career sites hosted on common hiring systems (needs SERPER_API_KEY).
ATS_NAMES = [("personio", "Personio"), ("smartrecruiters", "SmartRecruiters"), ("myworkdayjobs", "Workday"),
             ("successfactors", "SuccessFactors"), ("sapsf", "SuccessFactors"), ("greenhouse", "Greenhouse"),
             ("lever.co", "Lever"), ("ashbyhq", "Ashby"), ("join.com", "JOIN"), ("softgarden", "softgarden"),
             ("recruitee", "Recruitee"), ("teamtailor", "Teamtailor"), ("jobs.sap.com", "SAP careers"),
             ("workable", "Workable"), ("d.vinci", "d.vinci"), ("onlyfy", "onlyfy")]


def _serper(query, days):
    headers = {"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"}
    tbs = {1: "qdr:d", 7: "qdr:w", 30: "qdr:m"}.get(days, "qdr:w")
    r = None
    for payload in ({"q": query, "tbs": tbs}, {"q": query}):
        r = requests.post("https://google.serper.dev/search", timeout=30, headers=headers, json=payload)
        if r.status_code != 400:
            break
        log.warning("serper 400 for %s: %s", sorted(payload), r.text[:200])
    if not r.ok:
        raise RuntimeError(f"serper {r.status_code}: {r.text[:200]}")
    return r.json().get("organic", [])


def career_sites(query, days=30):
    jobs = []
    for it in _serper(query, days):
        link = it.get("link", "")
        ats = next((name for key, name in ATS_NAMES if key in link), "company site")
        title = re.sub(r"\s*[-|–]\s*(Jobs? (at|bei)|Karriere|Careers?|Stellenangebot).*$", "", it.get("title", ""), flags=re.I)
        company = ""
        m = re.search(r"https?://([\w-]+)\.(jobs\.personio|softgarden|recruitee|teamtailor)", link) \
            or re.search(r"(?:smartrecruiters\.com|greenhouse\.io|lever\.co|ashbyhq\.com)/([\w-]+)", link) \
            or re.search(r"https?://([\w-]+)\.wd\d+\.myworkdayjobs", link)
        if m:
            company = m.group(1).replace("-", " ").title()
        jobs.append(_job(f"Career site ({ats})", title, company or "see posting", "", link,
                         _relative_date(it.get("date", "")), "remote" in it.get("snippet", "").lower(), it.get("snippet", "")))
    return jobs


def smartrecruiters(slug, company, query):
    r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                     params={"q": query, "limit": 100}, timeout=30)
    r.raise_for_status()
    return [_job(f"{company} careers", p.get("name"), company,
                 ", ".join(x for x in [(p.get("location") or {}).get("city"), (p.get("location") or {}).get("country")] if x),
                 f"https://jobs.smartrecruiters.com/{slug}/{p.get('id')}", (p.get("releasedDate") or "")[:10],
                 bool((p.get("location") or {}).get("remote")), "")
            for p in r.json().get("content", [])]
