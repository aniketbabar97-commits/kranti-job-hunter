"""Full job record: data/jobs_log.csv (all jobs ever sent) rendered as JOBS.md,
grouped like the email (language -> fit score), newest first. Rebuilt every run."""
import csv
from datetime import date
from pathlib import Path

from . import applied, rules
from .digest import LANGS, SECTIONS, age_label
from .score import _guess_lang

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "jobs_log.csv"
REPORT = ROOT / "JOBS.md"
FIELDS = ["found", "score", "title", "company", "location", "remote", "source", "url", "why", "lang", "posted"]


def read_log():
    if not LOG.exists():
        return []
    with LOG.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:  # rows written before lang/posted existed
        r.setdefault("description", "")
        if not r.get("lang"):
            r["lang"] = _guess_lang({"title": r["title"], "description": ""})
        if not r.get("posted"):
            r["posted"] = r["found"]
        r["score"] = int(r["score"] or 0)
    return rows


def append_log(jobs, today):
    """Append this run's jobs; rewrites the file once if it still has the old header."""
    rows = read_log()
    rows += [{"found": today, "score": j["score"], "title": j["title"], "company": j["company"],
              "location": j["location"], "remote": j["remote"], "source": j["source"], "url": j["url"],
              "why": j.get("why", ""), "lang": j.get("lang", ""), "posted": j.get("posted") or today} for j in jobs]
    with LOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return rows


def _cell(text):
    return str(text).replace("|", "/").replace("\n", " ").strip()


def build_report(rows):
    today = date.today().isoformat()
    # Same hard ranking rules as the email, so older rows (scored before the rules existed) sort consistently.
    rows = [dict(r, description="") for r in rows]
    applied_data = applied.load()
    for r in rows:
        r["score"], _ = rules.adjust(r)
    by_lang = {code: [r for r in rows if r["lang"] == code] for code, _ in LANGS}
    out = [f"# Job record — every job sent ({len(rows)})", "",
           f"_Updated {today}. Grouped like the email: language → fit score; newest first inside each group. "
           f"Use Ctrl+F / ⌘F to search, or open [the raw CSV](data/jobs_log.csv) in Excel. "
           f"Mark applications in [APPLIED.md](APPLIED.md)._", ""]
    for code, title in LANGS:
        anchor = "english" if code == "en" else "german"
        out.append(f"- [{title} ({len(by_lang[code])})](#{anchor})")
    out.append("")
    for code, title in LANGS:
        out += [f'<a id="{"english" if code == "en" else "german"}"></a>', "", f"## {title} ({len(by_lang[code])})", ""]
        for floor, label in SECTIONS:
            ceiling = next((f for f, _ in reversed(SECTIONS) if f > floor), 101)
            group = [r for r in by_lang[code] if floor <= r["score"] < ceiling]
            if not group:
                continue
            group.sort(key=lambda r: (r["posted"], r["score"]), reverse=True)
            out += [f"### {label} ({len(group)})", "",
                    "| Score | Age | Job | Company | Location | Remote | Source | Found | Status | Why |",
                    "|---:|---|---|---|---|---|---|---|---|---|"]
            for r in group:
                out.append(" | ".join([
                    f"| {r['score']}", age_label(r), f"[{_cell(r['title'])}]({r['url']})", _cell(r["company"]),
                    _cell(r["location"]), "🏠" if r["remote"] == "True" else "", _cell(r["source"]),
                    r["found"], {"applied": "✅ Applied", "company": "↺ company"}.get(applied.status(r, applied_data), ""),
                    _cell(r["why"]) + " |"]))
            out.append("")
    REPORT.write_text("\n".join(out), encoding="utf-8")
