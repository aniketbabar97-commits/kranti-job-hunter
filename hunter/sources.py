"""Job sources. Each returns a list of normalized job dicts."""
import logging
import time

import requests

log = logging.getLogger(__name__)

AA_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
AA_HEADERS = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": "Jobsuche/2.9.2"}


def _job(source, title, company, location, url, posted="", remote=False, description="", salary=""):
    return {
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


def arbeitsagentur(query, days=2, max_pages=3):
    """Federal employment agency (Bundesagentur für Arbeit) - all of Germany."""
    jobs = []
    for page in range(1, max_pages + 1):
        params = {"was": query, "veroeffentlichtseit": days, "size": 100, "page": page, "angebotsart": 1}
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
        ))
    return jobs
