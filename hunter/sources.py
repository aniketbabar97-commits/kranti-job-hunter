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
    if d.get("externeUrl"):
        job["apply_url"] = d["externeUrl"]
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


JOBSPY_SITES = ["linkedin", "indeed", "glassdoor", "google"]


def jobspy(query, location, hours_old, results, remote_only=False, sites=None):
    """LinkedIn, Indeed, Glassdoor and Google Jobs via the JobSpy library. Each site is scraped on its
    own so one blocked site (Glassdoor often answers 403 from data-center IPs) does not lose the others."""
    from jobspy import scrape_jobs

    frames = []
    for site in sites or JOBSPY_SITES:
        kwargs = dict(site_name=[site], search_term=query, location=location, country_indeed="germany",
                      is_remote=remote_only, results_wanted=results, hours_old=hours_old,
                      linkedin_fetch_description=False, verbose=0)
        if site == "google":
            kwargs["google_search_term"] = f"{query} jobs {location}" + (" remote" if remote_only else "")
        try:
            df = scrape_jobs(**kwargs)
        except Exception as e:  # noqa: BLE001 - per-site failures must not kill the run
            log.warning("jobspy %s %r failed: %s", site, query, e)
            continue
        if df is not None and len(df):
            frames.append(df)
    if not frames:
        return []
    import pandas as pd
    df = pd.concat(frames, ignore_index=True)
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


SEARCH_TERMS = ["hybris", "SAP Commerce", "e-commerce"]


def company_feed(entry):
    """One configured employer -> its open jobs. Big ATSes are searched, small ones downloaded whole."""
    ats, name = entry["ats"], entry["name"]
    terms = entry.get("search", SEARCH_TERMS)
    searched = {"smartrecruiters": lambda q: smartrecruiters(entry["slug"], name, q),
                "workday": lambda q: workday_search(entry["url"], q, name),
                "successfactors": lambda q: successfactors_search(entry["url"], q, name)}
    if ats in searched:  # huge companies: search their feed instead of downloading all of it
        jobs = []
        for q in terms:
            jobs += searched[ats](q)
        return list({j["url"]: j for j in jobs}.values())
    if ats == "softgarden":
        return softgarden(entry["slug"], name)
    if ats == "join":
        return join_com(entry["slug"], name)
    if ats not in COMPANY_FEEDS:  # own / unknown careers page: covered by the Google career-site searches
        return []
    return COMPANY_FEEDS[ats](entry["slug"], name)


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


# ---- Job boards: StepStone, XING ------------------------------------------------------
# Notes on why each works this way: helper/knowledge/scrapers.md

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/129.0 Safari/537.36")
CHROMIUM = os.getenv("PW_CHROMIUM", "/opt/pw-browsers/chromium")
BLOCKED = re.compile(r"(?i)captcha|are you a human|access denied|unusual traffic|px-captcha|datadome|incapsula|cf-chl")


def _slug(text):
    t = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def stepstone(query, location="Deutschland", days=7, timeout=30):
    """StepStone search results via headless Chromium (plain requests hang from data-center IPs).
    Returns [] (logged) when blocked or slow."""
    from urllib.parse import quote
    age = "age_1" if days <= 1 else "age_7"
    url = f"https://www.stepstone.de/jobs/{quote(_slug(query))}/in-{quote(_slug(location))}?ag={age}"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("stepstone: playwright not installed")
        return []
    jobs = []
    try:
        with sync_playwright() as p:
            kw = {"headless": True}
            if os.path.exists(CHROMIUM):
                kw["executable_path"] = CHROMIUM
            browser = p.chromium.launch(**kw)
            try:
                page = browser.new_page(user_agent=BROWSER_UA, locale="de-DE")
                page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
                try:
                    page.wait_for_selector('[data-at="job-item"]', timeout=8000)
                except Exception:  # noqa: BLE001
                    pass
                cards = page.locator('[data-at="job-item"]')
                if not cards.count():
                    body = page.content()
                    if BLOCKED.search(body[:20000]):
                        log.warning("stepstone blocked for %r", query)
                    return []
                for i in range(cards.count()):
                    c = cards.nth(i)
                    get = lambda sel: (c.locator(f'[data-at="{sel}"]').first.inner_text(timeout=2000)
                                       if c.locator(f'[data-at="{sel}"]').count() else "")
                    link = c.locator('a[href*="stellenangebote--"]').first
                    href = link.get_attribute("href") if link.count() else ""
                    if not href:
                        continue
                    href = href if href.startswith("http") else "https://www.stepstone.de" + href
                    location_ = get("job-item-location")
                    jobs.append(_job("StepStone", get("job-item-title"), get("job-item-company-name"), location_,
                                     href.split("?")[0], _relative_de(get("job-item-timeago")),
                                     "home" in location_.lower() or "remote" in location_.lower(),
                                     c.inner_text(timeout=2000)))
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001
        log.warning("stepstone %r failed: %s", query, e)
        return []
    return jobs


