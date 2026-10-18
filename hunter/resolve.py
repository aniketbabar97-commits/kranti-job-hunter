"""Find every job's real application form + applicant-tracking system (ATS).

resolve(job) -> {"form_url", "ats", "needs_login", "captcha", "status": ok|closed|unknown, "doors": [...]}
`python3 -m hunter.resolve` updates all application kits (applications/*.json) in place.
"""
import base64
import html
import json
import logging
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("hunter.resolve")

AA_HEADERS = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "Jobsuche/2.9.2"}
# Only v4 jobdetails answers (v5/v6 jobdetails -> 403); v6 is the search endpoint.
AA_DETAILS = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0 Safari/537.36",
           "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}
SLEEP = 0.7

DOOR_ORDER = ["own", "personio", "join", "softgarden", "recruitee", "workable", "teamtailor", "greenhouse", "lever",
              "smartrecruiters", "concludis", "dvinci", "rexx", "onlyfy", "bite", "umantis", "successfactors",
              "workday", "arbeitsagentur", "indeed", "linkedin", "stepstone", "xing", "board", "unknown"]
BOARDS = {"arbeitsagentur", "indeed", "linkedin", "stepstone", "xing", "board", "unknown"}

ATS_RULES = [  # (ats, regex on host+path)
    ("personio", r"\.jobs\.personio\.(de|com)|personio\.(de|com)/job"),
    ("join", r"(^|\.)join\.com"),
    ("softgarden", r"softgarden\.(io|de)"),
    ("smartrecruiters", r"smartrecruiters\.com|jobs\.sap\.com|careers\.sap\.com"),
    ("workday", r"myworkdayjobs\.com|myworkdaysite\.com|\.wd\d+\."),
    ("successfactors", r"successfactors\.(com|eu)|sapsf\.(com|eu)|career\d*\.sap|/career\?company="),
    ("greenhouse", r"greenhouse\.io"),
    ("lever", r"lever\.co"),
    ("recruitee", r"recruitee\.com"),
    ("workable", r"workable\.com"),
    ("teamtailor", r"teamtailor\.com"),
    ("concludis", r"concludis\.(de|com)"),
    ("dvinci", r"dvinci(-hr)?\.(de|com)|dvinci-easy"),
    ("rexx", r"rexx-systems\.com|rexx-recruitment|/jobs/[^/]*-\d+\.html?.*rexx"),
    ("onlyfy", r"onlyfy\.(jobs|io)|prescreen\.io"),
    ("bite", r"b-ite\.(de|com)|bite\.(de|io)/"),
    ("umantis", r"umantis\.com"),
    ("taleo", r"taleo\.net"),
    ("icims", r"icims\.com"),
    ("arbeitsagentur", r"arbeitsagentur\.de"),
    ("indeed", r"indeed\.(com|de)"),
    ("linkedin", r"linkedin\.com"),
    ("stepstone", r"stepstone\.(de|com)"),
    ("xing", r"xing\.com"),
    ("board", r"jobware\.de|heyjobs\.(co|de)|get-in-it\.de|finest-jobs\.com|monster\.(de|com)|glassdoor\.|"
              r"kimeta\.de|jobvector\.de|stellenanzeigen\.de|meinestadt\.de|fashionunited\.|jooble\.|"
              r"careerjet\.|talent\.com|jobleads\.|absolventa\.de|yourfirm\.de|jobs\.de|experteer\.|"
              r"freelancermap\.|gulp\.de|hays\.de|jobted\.|stellenonline\.|karriere\.at|jobs\.ch|"
              r"bundesagentur|ziprecruiter|simplyhired|adzuna\.|google\.com"),
]
NEEDS_LOGIN = {"workday", "successfactors", "taleo", "icims"}
CAPTCHA = re.compile(r"recaptcha|hcaptcha|h-captcha|challenges\.cloudflare\.com/turnstile|cf-turnstile", re.I)
CLOSED = re.compile(r"nicht mehr verfügbar|nicht mehr verfuegbar|no longer (available|accepting|active|open)|"
                    r"bereits besetzt|position has been filled|job (has )?expired|posting (has )?expired|"
                    r"stelle ist (leider )?(nicht mehr|bereits)|this job is closed", re.I)
