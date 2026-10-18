"""Run all searches, keep new relevant jobs, score them, email the digest."""
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

from . import applied, digest, inbox, kit, outreach, report, rules, score, sources, weekly

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "seen.json"
PREVIEW = ROOT / "data" / "last_digest.html"
log = logging.getLogger("hunter")


LEGAL_FORMS = re.compile(r"\b(gmbh|ag|se|kg|co|mbh|ltd|inc|llc|group|gruppe|deutschland|germany|industries|holding)\b")


def key(job):
    """Same job posted on several boards -> one key: title (gender tags stripped) + core company name."""
    norm = lambda s: re.sub(r"\(.*?\)|[^a-z0-9]", "", s.lower())
    company = LEGAL_FORMS.sub("", job["company"].lower())
    return f"{norm(job['title'])}|{norm(company)}"


def legacy_key(job):
    """Key format used before 2026-10-14; still checked so already-sent jobs are not re-sent."""
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
    for entry in cfg.get("companies", []):
        run("Company career sites (direct)", sources.company_feed, entry)
    if os.getenv("SERPER_API_KEY"):
        for q in cfg.get("post_queries", []):
            run("LinkedIn posts (Google)", sources.linkedin_posts, q, days)
        if first_run_today():
            for q in cfg.get("career_site_queries", []):
                run("Career sites (Google)", sources.career_sites, q, 30)
    else:
        health["LinkedIn posts (Google)"] = (0, "off - add SERPER_API_KEY secret to enable")
    return jobs, health


RUN_STATE = ROOT / "data" / "last_career_search.txt"


def first_run_today():
    """Career-site searches cost Serper credits, so only the first run of each day does them."""
    today = date.today().isoformat()
    if RUN_STATE.exists() and RUN_STATE.read_text(encoding="utf-8").strip() == today and not os.getenv("FORCE_CAREER_SEARCH"):
        return False
    RUN_STATE.write_text(today, encoding="utf-8")
    return True


def relevant(job, cfg):
    title = job["title"].lower()
    if any(t in title for t in cfg["exclude_title_terms"]):
        return False
    if job["source"].endswith(" careers"):
        # Whole company feeds: e-commerce companies mention "e-commerce" in every ad, so require the
        # term in the title, or a core SAP Commerce term anywhere.
        return any(re.search(rf"\b{re.escape(t)}\b", title) for t in cfg["relevance_terms"]) \
            or bool(rules.COMMERCE_CORE.search(job["description"]))
    text = f"{title} {job['description'].lower()}"
    return any(re.search(rf"\b{re.escape(t)}\b", text) for t in cfg["relevance_terms"])


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if os.getenv("TEST_EMAIL"):
        label = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%a %d %b %Y, %H:%M")
        ok = digest.send(f"✅ Job hunter test email — {label}",
                         "<p>This is a test email from the job hunter. If you can read this, email delivery works.</p>")
        sys.exit(0 if ok else 1)
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    if os.getenv("QUERY_LIMIT"):  # for quick local tests
        cfg["queries"] = cfg["queries"][: int(os.environ["QUERY_LIMIT"])]
    cv = (ROOT / "cv.md").read_text(encoding="utf-8")
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}

    raw, health = collect(cfg)
    new = {}
    for j in raw:
        k = key(j)
        if j["title"] and k not in seen and legacy_key(j) not in seen and k not in new and relevant(j, cfg):
            new[k] = j
    jobs = list(new.values())
    log.info("raw=%d new_relevant=%d", len(raw), len(jobs))
    for src, (n, err) in health.items():
        log.info("source %s: %d results %s", src, n, err)

    for j in jobs:  # full text + application email; the search API only returns occupation names
        if j["source"] == "Arbeitsagentur":
            try:
                sources.arbeitsagentur_details(j)
            except Exception as ex:
                log.warning("Arbeitsagentur details for %s failed: %s", j["title"], ex)
    score.score_jobs(jobs, cv)
    jobs = sorted((j for j in jobs if j["score"] >= cfg["min_score_in_digest"]), key=lambda j: -j["score"])
    digest.assign_sections(jobs)
    ledger = outreach.sync() if not os.getenv("DRY_RUN") else outreach.load()  # sent drafts -> APPLIED.md
    replies = inbox.scan() if not os.getenv("DRY_RUN") else []  # interviews / rejections in her Gmail
    applied_data = applied.load()
    for j in jobs:
        j["applied"] = applied.status(j, applied_data)
    if not os.getenv("DRY_RUN") or os.getenv("KIT_IN_DRY_RUN"):
        kit.make_kits(jobs, cv)

    made = outreach.prepare(jobs, cfg) if not os.getenv("DRY_RUN") else []
    if not os.getenv("DRY_RUN"):  # strong jobs from earlier digests that still have no application
        made += outreach.backfill(cfg)[0]
        try:  # a few more form-based jobs for the Windows helper each run
            from . import formkits
            formkits.run(5)
        except Exception as ex:
            log.warning("form kits failed: %s", ex)
    ledger = outreach.load()

    label = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%a %d %b %Y, %H:%M")
    body = digest.build_html(jobs, health, label, inbox.digest_block(replies)
                             + outreach.digest_block(made, ledger, outreach._settings(cfg)["mode"]))
    PREVIEW.parent.mkdir(exist_ok=True)
    PREVIEW.write_text(body, encoding="utf-8")
    if os.getenv("DRY_RUN"):
        log.info("DRY_RUN: not emailing, not updating seen list")
        return
    strong, good, _ = digest.summary(jobs)
    subject = (f"🎯 {strong} strong · 👍 {good} good · {len(jobs)} new jobs — {label}" if jobs
               else f"No new jobs — {label}")
    # Emailed applications are already in her Gmail Drafts; attach PDFs only for the top 5 form-based jobs
    # (Gmail rejects mails over 25 MB).
    form_jobs = [j for j in jobs if j.get("attachments") and not j.get("email_application")][:5]
    if not digest.send(subject, body, [a for j in form_jobs for a in j["attachments"]]):
        log.error("Email not sent; seen list left unchanged so jobs show up next run")
        sys.exit(1)

    today = date.today().isoformat()
    for k in new:
        seen[k] = today
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    SEEN.write_text(json.dumps({k: v for k, v in seen.items() if v >= cutoff}, indent=0, sort_keys=True))
    report.build_report(report.append_log(jobs, today))
    weekly.maybe_send(datetime.now(ZoneInfo("Europe/Berlin")).date(), cfg)


if __name__ == "__main__":
    main()