def _relative_de(text):
    """'vor 3 Tagen' / 'vor 2 Stunden' / 'Gestern' -> ISO date."""
    t = (text or "").lower()
    if "gestern" in t:
        return (date.today() - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s*(minute|stunde|tag|woche|monat)", t)
    if not m:
        return date.today().isoformat() if "heute" in t or "neu" in t else ""
    n, unit = int(m.group(1)), m.group(2)
    return (date.today() - timedelta(days={"minute": 0, "stunde": 0, "tag": n, "woche": 7 * n, "monat": 30 * n}[unit])).isoformat()


_XING_URLS = None  # [(url, lastmod)] cached for the run: ~600k URLs in 12 gzip chunks


def _xing_sitemap():
    global _XING_URLS
    if _XING_URLS is None:
        import gzip
        hdr = {"User-Agent": BROWSER_UA}
        unz = lambda b: gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b
        idx = unz(requests.get("https://www.xing.com/jobs/sitemap.xml.gz", headers=hdr, timeout=30).content).decode()
        out = []
        for chunk in re.findall(r"<loc>([^<]+)</loc>", idx):
            try:
                xml = unz(requests.get(chunk, headers=hdr, timeout=60).content).decode("utf-8", "ignore")
            except Exception as e:  # noqa: BLE001
                log.warning("xing sitemap chunk %s failed: %s", chunk, e)
                continue
            out += re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]{10})", xml)
        _XING_URLS = out
    return _XING_URLS


def xing(query, days=7, max_pages=40):
    """XING jobs: keyword-match the job sitemap's URL slugs, then read each page's JobPosting JSON-LD
    (/jobs/search is disallowed in robots.txt)."""
    import json
    words = _slug(query).split("-")
    cutoff = (date.today() - timedelta(days=days)).isoformat() if days else ""
    hits = [(u, lm) for u, lm in _xing_sitemap() if lm >= cutoff
            and all(re.search(rf"(^|-){re.escape(w)}(-|$)", u.rsplit("/", 1)[-1]) for w in words)]
    jobs = []
    for u, lm in sorted(hits, key=lambda x: x[1], reverse=True)[:max_pages]:
        try:
            r = requests.get(u, headers={"User-Agent": BROWSER_UA, "Accept-Language": "de"}, timeout=30)
            if r.status_code != 200:
                continue
            d = None
            for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', r.text, re.S):
                cand = json.loads(m.group(1))
                if isinstance(cand, dict) and cand.get("@type") == "JobPosting":
                    d = cand
                    break
            if not d:
                continue
            fix = lambda s: s.encode("latin-1").decode("utf-8") if "Ã" in (s or "") else (s or "")
            locs = d.get("jobLocation") or []
            locs = locs if isinstance(locs, list) else [locs]
            place = ", ".join(dict.fromkeys(fix((l.get("address") or {}).get("addressLocality", "")) for l in locs if isinstance(l, dict)))
            jobs.append(_job("XING", fix(d.get("title")), fix((d.get("hiringOrganization") or {}).get("name", "")),
                             place, u, (d.get("datePosted") or lm)[:10],
                             d.get("jobLocationType") == "TELECOMMUTE", _strip_html(html.unescape(fix(d.get("description"))))))
        except Exception as e:  # noqa: BLE001
            log.warning("xing page %s failed: %s", u, e)
        time.sleep(0.5)
    return jobs


# ---- Workday / SuccessFactors / softgarden / JOIN career sites -------------------------