FOREIGN = re.compile(r"\b(ital|india|indien|vietnam|poland|polska|spain|españa|france|romania|portugal|"
                     r"hungary|czech|united states|usa|uk\b|united kingdom|milan|milano|roma|torino|bangalore|"
                     r"hyderabad|pune|warsaw|kraków|krakow|ho chi minh|madrid|barcelona|paris|lisbon)", re.I)
STOP = {"gmbh", "ag", "se", "kg", "co", "mbh", "ltd", "inc", "llc", "group", "gruppe", "deutschland", "germany",
        "holding", "the", "und", "and", "der", "die", "das", "consulting", "services", "solutions", "digital",
        "technology", "technologies", "international", "europe", "software", "systems", "it"}


def classify(url, company=""):
    """ATS name from a URL's host/path; 'own' when the host carries a token of the company name."""
    if not url:
        return "unknown"
    p = urlparse(url)
    hp = (p.netloc + p.path + ("?" + p.query if p.query else "")).lower()
    for ats, rx in ATS_RULES:
        if re.search(rx, hp):
            return ats
    host = p.netloc.lower()
    toks = [t for t in re.split(r"[^a-z0-9]+", (company or "").lower()) if len(t) >= 3 and t not in STOP]
    if any(t in host.replace("-", "") for t in toks):
        return "own"
    return "own" if re.search(r"(karriere|career|jobs?)\.", host) or re.search(r"/(karriere|career|jobs?)", p.path.lower()) \
        else "unknown"


def _get(url, headers=None, **kw):
    """GET with ≤5 redirects and one 429 backoff; returns Response or None."""
    for attempt in range(3):
        try:
            s = requests.Session()
            s.max_redirects = 5
            r = s.get(url, headers=headers or BROWSER, timeout=20, allow_redirects=True, **kw)
        except requests.RequestException as ex:
            log.debug("GET %s failed: %s", url, ex)
            return None
        finally:
            time.sleep(SLEEP)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", "0") or 0) or 10 * (attempt + 1))
            continue
        return r
    return None


def _door(url, company="", source_ats=None):
    return {"url": url, "ats": source_ats or classify(url, company)}


def _workday_closed(url):
    """Workday: /<locale>/<site>/job/<loc>/<slug> -> /wday/cxs/<tenant>/<site>/job/<loc>/<slug>."""
    p = urlparse(url)
    tenant = p.netloc.split(".")[0]
    parts = [x for x in p.path.split("/") if x]
    if parts and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]):
        parts = parts[1:]
    if "job" not in parts:
        return None
    i = parts.index("job")
    api = f"{p.scheme}://{p.netloc}/wday/cxs/{tenant}/{parts[i - 1] if i else ''}/job/{'/'.join(parts[i + 1:])}"
    r = _get(api, {**BROWSER, "Accept": "application/json"})
    if r is None:
        return None
    if r.status_code in (404, 410):
        return True
    try:
        info = r.json().get("jobPostingInfo") or {}
        return bool(info.get("endDate") and not info.get("canApply", True)) or info.get("canApply") is False
    except ValueError:
        return None


