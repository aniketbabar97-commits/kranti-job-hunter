"""Initiative applications (Initiativbewerbung) to every known SAP Commerce / Hybris user and partner in Germany.

python -m hunter.initiative          -> creates one kit per company in applications/ (skips companies she already applied to)
Targets: data/initiative_targets.json (company, domain, jobs email if one was found). With an email the kit goes
the email route (send_kits); otherwise the nightly PC run opens the careers site and uses its
"Initiativbewerbung" option.
"""
import copy
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "applications"
TEMPLATE = "2026-10-18-maify-gmbh-senior-sap-commerce-cloud-hybris-developer-al.json"
TITLE = "Initiativbewerbung – SAP Commerce Cloud (Hybris) Developer / Consultant"


def _norm(x):
    return re.sub(r"\(.*?\)|gmbh|se|ag|kg|co|group|gruppe|[^a-z]", "", (x or "").lower())


def applied_companies():
    """Companies she already applied to (website or email) — no initiative there."""
    text = (ROOT / "APPLIED.md").read_text(encoding="utf-8") if (ROOT / "APPLIED.md").exists() else ""
    names = {_norm(m) for m in re.findall(r"\(([^,()]+),", text)}
    for f in ("data/submissions.json", "data/applications.json"):
        p = ROOT / f
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            names |= {_norm(v.get("company")) for v in (d.values() if isinstance(d, dict) else d)}
    return {n for n in names if len(n) > 2}


def letter(tpl, company):
    cl = copy.deepcopy(tpl)
    cl["subject"] = f"Initiativbewerbung: SAP Commerce Cloud (Hybris) Developer / Consultant – Kranti Chavan"
    cl["salutation"] = "Sehr geehrte Damen und Herren,"
    cl["hook"] = (f"{company} setzt auf SAP Commerce Cloud – und genau dort bringe ich über fünf Jahre Praxis mit. "
                  "Bei Rockwell Automation und Shell entwickle und erweitere ich B2B- und B2C-Plattformen auf "
                  "SAP Commerce Cloud (Hybris 2105 und 2211) mit Java und Spring – als SAP Certified Commerce Cloud "
                  "Developer. Deshalb bewerbe ich mich initiativ als SAP Commerce Developer oder Consultant.")
    return cl


def make(today=None):
    today = today or date.today().isoformat()
    tpl = json.loads((DIR / TEMPLATE).read_text(encoding="utf-8"))
    done = applied_companies()
    targets = json.loads((ROOT / "data" / "initiative_targets.json").read_text(encoding="utf-8"))
    made = skipped = 0
    for t in targets:
        slug = re.sub(r"[^a-z0-9]+", "-", t["company"].lower()).strip("-")
        f = DIR / f"{today}-initiative-{slug}.json"
        if any(DIR.glob(f"*-initiative-{slug}.json")):
            continue
        if _norm(t["company"]) in done or any(_norm(t["company"])[:8] in d for d in done):
            skipped += 1
            continue
        job = {"title": TITLE, "company": t["company"], "location": "Deutschland",
               "url": f"https://www.{t['domain']}/#initiativbewerbung", "apply_url": "", "score": 78,
               "source": "Initiative (SAP Commerce user/partner)", "posted": today, "lang": "de", "salary": "",
               "initiative": True, "contact": t.get("email") or "", "direct_url": f"https://www.{t['domain']}/"}
        if t.get("email"):
            job["channel"] = "email"
        kit = {"job": job, "tailoring": copy.deepcopy(tpl["tailoring"]),
               "letters": {"de": letter(tpl["letters"]["de"], t["company"])}, "lang": "de", "created": today}
        f.write_text(json.dumps(kit, ensure_ascii=False, indent=1), encoding="utf-8")
        made += 1
    print(f"initiative kits: {made} new, {skipped} skipped (already applied)")
    return made


if __name__ == "__main__":
    make()
