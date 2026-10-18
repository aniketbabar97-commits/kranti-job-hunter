"""Email applications for ready-made kits (applications/*.json) that have an application address.

python -m hunter.send_kits [max]   (workflow input "send_kits")
Builds the CV + cover letter PDFs with her real contact data, then drafts or sends via outreach.prepare
(same rules: one job never twice, max 2 roles per company and never two on the same day).
"""
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from . import applied, documents, outreach

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "send"
log = logging.getLogger(__name__)


def kits(days=45):
    since = (date.today() - timedelta(days=days)).isoformat()
    latest = {}
    for f in sorted((ROOT / "applications").glob("*.json")):
        k = json.loads(f.read_text(encoding="utf-8"))
        if k.get("created", "") >= since:
            latest[k["job"]["url"]] = k  # newest kit per job wins (files sort by date)
    return list(latest.values())


def build(kit, master):
    j, t = kit["job"], kit["tailoring"]
    out = OUT / kit["slug"]
    out.mkdir(parents=True, exist_ok=True)
    htmls = [out / "Kranti_Chavan_CV.html"]
    htmls[0].write_text(documents.render_cv(master, t), encoding="utf-8")
    for lang, cl in kit["letters"].items():
        f = out / f"Kranti_Chavan_Cover_Letter_{lang.upper()}.html"
        f.write_text(documents.render_cover(master, cl, j, lang, t.get("headline") or master["headlines"][0]),
                     encoding="utf-8")
        htmls.append(f)
    return documents.to_pdf(htmls)


def run(limit=60):
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cfg.setdefault("applications", {})["max_per_day"] = limit  # explicit run: the cap is the run's limit
    if not outreach.ready():
        raise SystemExit("Gmail login or CANDIDATE_* secrets missing")
    master = yaml.safe_load((ROOT / "profile" / "master.yaml").read_text(encoding="utf-8"))
    data = applied.load()
    jobs = []
    for k in sorted(kits(), key=lambda k: -int(k["job"].get("score") or 0)):
        j = dict(k["job"])
        if not outreach.pick_email(j) or applied.status(j, data) == "applied":
            continue
        k["slug"] = f"{outreach._company_key(j)}-{abs(hash(j['url'])) % 10000}"
        try:
            j["attachments"] = build(k, master)
        except Exception as ex:
            log.warning("PDF for %s failed: %s", j["title"], ex)
            continue
        j["letters"], j["description"], j["applied"] = k["letters"], "", ""
        jobs.append(j)
    log.info("kits with an application address: %d", len(jobs))
    made = outreach.prepare(jobs, cfg)
    log.info("email applications this run: %d (%s)", len(made), outreach._settings(cfg)["mode"])
    for m in made:
        log.info("  %s · %s -> %s [%s]", m["company"], m["title"], m["to"], m["status"])
    return made


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
