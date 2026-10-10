"""Run all searches, keep new relevant jobs, score them, email the digest."""
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import digest, score, sources

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "seen.json"
LOG = ROOT / "data" / "jobs_log.csv"
PREVIEW = ROOT / "data" / "last_digest.html"
log = logging.getLogger("hunter")


def key(job):
    """Same job posted on several boards -> one key (title + company, gender tags stripped)."""
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
            log.warning("%s %r failed: %s", name, args[0], e)
            health[name] = (n, str(e)[:150])

    days = max(1, cfg["hours_old"] // 24)
    for q in cfg["queries"]:
        log.info("query: %s", q)
        run("Arbeitsagentur", sources.arbeitsagentur, q, days)
        for loc in cfg["locations"]:
            run("LinkedIn/Indeed (Germany)", sources.jobspy, q, loc, cfg["hours_old"], cfg["results_per_query"])
        run("LinkedIn/Indeed (remote EU)", sources.jobspy, q, cfg["remote_location"], cfg["hours_old"],
            cfg["results_per_query"], True)
        time.sleep(3)
    if os.getenv("SERPER_API_KEY"):
        for q in cfg.get("post_queries", []):
            run("LinkedIn posts (Google)", sources.linkedin_posts, q, days)
    else:
        health["LinkedIn posts (Google)"] = (0, "off - add SERPER_API_KEY secret to enable")
    return jobs, health


def relevant(job, cfg):
    title = job["title"].lower()
    if any(t in title for t in cfg["exclude_title_terms"]):
        return False
    text = f"{title} {job['description'].lower()}"
    return any(re.search(rf"\b{re.escape(t)}\b", text) for t in cfg["relevance_terms"])


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if os.getenv("TEST_EMAIL"):
        label = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%a %d %b %Y, %H:%M")
        ok = digest.send(f"✅ Job hunter test email — {label}",
                         "<p>This is a test email from the job hunter. If you can read this, email delivery works.</p>")
        sys.exit(0 if ok else 1)
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    if os.getenv("QUERY_LIMIT"):  # for quick local tests
        cfg["queries"] = cfg["queries"][: int(os.environ["QUERY_LIMIT"])]
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

    label = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%a %d %b %Y, %H:%M")
    body = digest.build_html(jobs, health, label)
    PREVIEW.parent.mkdir(exist_ok=True)
    PREVIEW.write_text(body)
    if os.getenv("DRY_RUN"):
        log.info("DRY_RUN: not emailing, not updating seen list")
        return
    top = sum(1 for j in jobs if j["score"] >= 80)
    subject = f"🎯 {len(jobs)} new jobs ({top} strong) — {label}" if jobs else f"No new jobs — {label}"
    if not digest.send(subject, body):
        log.error("Email not sent; seen list left unchanged so jobs show up next run")
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
