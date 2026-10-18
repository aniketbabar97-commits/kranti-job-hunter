"""Kits for strong jobs that need a website form (no application email), so the Windows helper has work.

Runs as part of every job hunt (a few per run) and on demand: python -m hunter.formkits [max]
Jobs are taken from data/jobs_log.csv (last 45 days, score 60+, best first), skipping jobs that already have a
kit, an email application, or an APPLIED.md entry. The posting text is fetched first so the letter is specific.
"""
import csv
import html
import json
import logging
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

from . import applied, kit, outreach, sources

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def linkedin_details(job):
    """Public (logged-out) job page: posting text. Returns False if the job is closed."""
    m = re.search(r"(\d{8,})", job["url"])
    if not m:
        return True
    r = requests.get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}", headers=UA, timeout=20)
    if r.status_code == 404 or "No longer accepting applications" in r.text:
        return False
    body = re.search(r'class="show-more-less-html__markup[^"]*">(.*?)</div>', r.text, re.S)
    if body:
        job["description"] = html.unescape(re.sub(r"<[^>]+>", " ", body.group(1)))[:4000]
    return True


def candidates(days=45, min_score=60):
    data = applied.load()
    ledger_urls = {v["url"] for v in outreach.load().values()}
    have_kit = set()
    for f in (ROOT / "applications").glob("*.json"):
        have_kit.add(json.loads(f.read_text(encoding="utf-8"))["job"]["url"])
    since = (date.today() - timedelta(days=days)).isoformat()
    rows, urls = [], set()
    with open(ROOT / "data" / "jobs_log.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["url"] in urls or r["found"] < since or int(r["score"] or 0) < min_score:
                continue
            urls.add(r["url"])
            if r["url"] in have_kit or r["url"] in ledger_urls:
                continue
            job = {**r, "score": int(r["score"]), "remote": r["remote"] == "True", "contact": "", "description": "",
                   "salary": ""}
            if applied.status(job, data) == "applied":
                continue
            rows.append(job)
    return sorted(rows, key=lambda j: (-j["score"], j["found"]))


def run(limit=15):
    master_cv = (ROOT / "cv.md").read_text(encoding="utf-8")
    jobs = []
    for job in candidates():
        if len(jobs) >= limit:
            break
        try:
            if job["source"] == "Arbeitsagentur":
                sources.arbeitsagentur_details(job)
                if not job["description"]:
                    continue  # closed
                if outreach.pick_email(job):
                    continue  # applied to by email instead
            elif "linkedin.com/jobs/view" in job["url"]:
                if not linkedin_details(job):
                    continue
        except Exception as ex:
            log.info("details for %s failed (%s); using title only", job["title"], ex)
        jobs.append(job)
    log.info("form kits: %d jobs", len(jobs))
    saved_max = kit.MAX_PER_RUN
    kit.MAX_PER_RUN = limit
    try:
        kit.make_kits(jobs, master_cv, force=True)
    finally:
        kit.MAX_PER_RUN = saved_max
    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
