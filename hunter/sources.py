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


def personio(slug, company, query=None):
    import xml.etree.ElementTree as ET
    r = requests.get(f"https://{slug}.jobs.personio.de/xml", timeout=30)
    if r.status_code == 404:
        r = requests.get(f"https://{slug}.jobs.personio.com/xml", timeout=30)
    r.raise_for_status()
    jobs = []
    for p in ET.fromstring(r.content).iter("position"):
        desc = " ".join(_strip_html(d.findtext("value")) for d in p.iter("jobDescription"))
        office = p.findtext("office") or ""
        jobs.append(_job(f"{company} careers", p.findtext("name"), company, office,
                         f"https://{slug}.jobs.personio.de/job/{p.findtext('id')}",
                         (p.findtext("createdAt") or "")[:10], "remote" in f"{office} {desc}".lower(), desc))
    return jobs


def greenhouse(slug, company, query=None):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"}, timeout=30)
    r.raise_for_status()
    return [_job(f"{company} careers", j["title"], company, (j.get("location") or {}).get("name", ""),
                 j["absolute_url"], (j.get("first_published") or j.get("updated_at") or "")[:10],
                 "remote" in str(j.get("location")).lower(), _strip_html(html.unescape(j.get("content") or "")))
            for j in r.json().get("jobs", [])]


def lever(slug, company, query=None):
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




SEARCH_TERMS = ["hybris", "SAP Commerce", "e-commerce"]


def company_feed(entry):
    """One configured employer -> its open jobs. Big ATSes are searched, the rest downloaded whole
    (every opening; relevance filtering happens in main). ats own/unknown with a url -> career_page()."""
    ats, name = entry["ats"], entry["name"]
    terms = entry.get("search", SEARCH_TERMS)
    feed = entry.get("feed") if str(entry.get("feed", "")).startswith("http") else None
    if ats in ("phenom", "job-shop"):  # their 'feed' is an API host, the reader needs the site
        feed = None
    site = feed if feed and ats in ("workday", "successfactors") and "/sitemap" not in feed else entry.get("url")
    searched = {"smartrecruiters": lambda q: smartrecruiters(entry["slug"], name, q),
                "workday": lambda q: workday_search(site, q, name),
                "successfactors": lambda q: successfactors_search(site, q, name)}
    slug_first = ("personio", "greenhouse", "lever", "smartrecruiters", "join", "ashby", "workable", "recruitee")
    target = (entry.get("slug") if ats in slug_first else None) or feed or entry.get("slug") or entry.get("url")
    reader = ATS_READERS.get(ats)
    dedicated = ats in searched or (reader is not None and reader is not career_page)
    jobs, err = [], None
    try:
        if ats in searched and (entry.get("slug") or site):  # huge companies: search their feed
            for q in terms:
                jobs += searched[ats](q)
            jobs = list({j["url"]: j for j in jobs}.values())
        elif dedicated and target:
            jobs = reader(target, name)
    except Exception as e:  # noqa: BLE001
        err = e
        log.info("%s reader for %s failed (%s), trying the career page", ats, name, e)
    if not jobs and (entry.get("url") or feed) and (err or not dedicated or ats not in searched):
        # own/custom/unknown ATS, or the dedicated reader failed / came back empty
        page = (entry.get("url") or feed) if dedicated else (feed or entry.get("url"))
        jobs = career_page(page, name)
    if not jobs and err:
        raise err
    return jobs


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
            from urllib.parse import urljoin
            href = urljoin(f"https://{slug}.softgarden.io/de/vacancies", a["href"])
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


# ---- Direct career-portal readers ------------------------------------------------------
# Each takes (slug_or_url, company, query=None) and returns EVERY opening (optionally title-filtered by query).
# Notes: helper/knowledge/scrapers.md ("Career portals").

JOBISH_HREF = re.compile(r"(?i)stellenangebot|stellen|/jobs?/|/job[-_]|jobdetail|jobposting|karriere/|career|position|vacanc|"
                         r"offer|ausschreibung|/j/|requisition|opening")
JOBISH_TITLE = re.compile(r"(?i)\(\s*[mwfdx]\s*/\s*[mwfdx]|\b(m/w/d|w/m/d|f/m/d|m/f/d|all genders?)\b|developer|entwickler|"
                          r"engineer|manager|consultant|berater|architekt|architect|specialist|spezialist|referent|"
                          r"analyst|lead|leiter|werkstudent|praktik|intern|sachbearbeiter|techniker|ingenieur|expert|"
                          r"administrator|designer|scientist|kaufm|mitarbeiter|head of|owner|tester|trainee|azubi|ausbildung")
NOT_JOB = re.compile(r"(?i)^(jobs?|karriere|career|careers|stellenangebote|alle jobs|all jobs|offene stellen|mehr|more|"
                     r"apply|bewerben|jetzt bewerben|details|weiterlesen|read more|job alert|jobs? finden)$")