def probe(url, company=""):
    """Visit a form URL: final URL, ats, captcha, status."""
    r = _get(url)
    if r is None:
        return {"url": url, "ats": classify(url, company), "captcha": False, "status": "unknown"}
    final = r.url
    ats = classify(final, company)
    if ats == "unknown":
        ats = classify(url, company)
    text = r.text[:400000] if "html" in r.headers.get("Content-Type", "html") else ""
    if r.status_code in (404, 410):
        status = "closed"
    elif r.status_code >= 400:
        status = "unknown"
    elif CLOSED.search(text):
        status = "closed"
    else:
        status = "ok"
    if ats == "workday" and status != "closed":
        c = _workday_closed(final)
        if c:
            status = "closed"
    if ats == "own" and status == "ok":  # career site may embed a known ATS
        for name, rx in ATS_RULES[:18]:
            if re.search(r"(https?://[^\"' ]*(" + rx + r")[^\"' ]*)", text, re.I) and name not in NEEDS_LOGIN:
                m = re.search(r"https?://[^\"'\s<>]*(?:" + rx + r")[^\"'\s<>]*", text, re.I)
                if m and "job" in m.group(0).lower():
                    return {"url": final, "ats": "own", "captcha": bool(CAPTCHA.search(text)), "status": status,
                            "embedded": {"url": html.unescape(m.group(0)), "ats": name}}
                break
    return {"url": final, "ats": ats, "captcha": bool(CAPTCHA.search(text)), "status": status}


def _arbeitsagentur(job, doors):
    ref = job["url"].rstrip("/").split("/")[-1].split("?")[0]
    r = _get(AA_DETAILS + base64.b64encode(ref.encode()).decode(), AA_HEADERS)
    if r is None:
        return "unknown"
    if r.status_code in (404, 410):
        doors.append(_door(job["url"], source_ats="arbeitsagentur"))
        return "closed"
    if r.status_code != 200:
        return "unknown"
    d = r.json()
    for k in ("externeUrl", "allianzpartnerUrl"):
        if d.get(k):
            u = d[k] if d[k].startswith("http") else "https://" + d[k]
            if "arbeitsagentur.de" not in urlparse(u).netloc:
                doors.append(_door(u, job.get("company", "")))
    doors.append(_door(job["url"], source_ats="arbeitsagentur"))
    return "ok"


def _linkedin(job, doors):
    m = re.search(r"/jobs/view/(?:[^/]*-)?(\d{6,})", job["url"]) or re.search(r"currentJobId=(\d+)", job["url"])
    if not m:
        doors.append(_door(job["url"], source_ats="linkedin"))
        return "unknown"
    r = _get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}")
    doors.append(_door(f"https://www.linkedin.com/jobs/view/{m.group(1)}", source_ats="linkedin"))
    if r is None or r.status_code >= 400:
        return "closed" if r is not None and r.status_code in (404, 410) else "unknown"
    if re.search(r"No longer accepting applications", r.text, re.I):
        return "closed"
    e = re.search(r'externalApply[^"]*?url=([^"&]+)', r.text) or \
        re.search(r'id="applyUrl"[^>]*>\s*<!--\s*"([^"]+)"', r.text)
    if e:
        u = unquote(html.unescape(e.group(1)))
        if "url=" in u and "linkedin.com" in urlparse(u).netloc:
            u = unquote(u.split("url=", 1)[1].split("&")[0])
        doors.insert(0, _door(u, job.get("company", "")))
    return "ok"


def _indeed(job, doors):
    m = re.search(r"jk=([0-9a-f]+)", job["url"])
    url = f"https://de.indeed.com/viewjob?jk={m.group(1)}" if m else job["url"]
    doors.append(_door(url, source_ats="indeed"))
    r = _get(url)
    if r is not None and r.status_code in (404, 410):
        return "closed"
    if r is None or r.status_code >= 400 or "captcha" in r.url.lower():
        return "unknown"  # Indeed blocks non-browser clients
    if CLOSED.search(r.text[:300000]) or "expired" in r.url:
        return "closed"
    e = re.search(r'"(?:applyUrl|thirdPartyApplyUrl|companyApplyUrl)"\s*:\s*"([^"]+)"', r.text) or \
        re.search(r'href="(https://de\.indeed\.com/applystart[^"]+)"', r.text)
    if e:
        u = html.unescape(e.group(1).encode().decode("unicode_escape", "ignore"))
        doors.insert(0, _door(u, job.get("company", "")))
    return "ok"


