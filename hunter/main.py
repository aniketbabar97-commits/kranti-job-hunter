"""Run all searches, keep new relevant jobs, score them, email the digest."""
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import digest, score, sources

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "seen.json"
LOG = ROOT / "data" / "jobs_log.csv"
PREVIEW = ROOT / "data" / "last_digest.html"
log = logging.getLogger("hunter")


def key(job):
    norm = lambda s: re.sub(r"\(.*?\)|[^a-z0-9]", "", s.lower())
    return f"{norm(job['title'])}|{norm(job['company'])}"


def collect(cfg):
    jobs, health = [], {}

    def run(name, fn, *args):
        n, err = health.get(name, (0, ""))
        try:
            found = fn(*args)
            jobs.extend(found)
            health[name] = (n + len(found), err)
        except Exception as e:
            log.warning("%s %s failed: %s", name, args[0], e)
            health[name] = (n, str(e)[:120])

    days = max(1, cfg["hours_old"] // 24)
    for q in cfg["queries"]:
        run("Arbeitsagentur", sources.arbeitsagentur, q, days)
        for loc in cfg["locations"]:
            run("LinkedIn/Indeed/Google (Germany)", sources.jobspy, q, loc, cfg["hours_old"], cfg["results_per_query"])
        run("LinkedIn/Indeed/Google (remote EU)", sources.jobspy, q, cfg["remote_location"], cfg["hours_old"],
            cfg["results_per_query"], True)
        time.sleep(2)
    return jobs, health


def relevant(job, cfg):
    title = job["title"].lower()
    text = f"{title} {job['description'].lower()}"
    if any(t in title for t in cfg["exclude_title_terms"]):
        return False
    return any(t in text for t in cfg["relevance_terms"])


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cv = (ROOT / "cv.md").read_text()
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}

    raw, health = collect(cfg)
    new = {}
    for j in raw:
        k = key(j)
        if j["title"] and k not in seen and k not in new and relevant(j, cfg):
            new[k] = j
    jobs = list(new.values())
    log.info("raw=%d new_relevant=%d", len(raw), len(jobs))

    score.score_jobs(jobs, cv)
    jobs = sorted((j for j in jobs if j["score"] >= cfg["min_score_in_digest"]), key=lambda j: -j["score"])
    digest.assign_sections(jobs)

    now = datetime.now(timezone(timedelta(hours=2)))
    label = now.strftime("%a %d %b %Y, %H:%M")
    body = digest.build_html(jobs, health, label)
    PREVIEW.write_text(body)
    top = sum(1 for j in jobs if j["score"] >= 80)
    if jobs and not os.getenv("DRY_RUN"):
        if not digest.send(f"🎯 {len(jobs)} new jobs ({top} strong) — {label}", body):
            log.error("Email not sent")
            sys.exit(1)

    today = date.today().isoformat()
    for k in new:
        seen[k] = today
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    SEEN.write_text(json.dumps({k: v for k, v in seen.items() if v >= cutoff}, indent=0, sort_keys=True))
    write_header = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["found", "score", "title", "company", "location", "remote", "source", "url", "why"])
        for j in jobs:
            w.writerow([today, j["score"], j["title"], j["company"], j["location"], j["remote"], j["source"], j["url"], j["why"]])


if __name__ == "__main__":
    main()