def _q(jobs, query):
    jobs = list({j["url"]: j for j in jobs if j.get("url") and j.get("title")}.values())
    return [j for j in jobs if not query or query.lower() in j["title"].lower()]


def _get(url, **kw):
    kw.setdefault("timeout", 30)
    kw.setdefault("headers", {"User-Agent": BROWSER_UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
    r = requests.get(url, **kw)
    r.raise_for_status()
    return r


def _base(slug_or_url, pattern):
    """slug -> pattern.format(slug); a full URL is used as is (scheme+host, or the whole URL if pattern is None)."""
    s = slug_or_url.strip().rstrip("/")
    if s.startswith("http"):
        return s
    return f"https://{s}" if "." in s else pattern.format(s)


def _walk(o, pred, out):
    if isinstance(o, dict):
        if pred(o):
            out.append(o)
        for v in o.values():
            _walk(v, pred, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, pred, out)
    return out


def _loc(v):
    if isinstance(v, list):
        return ", ".join(filter(None, (_loc(x) for x in v)))[:150]
    if isinstance(v, dict):
        return ", ".join(str(v[k]) for k in ("city", "name", "addressLocality", "region", "country") if v.get(k) and isinstance(v[k], str))
    return str(v or "")


def _html_jobs(url, company, query=None, href=JOBISH_HREF, source=None, html_text=None, strict=None):
    """Server-rendered job list: anchors whose href looks like a job detail and text like a job title."""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    text = html_text if html_text is not None else _get(url).text
    soup = BeautifulSoup(text, "html.parser")
    strict = (href is JOBISH_HREF) if strict is None else strict  # ATS-specific href pattern: trust the link
    out = _jsonld_jobs(soup, url, company)
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith(("mailto:", "tel:", "javascript:", "#")) or not href.search(h):
            continue
        t = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not (4 <= len(t) <= 160) or NOT_JOB.match(t) or (strict and not JOBISH_TITLE.search(t)):
            continue
        out.append(_job(source or f"{company} careers", t, company, "", urljoin(url, h).split("#")[0], "",
                        "remote" in t.lower(), ""))
    return _q(out, query)


def _jsonld_jobs(soup, url, company):
    import json
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except ValueError:
            continue
        for p in _walk(data, lambda o: o.get("@type") == "JobPosting", []):
            org = p.get("hiringOrganization")
            out.append(_job(f"{company} careers", p.get("title"), (org or {}).get("name", company) if isinstance(org, dict) else company,
                            _loc([x.get("address", x) for x in (p.get("jobLocation") if isinstance(p.get("jobLocation"), list) else [p.get("jobLocation") or {}])]),
                            p.get("url") or url, (p.get("datePosted") or "")[:10],
                            p.get("jobLocationType") == "TELECOMMUTE", _strip_html(html.unescape(p.get("description") or ""))))
    return out


def recruitee(slug_or_url, company, query=None):
    base = re.sub(r"/api/offers.*$", "", _base(slug_or_url, "https://{}.recruitee.com"))
    out = []
    for o in _get(f"{base}/api/offers/").json().get("offers", []):
        loc = o.get("location") or ", ".join(x for x in [o.get("city"), o.get("country")] if x)
        out.append(_job(f"{company} careers", o.get("title"), company, loc, o.get("careers_url") or f"{base}/o/{o.get('slug')}",
                        (o.get("published_at") or o.get("created_at") or "")[:10], bool(o.get("remote")),
                        _strip_html(html.unescape((o.get("description") or "") + " " + (o.get("requirements") or "")))))
    return _q(out, query)


def workable(slug_or_url, company, query=None):
    slug = slug_or_url.rstrip("/").split("/")[-1]
    out, token = [], None
    for _ in range(20):
        body = {"query": query or "", "location": [], "department": [], "worktype": [], "remote": []}
        if token:
            body["token"] = token
        r = requests.post(f"https://apply.workable.com/api/v3/accounts/{slug}/jobs", json=body, timeout=30,
                          headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
        if r.status_code == 429:  # rate limited: fall back to the widget feed
            r = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
            for j in r.json().get("jobs", []):
                out.append(_job(f"{company} careers", j.get("title"), company,
                                ", ".join(x for x in [j.get("city"), j.get("country")] if x), j.get("url") or j.get("shortlink"),
                                (j.get("published_on") or j.get("created_at") or "")[:10], bool(j.get("telecommuting")), ""))
            break
        r.raise_for_status()
        d = r.json()
        for j in d.get("results", []):
            loc = j.get("location") or {}
            out.append(_job(f"{company} careers", j.get("title"), company,
                            ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                            f"https://apply.workable.com/{slug}/j/{j.get('shortcode')}/", (j.get("published") or "")[:10],
                            bool(j.get("remote")) or j.get("workplace") == "remote", ""))
        token = d.get("nextPage")
        if not token:
            break
    return _q(out, query)


def teamtailor(slug_or_url, company, query=None):
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    base = _base(slug_or_url, "https://{}.teamtailor.com")
    base = re.sub(r"/jobs(\.rss)?$", "", base)
    root = ET.fromstring(_get(f"{base}/jobs.rss").content)
    out = []
    for it in root.iter("item"):
        locs = [(e.text or "").strip() for e in it.iter() if e.tag.endswith(("}city", "}name", "}country")) and (e.text or "").strip()]
        posted = ""
        try:
            posted = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        except Exception:  # noqa: BLE001
            pass
        desc = _strip_html(html.unescape(it.findtext("description") or ""))
        out.append(_job(f"{company} careers", it.findtext("title"), company, ", ".join(dict.fromkeys(filter(None, locs))),
                        it.findtext("link"), posted, "remote" in (it.findtext("remoteStatus") or desc[:300]).lower(), desc))
    return _q(out, query)


def onlyfy(slug_or_url, company, query=None):
    """onlyfy (ex Prescreen) career page https://<slug>.onlyfy.jobs (server-rendered list)."""
    base = _base(slug_or_url, "https://{}.onlyfy.jobs")
    return _html_jobs(base, company, query, href=re.compile(r"/job/|/candidate/job"))


def dvinci(slug_or_url, company, query=None):
    """d.vinci: <base>/jobPublication/list.json (base like https://x.dvinci-hr.com or https://x.dvinci-easy.com)."""
    base = _base(slug_or_url, "https://{}.dvinci-hr.com")
    base = re.sub(r"(/jobPublication.*|/de/jobs.*|/jobs.*)$", "", base)
    data = None
    for path in ("/jobPublication/list.json", "/jobs.json"):
        try:
            data = _get(base + path).json()
            break
        except Exception:  # noqa: BLE001
            continue
    if data is None:
        return _html_jobs(base + "/de/jobs", company, query)
    items = data if isinstance(data, list) else _walk(data, lambda o: o.get("position") and o.get("jobPublicationURL"), [])
    out = []
    for j in items:
        title = j.get("position") or j.get("pageTitle")
        url = j.get("jobPublicationURL") or f"{base}/de/jobs/{j.get('id')}"
        op = j.get("jobOpening") if isinstance(j.get("jobOpening"), dict) else {}
        loc = _loc([x.get("name") for x in op.get("locations") or []]) or op.get("location") or ""
        desc = _strip_html(" ".join(str(j.get(k) or "") for k in ("introduction", "tasks", "profile")))
        out.append(_job(f"{company} careers", title, company, loc, url,
                        (j.get("startDate") or op.get("createdDate") or "")[:10], "remote" in f"{title} {loc}".lower(), desc))
    return _q(out, query)


def rexx(slug_or_url, company, query=None):
    """rexx systems: https://<x>.rexx-systems.com/stellenangebote.html (detail pages ...-<id>.html / job_*.html)."""
    url = _base(slug_or_url, "https://{}.rexx-systems.com/stellenangebote.html")
    if not re.search(r"\.html?$|\?", url):
        url += "/stellenangebote.html"
    return _html_jobs(url, company, query, href=re.compile(r"(?i)stellenangebot|job|-\d+(-de)?\.html|/[\w-]+-de-[\w-]+\.html"))


def concludis(slug_or_url, company, query=None):
    """concludis job list https://<x>.concludis.de/prj/lst/ (rows are onclick="cJobboard.openJob('<detail url>')", paged)."""
    base = _base(slug_or_url, "https://{}.concludis.de/prj/lst/")
    if "/prj/" not in base:
        base += "/prj/lst/"
    out, seen = [], set()
    for page in range(1, 30):
        text = _get(base, params={"b": 0, "page": page}).text if "?" not in base else _get(base).text
        from bs4 import BeautifulSoup
        rows = []
        for el in BeautifulSoup(text, "html.parser").select("[onclick*=openJob]"):
            m = re.search(r"openJob\('([^']+)'", el["onclick"])
            t = el.select_one(".stellenlink, .headerlink, a, span")
            rows.append((m.group(1), (t or el).get_text(" ", strip=True)))
        new = [(u, t) for u, t in rows if u not in seen]
        for u, title in new:
            seen.add(u)
            out.append(_job(f"{company} careers", title, company, "", u.split("?")[0], "", "remote" in title.lower(), ""))
        if not new or "?" in base or f"page={page + 1}" not in text:
            break
    return _q(out, query)


def umantis(slug_or_url, company, query=None):
    """Abacus umantis: https://recruitingapp-XXXX.umantis.com/Jobs/All?lang=ger (slug = the XXXX number)."""
    s = slug_or_url.strip().rstrip("/")
    url = s if s.startswith("http") else f"https://recruitingapp-{s}.umantis.com/Jobs/All?lang=ger"
    if "/Jobs/" not in url and "Vacancies" not in url:
        url += "/Jobs/All?lang=ger"
    return _html_jobs(url, company, query, href=re.compile(r"(?i)/Vacancies/\d+|/Jobs/\d+|Description"))


def _bite_key(spec):
    """'customer:listing' (data-bite-jobs-api-listing) -> API key from the listing definition on cs-assets.b-ite.com."""
    customer, listing = spec.split("#")[0].split(":", 1)
    js = _get(f"https://cs-assets.b-ite.com/{customer}/jobs-api/{listing}.min.js").text
    m = re.search(r'key\s*:\s*"([0-9a-f]{20,})"', js)
    return m.group(1) if m else None


def bite(slug_or_url, company, query=None):
    """BITE: slug_or_url = API key, 'customer:listing', or a page embedding data-bite-jobs-api-listing="customer:listing"
    (or linking server-rendered .../jobposting/<hash> pages)."""
    spec = slug_or_url.strip()
    if spec.startswith("http"):
        page = _get(spec).text
        m = re.search(r'data-bite-jobs-api-listing\s*=\s*["\']([^"\']+)', page)
        if not m:
            jobs = _html_jobs(spec, company, query, href=re.compile(r"b-ite\.(com|net)|/jobposting/"), html_text=page)
            return jobs or career_page(spec, company, query)
        specs = list(dict.fromkeys(re.findall(r'data-bite-jobs-api-listing\s*=\s*["\']([^"\']+)', page)))
    else:
        specs = [spec]
    keys = []
    for sp in specs:
        try:
            k = _bite_key(sp) if ":" in sp else sp
            if k:
                keys.append(k)
        except Exception as e:  # noqa: BLE001
            log.info("bite listing %s: %s", sp, e)
    out = []
    for key in dict.fromkeys(keys):
        for off in range(0, 5000, 500):
            body = {"key": key, "channel": 0, "locale": "de", "sort": {"by": "title", "order": "asc"},
                    "page": {"num": 500, "offset": off}}
            r = requests.post("https://jobs.b-ite.com/api/v1/postings/search", json=body, timeout=30,
                              headers={"User-Agent": BROWSER_UA, "Content-Type": "application/json"})
            r.raise_for_status()
            ps = r.json().get("jobPostings", [])
            for j in ps:
                out.append(_job(f"{company} careers", j.get("title"), company, _loc(j.get("jobSite") or j.get("locations")),
                                j.get("url"), (j.get("activatedOn") or j.get("startsOn") or j.get("createdOn") or "")[:10],
                                "remote" in str(j.get("jobSite", "")).lower() or "remote" in (j.get("title") or "").lower(), ""))
            if len(ps) < 500:
                break
    return _q(out, query)


def avature(slug_or_url, company, query=None):
    """Avature: <portal>/SearchJobs RSS feed (<portal>/SearchJobs/feed/), else the HTML list (JobDetail links)."""
    import xml.etree.ElementTree as ET
    base = re.sub(r"/SearchJobs.*$", "", slug_or_url.rstrip("/"))
    out = []
    try:
        r = _get(f"{base}/SearchJobs/feed/", params={"jobRecordsPerPage": 500})
        for it in ET.fromstring(r.content).iter("item"):
            out.append(_job(f"{company} careers", it.findtext("title"), company, "", it.findtext("link"),
                            "", False, _strip_html(it.findtext("description") or "")))
    except Exception as e:  # noqa: BLE001
        log.info("avature feed %s: %s", base, e)
    seen = {o["url"] for o in out}
    for off in range(0, 3000, 50):  # the feed is capped (~20 items): page through the HTML list too
        try:
            page = _html_jobs(f"{base}/SearchJobs/?jobOffset={off}&jobRecordsPerPage=50", company, None,
                              href=re.compile(r"(?i)JobDetail"))
        except Exception as e:  # noqa: BLE001
            log.info("avature list %s: %s", base, e)
            break
        new = [j for j in page if j["url"] not in seen]
        if not new:
            break
        seen.update(j["url"] for j in new)
        out += new
    return _q(out, query)


def taleo(slug_or_url, company, query=None):
    """Oracle Taleo career section (JS-rendered): REST jobboard search, else the generic browser reader."""
    m = re.match(r"(https://[\w.-]+\.taleo\.net)/careersection/([\w-]+)", slug_or_url)
    if m:
        host, section = m.groups()
        try:
            r = requests.post(f"{host}/careersection/rest/jobboard/searchjobs", params={"lang": "de", "portal": section},
                              json={"multilineEnabled": False, "sortingSelection": {"sortBySelectionParam": "3", "ascendingSortingOrder": "false"},
                                    "fieldData": {"fields": {"KEYWORD": query or "", "LOCATION": ""}, "valid": True},
                                    "filterSelectionParam": {"searchFilterSelections": []}, "advancedSearchFiltersSelectionParam": {"searchFilterSelections": []},
                                    "pageNo": 1},
                              headers={"User-Agent": BROWSER_UA, "Content-Type": "application/json", "tz": "GMT+02:00"}, timeout=30)
            r.raise_for_status()
            out = []
            for req in r.json().get("requisitionList", []):
                cols = req.get("column") or []
                out.append(_job(f"{company} careers", cols[0] if cols else "", company, cols[1] if len(cols) > 1 else "",
                                f"{host}/careersection/{section}/jobdetail.ftl?job={req.get('contestNo') or req.get('jobId')}",
                                "", False, ""))
            if out:
                return _q(out, query)
        except Exception as e:  # noqa: BLE001
            log.info("taleo rest %s: %s", slug_or_url, e)
    return career_page(slug_or_url, company, query)


def eightfold(slug_or_url, company, query=None):
    """Eightfold: https://<host>/api/apply/v2/jobs?domain=<domain>. slug_or_url = careers URL (host) with
    ?domain=... or 'host|domain'."""
    from urllib.parse import urlparse, parse_qs
    if "|" in slug_or_url:
        host, domain = slug_or_url.split("|", 1)
    else:
        u = urlparse(slug_or_url if slug_or_url.startswith("http") else
                     f"https://{slug_or_url}" if "." in slug_or_url else f"https://{slug_or_url}.eightfold.ai")
        host = f"{u.scheme}://{u.netloc}"
        domain = (parse_qs(u.query).get("domain") or [u.netloc.split(".")[0] + ".com"])[0]
    host = host if host.startswith("http") else f"https://{host}"
    out = []
    probe = requests.get(f"{host}/api/apply/v2/jobs", params={"domain": domain, "num": 1}, timeout=30, headers={"User-Agent": BROWSER_UA})
    if probe.status_code in (403, 404):  # newer tenants: PCSX search API, 10 per page
        for start in range(0, 2000, 10):
            d = (_get(f"{host}/api/pcsx/search", params={"domain": domain, "query": query or "", "location": "", "start": start})
                 .json().get("data") or {})
            ps = d.get("positions", [])
            for p in ps:
                posted = date.fromtimestamp(p["postedTs"]).isoformat() if p.get("postedTs") else ""
                url = p.get("positionUrl") or f"/careers/job/{p.get('id')}"
                out.append(_job(f"{company} careers", p.get("name"), company, _loc(p.get("standardizedLocations") or p.get("locations")),
                                (host + url if url.startswith("/") else url) + ("" if "domain=" in url else f"?domain={domain}"),
                                posted, p.get("workLocationOption") == "remote", ""))
            if len(ps) < 10 or len(out) >= d.get("count", 10 ** 6):
                break
        return _q(out, query)
    for start in range(0, 2000, 100):
        d = _get(f"{host}/api/apply/v2/jobs", params={"domain": domain, "start": start, "num": 100, "query": query or ""}).json()
        ps = d.get("positions", [])
        for p in ps:
            posted = date.fromtimestamp(p["t_create"]).isoformat() if p.get("t_create") else ""
            out.append(_job(f"{company} careers", p.get("name"), company, p.get("location", ""),
                            p.get("canonicalPositionUrl") or f"{host}/careers?pid={p.get('id')}&domain={domain}", posted,
                            "remote" in str(p.get("work_location_option", "")).lower(), _strip_html(p.get("job_description", ""))))
        if len(ps) < 100 or len(out) >= d.get("count", 0):
            break
    return _q(out, query)


def phenom(slug_or_url, company, query=None):
    """Phenom People career site: POST <site>/widgets (refineSearch) with the refNum found in the page."""
    import json
    from urllib.parse import urlparse
    u = urlparse(slug_or_url)
    host = f"{u.scheme}://{u.netloc}"
    page = _get(slug_or_url).text
    ref = re.search(r'"refNum"\s*:\s*"([^"]+)"', page)
    lang = (re.search(r'"locale"\s*:\s*"([^"]+)"', page) or re.search(r"/([a-z]{2}/[a-z]{2})/", slug_or_url))
    locale = lang.group(1).replace("/", "_") if lang else "en_us"
    prefix = re.search(r"^(/[\w-]+/[a-z]{2})(?=/)", u.path)
    if not ref:
        return career_page(slug_or_url, company, query)
    out = []
    for frm in range(0, 2000, 100):
        body = {"lang": locale, "deviceType": "desktop", "country": locale.split("_")[-1], "pageName": "search-results",
                "ddoKey": "refineSearch", "sortBy": "", "subsearch": "", "from": frm, "jobs": True, "counts": True,
                "all_fields": [], "size": 100, "clearAll": False, "jdsource": "facets", "isSliderEnable": False,
                "pageId": "page20", "siteType": "external", "keywords": query or "", "global": True,
                "selected_fields": {}, "locationData": {}, "refNum": ref.group(1)}
        r = requests.post(f"{host}/widgets", json=body, timeout=30, headers={"User-Agent": BROWSER_UA, "Content-Type": "application/json"})
        r.raise_for_status()
        jobs = (((r.json().get("refineSearch") or {}).get("data") or {}).get("jobs")) or []
        for j in jobs:
            url = f"{host}{prefix.group(1) if prefix else ''}/job/{j.get('jobId') or j.get('jobSeqNo')}"
            out.append(_job(f"{company} careers", j.get("title"), company,
                            j.get("cityStateCountry") or j.get("location") or j.get("city", ""), url,
                            (j.get("postedDate") or j.get("dateCreated") or "")[:10], "remote" in json.dumps(j).lower()[:3000],
                            j.get("descriptionTeaser", "")))
        if len(jobs) < 100:
            break
    return _q(out, query)


def ashby(slug_or_url, company, query=None):
    slug = slug_or_url.rstrip("/").split("/")[-1]
    out = []
    for j in _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}").json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        loc = ", ".join(filter(None, [j.get("location")] + [x.get("location") for x in j.get("secondaryLocations") or []]))
        out.append(_job(f"{company} careers", j.get("title"), company, loc, j.get("jobUrl"), (j.get("publishedAt") or "")[:10],
                        bool(j.get("isRemote")), j.get("descriptionPlain", "")))
    return _q(out, query)


def jobylon(slug_or_url, company, query=None):
    """Jobylon company page (https://emp.jobylon.com/companies/<slug>/ or the company's jobylon URL)."""
    url = _base(slug_or_url, "https://emp.jobylon.com/companies/{}/")
    return _html_jobs(url, company, query, href=re.compile(r"/jobs/\d+"))


def softgarden_all(slug_or_url, company, query=None):
    """softgarden: the vacancies page, falling back to the jobs widget."""
    if slug_or_url.startswith("http"):
        return _html_jobs(slug_or_url, company, query, href=re.compile(r"/job/"))
    jobs = softgarden(slug_or_url, company, query or "")
    if not jobs:
        jobs = _html_jobs(f"https://{slug_or_url}.softgarden.io/de/widgets/jobs", company, query, href=re.compile(r"/job/"))
    return jobs


def join_all(slug_or_url, company, query=None):
    """JOIN: public API for a numeric company id, else the company page's __NEXT_DATA__."""
    s = str(slug_or_url)
    if s.isdigit():
        d = _get(f"https://join.com/api/public/companies/{s}/jobs", params={"page": 1, "pageSize": 100}).json()
        items = d.get("items", d if isinstance(d, list) else [])
        out = [_job(f"{company} careers", j.get("title"), company, _loc(j.get("city")),
                    f"https://join.com/companies/{(j.get('company') or {}).get('domain') or s}/{j.get('idParam') or j.get('id')}",
                    (j.get("createdAt") or "")[:10], j.get("workplaceType") == "REMOTE", "") for j in items]
        return _q(out, query)
    return join_com(s.rstrip("/").split("/")[-1], company, query or "")


# A career page that links/embeds a known ATS -> read that ATS directly (complete + structured).
ATS_LINKS = [
    (re.compile(r"https?://([\w-]+)\.jobs\.personio\.(?:de|com)"), "personio"),
    (re.compile(r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([\w-]+)"), "greenhouse"),
    (re.compile(r"https?://jobs\.(?:eu\.)?lever\.co/([\w-]+)"), "lever"),
    (re.compile(r"https?://([\w-]+)\.recruitee\.com"), "recruitee"),
    (re.compile(r"https?://apply\.workable\.com/([\w-]+)"), "workable"),
    (re.compile(r"https?://((?!www\.|app\.)[\w-]+)\.teamtailor\.com"), "teamtailor"),
    (re.compile(r"https?://([\w-]+)\.onlyfy\.jobs"), "onlyfy"),
    (re.compile(r"(https?://[\w-]+\.dvinci-(?:hr|easy)\.com)"), "dvinci"),
    (re.compile(r"(https?://[\w-]+\.rexx-systems\.com)"), "rexx"),
    (re.compile(r"(https?://[\w-]+\.concludis\.de/prj/lst/[^\"'\s<>]*)"), "concludis"),
    (re.compile(r"https?://recruitingapp-(\d+)(?:\.de)?\.umantis\.com"), "umantis"),
    (re.compile(r"(https?://[\w-]+\.avature\.net/(?:[a-z]{2}_[A-Z]{2}/)?\w+)/"), "avature"),
    (re.compile(r"https?://jobs\.ashbyhq\.com/([\w.-]+)"), "ashby"),
    (re.compile(r"https?://((?!www\.)[\w-]+)\.softgarden\.io"), "softgarden"),
    (re.compile(r"https?://join\.com/companies/([\w-]+)"), "join"),
    (re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)"), "smartrecruiters"),
    (re.compile(r"(https?://[\w-]+\.wd\d+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[\w-]+)"), "workday"),
]
LIST_LINK = re.compile(r"(?i)^(jobs?|stellen|karriereportal|jobportal)$|\b(offenen? stellen|stellenangebote|stellenanzeigen|"
                       r"stellenbörse|job-?börse|alle jobs|alle stellen|jobs? (finden|suchen|entdecken|ansehen)|jobsuche|"
                       r"zu den (jobs|stellen)|open (positions|jobs)|vacancies|job openings|search jobs|find jobs|view jobs|"
                       r"all jobs|see jobs|current openings|jobangebote|freie stellen|job ?finder)\b")


def _ats_from_html(text):
    found = {}
    for rx, ats in ATS_LINKS:
        for m in rx.finditer(text):
            v = m.group(1)
            if v.lower() not in ("api", "static", "assets", "cdn", "www", "embed", "app"):
                found.setdefault((ats, v), None)
    return list(found)


def career_page(url, company, query=None, timeout=30, _follow_ats=True):
    """Generic career page (own site / unknown ATS): headless Chromium loads the page, scrolls, and collects
    job-detail anchors, JSON-LD JobPostings and job arrays from XHR JSON responses. If the page links/embeds a known
    ATS, that ATS is read directly; if it only links to a job list ("Stellenangebote", "Alle Jobs"), that is followed
    once. Graceful: [] on failure."""
    from urllib.parse import urljoin, urlparse
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("career_page: playwright not installed")
        return []
    xhr_jobs = []

    def on_response(resp):
        try:
            if "json" not in (resp.headers.get("content-type") or "") or resp.request.resource_type not in ("xhr", "fetch"):
                return
            data = resp.json()
        except Exception:  # noqa: BLE001
            return
        title_keys = ("title", "jobTitle", "name", "position", "positionTitle", "job_title")
        for o in _walk(data, lambda o: any(isinstance(o.get(k), str) and JOBISH_TITLE.search(o.get(k)) for k in title_keys), []):
            title = next(o[k] for k in title_keys if isinstance(o.get(k), str) and JOBISH_TITLE.search(o[k]))
            link = next((o[k] for k in ("url", "absolute_url", "jobUrl", "applyUrl", "detailUrl", "link", "href",
                                        "canonicalPositionUrl", "externalPath", "jobPublicationURL", "slug") if isinstance(o.get(k), str)), "")
            if not link or len(title) > 160:
                continue
            xhr_jobs.append(_job(f"{company} careers", title, company,
                                 _loc(o.get("location") or o.get("locations") or o.get("city") or o.get("locationsText")),
                                 urljoin(page_url[0], link), str(o.get("postedDate") or o.get("datePosted") or o.get("published") or "")[:10],
                                 "remote" in title.lower(), ""))

    def settle(page):
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        for sel in ("#onetrust-accept-btn-handler", "#uc-btn-accept-banner", "button:has-text('Alle akzeptieren')",
                    "button:has-text('Accept all')", "button:has-text('Akzeptieren')", "button:has-text('Zustimmen')"):
            try:
                if page.locator(sel).first.is_visible(timeout=300):
                    page.locator(sel).first.click(timeout=2000)
                    break
            except Exception:  # noqa: BLE001
                pass
        for _ in range(6):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(600)
            for sel in ("button:has-text('Mehr laden')", "button:has-text('Load more')", "button:has-text('Weitere Jobs')",
                        "button:has-text('Mehr anzeigen')", "button:has-text('Show more')", "a:has-text('Mehr laden')"):
                try:
                    if page.locator(sel).first.is_visible(timeout=200):
                        page.locator(sel).first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                except Exception:  # noqa: BLE001
                    pass

    def harvest(page):
        jobs, texts = [], [page.content()]
        for fr in page.frames[1:]:  # embedded ATS widgets (iframes)
            try:
                t = fr.content()
                texts.append(fr.url + " " + t)
                jobs += _html_jobs(fr.url, company, None, html_text=t)
            except Exception:  # noqa: BLE001
                pass
        jobs += _html_jobs(page.url, company, None, html_text=texts[0])
        return jobs, " ".join(texts)

    jobs, blob, page_url = [], "", [url]
    try:
        with sync_playwright() as p:
            kw = {"headless": True}
            if os.path.exists(CHROMIUM):
                kw["executable_path"] = CHROMIUM
            browser = p.chromium.launch(**kw)
            try:
                page = browser.new_page(user_agent=BROWSER_UA, locale="de-DE")
                page.set_default_timeout(timeout * 1000)
                page.on("response", on_response)
                page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
                settle(page)
                page_url[0] = page.url
                jobs, blob = harvest(page)
                if len(jobs) + len(xhr_jobs) < 5 and not _ats_from_html(blob):  # landing page: follow "Stellenangebote"
                    host = urlparse(page.url).netloc.split(".")[-2:]
                    best = None
                    for a in page.locator("a[href]").all()[:400]:
                        try:
                            t = re.sub(r"\s+", " ", a.inner_text(timeout=300)).strip()
                            h = urljoin(page.url, a.get_attribute("href") or "")
                        except Exception:  # noqa: BLE001
                            continue
                        if len(t) <= 45 and LIST_LINK.search(t) and h.startswith("http") and h.rstrip("/") != page.url.rstrip("/") \
                                and not re.search(r"(?i)apply|bewerb|initiativ|login", h):
                            score = (urlparse(h).netloc.split(".")[-2:] == host) + bool(re.search(r"(?i)stellen|jobs|vacanc|position", h))
                            if best is None or score > best[0]:
                                best = (score, h)
                    if best:
                        log.info("career_page %s -> %s", url, best[1])
                        page.goto(best[1], timeout=timeout * 1000, wait_until="domcontentloaded")
                        settle(page)
                        page_url[0] = page.url
                        j2, b2 = harvest(page)
                        jobs += j2
                        blob += " " + page.url + " " + b2
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001
        log.warning("career_page %s failed: %s", url, e)
    if _follow_ats:
        for ats, target in _ats_from_html(blob)[:3]:
            try:
                reader = ATS_READERS.get(ats)
                if ats == "smartrecruiters":
                    jobs += smartrecruiters(target, company, query or "")
                elif ats == "workday":
                    for q in SEARCH_TERMS:
                        jobs += workday_search(target, q, company)
                elif reader and reader is not career_page:
                    jobs += reader(target, company)
            except Exception as e:  # noqa: BLE001
                log.info("career_page %s: %s %s failed: %s", url, ats, target, e)
    jobs += xhr_jobs
    if not jobs:
        log.info("career_page %s: no jobs found", url)
    return _q(jobs, query)


def successfactors_rmk(slug_or_url, company, query=None):
    """SAP SuccessFactors Recruiting Marketing (RMK) site: every job URL from /sitemap.xml (title from the URL),
    falling back to the server-rendered /search/ list."""
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote, urlparse
    base = re.sub(r"/sitemap\.xml$", "", slug_or_url.rstrip("/"))
    u = urlparse(base if base.startswith("http") else f"https://{base}")
    base = f"{u.scheme}://{u.netloc}"
    out, maps = [], [f"{base}/sitemap.xml"]
    for sm in maps[:10]:
        try:
            root = ET.fromstring(_get(sm).content)
        except Exception as e:  # noqa: BLE001
            log.info("rmk sitemap %s: %s", sm, e)
            continue
        for loc in root.iter():
            if not loc.tag.endswith("loc") or not loc.text:
                continue
            link = loc.text.strip()
            if link.endswith(".xml") and len(maps) < 10:
                maps.append(link)
                continue
            m = re.search(r"/job/([^/]+)/(\d+)/?$", link)
            if m:
                title = unquote(m.group(1)).replace("-", " ")
                out.append(_job(f"{company} careers", title, company, "", link, "", "remote" in title.lower(), ""))
    if not out:
        out = successfactors_search(base, "", company)
    return _q(out, query)


def oracle_orc(slug_or_url, company, query=None):
    """Oracle Recruiting Cloud (CandidateExperience): REST recruitingCEJobRequisitions; needs siteNumber in the URL
    (.../sites/<siteNumber> or siteNumber=<x>), otherwise the generic browser reader."""
    m = re.search(r"(https://[\w.-]+oraclecloud\.com)", slug_or_url)
    site = re.search(r"siteNumber=([\w-]+)|/sites/([\w-]+)", slug_or_url)
    if not (m and site):
        return career_page(slug_or_url, company, query)
    host, site = m.group(1), site.group(1) or site.group(2)
    out = []
    for off in range(0, 2000, 200):
        r = _get(f"{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions",
                 params={"onlyData": "true", "expand": "requisitionList",
                         "finder": f"findReqs;siteNumber={site},limit=200,offset={off},sortBy=POSTING_DATES_DESC"})
        items = r.json().get("items") or [{}]
        reqs = items[0].get("requisitionList") or []
        for j in reqs:
            out.append(_job(f"{company} careers", j.get("Title"), company, j.get("PrimaryLocation", ""),
                            f"{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j.get('Id')}",
                            (j.get("PostedDate") or "")[:10], "remote" in str(j.get("WorkplaceType", "")).lower(),
                            j.get("ShortDescriptionStr") or ""))
        if len(reqs) < 200:
            break
    return _q(out, query)


ATS_READERS = {
    "personio": personio, "greenhouse": greenhouse, "lever": lever, "recruitee": recruitee, "workable": workable,
    "teamtailor": teamtailor, "onlyfy": onlyfy, "prescreen": onlyfy, "dvinci": dvinci, "rexx": rexx,
    "concludis": concludis, "umantis": umantis, "bite": bite, "avature": avature, "taleo": taleo,
    "eightfold": eightfold, "phenom": phenom, "ashby": ashby, "jobylon": jobylon, "softgarden": softgarden_all,
    "join": join_all, "own": career_page, "unknown": career_page, "custom": career_page,
    "successfactors_rmk": successfactors_rmk, "oracle_orc": oracle_orc, "oracle": oracle_orc, "b-ite": bite,
    "job-shop": career_page, "mhm_erecruiter": career_page, "icims": career_page, "cornerstone": career_page,
}