def workday_search(tenant_url, query, company="", limit=20):
    """Workday CXS JSON: tenant_url like https://zeissgroup.wd3.myworkdayjobs.com/External."""
    m = re.match(r"(https://([\w-]+)\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)", tenant_url)
    if not m:
        raise ValueError(f"not a Workday site URL: {tenant_url}")
    host, tenant, site = m.groups()
    r = requests.post(f"{host}/wday/cxs/{tenant}/{site}/jobs", timeout=30,
                      headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": BROWSER_UA},
                      json={"appliedFacets": {}, "limit": limit, "offset": 0, "searchText": query})
    r.raise_for_status()
    company = company or tenant.title()
    out = []
    for p in r.json().get("jobPostings", []):
        posted = p.get("postedOn", "")
        n = re.search(r"(\d+)", posted)
        iso = date.today().isoformat() if "today" in posted.lower() else \
            (date.today() - timedelta(days=1)).isoformat() if "yesterday" in posted.lower() else \
            (date.today() - timedelta(days=int(n.group(1)))).isoformat() if n and "30+" not in posted else ""
        out.append(_job(f"{company} careers", p.get("title"), company, p.get("locationsText", ""),
                        f"{host}/{site}{p.get('externalPath', '')}", iso, "remote" in str(p).lower(), ""))
    return out


def successfactors_search(portal_url, query, company=""):
    """SuccessFactors RMK career site (server-rendered): portal_url like https://jobs.zf.com."""
    from bs4 import BeautifulSoup
    base = portal_url.rstrip("/")
    r = requests.get(f"{base}/search/", params={"q": query, "locationsearch": ""}, timeout=30,
                     headers={"User-Agent": BROWSER_UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    company = company or re.sub(r"^(jobs|careers?|karriere)\.", "", base.split("//")[-1]).split(".")[0].title()
    out = []
    for row in soup.select("tr.data-row"):
        a = row.select_one("a.jobTitle-link")
        if not a:
            continue
        loc = row.select_one("span.jobLocation")
        dt = row.select_one("span.jobDate")
        posted = ""
        if dt:
            from datetime import datetime
            for fmt in ("%d.%m.%Y", "%b %d, %Y", "%d %b %Y", "%m/%d/%Y"):
                try:
                    posted = datetime.strptime(dt.get_text(strip=True), fmt).date().isoformat()
                    break
                except ValueError:
                    pass
        loc_t = re.sub(r"\s+", " ", loc.get_text(" ", strip=True)) if loc else ""
        out.append(_job(f"{company} careers", a.get_text(strip=True), company, loc_t,
                        base + a["href"], posted, "remote" in loc_t.lower(), ""))
    return out


def softgarden(slug, company, query=""):
    """softgarden career site: https://<slug>.softgarden.io/de/vacancies (server-rendered list)."""
    from bs4 import BeautifulSoup
    r = requests.get(f"https://{slug}.softgarden.io/de/vacancies", headers={"User-Agent": BROWSER_UA}, timeout=30)
    r.raise_for_status()
    out = []
    for a in BeautifulSoup(r.text, "html.parser").select("a[href*='/job/']"):
        title = a.get_text(" ", strip=True)
        if title and (not query or query.lower() in title.lower()):
            href = a["href"] if a["href"].startswith("http") else f"https://{slug}.softgarden.io{a['href']}"
            out.append(_job(f"{company} careers", title, company, "", href, "", "remote" in title.lower(), ""))
    return list({j["url"]: j for j in out}.values())


def join_com(slug, company, query=""):
    """JOIN company page: job list is in the page's __NEXT_DATA__."""
    import json
    r = requests.get(f"https://join.com/companies/{slug}", headers={"User-Agent": BROWSER_UA}, timeout=30)
    r.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return []
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("title") and o.get("idParam"):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(json.loads(m.group(1)))
    return [_job(f"{company} careers", j["title"], company, (j.get("city") or {}).get("cityName", "") if isinstance(j.get("city"), dict) else "",
                 f"https://join.com/companies/{slug}/{j['idParam']}", (j.get("createdAt") or "")[:10],
                 j.get("workplaceType") == "REMOTE", "")
            for j in found if not query or query.lower() in j["title"].lower()]
