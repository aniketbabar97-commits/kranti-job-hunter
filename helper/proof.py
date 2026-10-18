"""Proof of submission: data/submissions.json + out/proof/<slug>.png + the APPLIED.md line.

A website application is only "applied" when there is proof: the site's thank-you page ("page") or a
confirmation-of-receipt mail in her inbox within 24 h ("mail", set by hunter/inbox.py). Submissions without
proof stay "pending" in submissions.json and never reach APPLIED.md.
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "submissions.json"
PROOF_DIR = ROOT / "out" / "proof"


def slug(job):
    return re.sub(r"[^a-z0-9]+", "-", f"{job['company']}-{job['title']}".lower()).strip("-")[:60]


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []
    except Exception:
        return []


def save(items):
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")


def screenshot(page, job):
    """Save the current page as out/proof/<slug>.png; returns the path or '' when it fails."""
    try:
        PROOF_DIR.mkdir(parents=True, exist_ok=True)
        path = PROOF_DIR / f"{slug(job)}.png"
        page.screenshot(path=str(path), full_page=True)
        return str(path.relative_to(ROOT))
    except Exception:
        return ""


def record(job, ats, proof, shot="", mode="auto"):
    """Upsert the submission for this job. proof: 'page' | 'mail' | 'none' (= pending)."""
    items = load()
    rec = next((s for s in items if s.get("url") == job["url"]), None)
    if rec is None:
        rec = {"url": job["url"]}
        items.append(rec)
    rec.update({"company": job["company"], "title": job["title"], "ats": ats or "own",
                "ts": datetime.now().isoformat(timespec="seconds"), "proof": proof, "screenshot": shot or rec.get("screenshot", ""),
                "mode": mode, "status": "confirmed" if proof in ("page", "mail") else "pending"})
    save(items)
    return rec


def applied_line(job, how="confirmed"):
    """Append the APPLIED.md line "(Company, website via helper – confirmed)" once; True if written."""
    f = ROOT / "APPLIED.md"
    text = f.read_text(encoding="utf-8") if f.exists() else "# Applied jobs\n\n## My applications\n"
    if job["url"] in text:
        return False
    line = f"- {datetime.now().date().isoformat()} {job['url']} ({job['company']}, website via helper – {how})\n"
    f.write_text(text.rstrip("\n") + "\n" + line, encoding="utf-8")
    return True


def push(job):
    """Share APPLIED.md with the daily hunter (best effort)."""
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "APPLIED.md", "data/submissions.json", "data/ats_trust.json"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-m", f"applied: {job['company']}"], capture_output=True)
        subprocess.run(["git", "-C", str(ROOT), "pull", "--rebase", "-q"], capture_output=True, timeout=60)
        subprocess.run(["git", "-C", str(ROOT), "push", "-q"], capture_output=True, timeout=60)
    except Exception:
        print("   (saved locally; could not push to GitHub — that's fine)")


def log_submission(job, ats, page=None, proof_seen=False, mode="auto"):
    """Called by the helper after Submit. Proof page seen -> screenshot + APPLIED.md; else pending only."""
    shot = screenshot(page, job) if page is not None else ""
    if proof_seen:
        record(job, ats, "page", shot, mode)
        applied_line(job, "confirmed")
        push(job)
        return "confirmed"
    record(job, ats, "none", shot, mode)
    return "pending"