def choose_door(doors):
    if not doors:
        return None
    return min(doors, key=lambda d: DOOR_ORDER.index(d["ats"]) if d["ats"] in DOOR_ORDER else len(DOOR_ORDER))


def resolve(job):
    doors, url, company = [], job.get("url") or "", job.get("company", "")
    host = urlparse(url).netloc.lower()
    if "arbeitsagentur" in host:
        status = _arbeitsagentur(job, doors)
    elif "linkedin.com" in host and "/jobs/" in url:
        status = _linkedin(job, doors)
    elif "indeed." in host:
        status = _indeed(job, doors)
    elif url:
        doors.append(_door(url, company))
        status = "unknown"
    else:
        status = "unknown"
    # Follow every non-board door to its real final URL.
    captcha, probed = False, []
    for d in list(doors):
        if d["ats"] in {"arbeitsagentur", "linkedin", "indeed"}:
            continue
        p = probe(d["url"], company)
        d.update({"url": p["url"], "ats": p["ats"] if p["ats"] != "unknown" else d["ats"], "status": p["status"]})
        if p.get("embedded"):
            doors.append({**p["embedded"], "status": "ok"})
        captcha = captcha or p["captcha"]
        probed.append(p["status"])
    if probed and status != "closed":
        if "ok" in probed:
            status = "ok"
        elif all(s == "closed" for s in probed) and status == "unknown":
            status = "closed"  # the only real door is gone (board said nothing either way)
    live = [d for d in doors if d.get("status") != "closed"] or doors
    best = choose_door(live)
    return {"form_url": best["url"] if best else url, "ats": best["ats"] if best else "unknown",
            "needs_login": bool(best and best["ats"] in NEEDS_LOGIN), "captcha": captcha,
            "status": status, "doors": doors}


def _is_foreign(job):
    return bool(FOREIGN.search(job.get("location") or "")) and not job.get("remote")


def resolve_kits(paths=None):
    paths = paths or sorted((ROOT / "applications").glob("*.json"))
    stats, fails, examples = Counter(), [], []
    for f in paths:
        try:
            kit = json.loads(f.read_text(encoding="utf-8"))
        except Exception as ex:
            fails.append((f.name, f"unreadable: {ex}"))
            continue
        job = kit.get("job") or {}
        if kit.get("skip") or not job.get("url"):
            continue
        if _is_foreign(job):
            stats[("foreign", "left")] += 1
            continue
        try:
            res = resolve(job)
        except Exception as ex:
            fails.append((f.name, str(ex)[:150]))
            continue
        direct = job.get("direct_url") or ""
        if direct and classify(direct, job.get("company", "")) not in BOARDS and res["ats"] in BOARDS:
            res["form_url"], res["ats"] = direct, classify(direct, job.get("company", ""))
            res["needs_login"] = res["ats"] in NEEDS_LOGIN
        job.update({"form_url": res["form_url"], "ats": res["ats"], "needs_login": res["needs_login"],
                    "captcha": res["captcha"], "resolve_status": res["status"]})
        if res["status"] == "closed":
            kit["skip"] = "closed"
        kit["job"] = job
        f.write_text(json.dumps(kit, ensure_ascii=False, indent=2), encoding="utf-8")
        stats[(res["ats"], res["status"])] += 1
        if res["ats"] not in BOARDS and len(examples) < 10:
            examples.append(f"{res['ats']:<15} {res['form_url']}")
        print(f"  {res['status']:<7} {res['ats']:<15} {job.get('company', '')[:30]:<30} {res['form_url'][:90]}",
              flush=True)
    by_ats, by_status = Counter(), Counter()
    for (a, s), n in stats.items():
        by_ats[a] += n
        by_status[s] += n
    print("\nby ats:", dict(by_ats.most_common()))
    print("by status:", dict(by_status.most_common()))
    print("examples:\n  " + "\n  ".join(examples))
    if fails:
        print("failures:", *fails, sep="\n  ")
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    resolve_kits([Path(a) for a in sys.argv[1:]] or None)
