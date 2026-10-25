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
    cl["contact"] = ""  # the template's contact person belongs to the template company
    cl["logistics"] = ("Die direkte Abstimmung mit Fachbereichen und Kunden gehört für mich selbstverständlich dazu, und in "
                       "internationalen, agilen Teams arbeite ich eigenständig und ergebnisorientiert – vor Ort, hybrid oder remote. "
                       "Ich lebe in Karlsruhe, besitze eine gültige Arbeitserlaubnis und kann nach meiner Kündigungsfrist ab dem "
                       f"16.12.2026 starten. Gern zeige ich Ihnen in einem persönlichen Gespräch, wie ich {company} technisch voranbringen kann.")
    return cl


def tailoring(tpl, company):
    """Template tailoring with the company-specific texts rewritten (the template names another company)."""
    t = copy.deepcopy(tpl)
    t["why_company"] = (f"{company} setzt auf SAP Commerce Cloud – genau dort liegt meine Stärke: über fünf Jahre Hybris "
                        "2105/2211, OCC-APIs und PIM-/ERP-Integrationen für Rockwell Automation und Shell, SAP Certified "
                        "Commerce Cloud Developer. Ich möchte diese Erfahrung als Developer oder Consultant bei Ihnen einbringen, "
                        "von Karlsruhe aus vor Ort, hybrid oder remote, ab dem 16.12.2026.")
    t["linkedin_message"] = (f"Guten Tag, {company} setzt auf SAP Commerce Cloud – ich bringe 5+ Jahre Hybris 2105/2211 "
                             "(Rockwell Automation, Shell), OCC-APIs und PIM-/ERP-Integrationen mit, SAP-zertifiziert. "
                             "Start ab 16.12.2026, Karlsruhe. Gern kurz sprechen?")
    return t


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
        kit = {"job": job, "tailoring": tailoring(tpl["tailoring"], t["company"]),
               "letters": {"de": letter(tpl["letters"]["de"], t["company"])}, "lang": "de", "created": today}
        f.write_text(json.dumps(kit, ensure_ascii=False, indent=1), encoding="utf-8")
        made += 1
    print(f"initiative kits: {made} new, {skipped} skipped (already applied)")
    return made


if __name__ == "__main__":
    make()


def repair():
    """Rewrite existing initiative kits made before the template texts were neutralised."""
    for f in DIR.glob("*-initiative-*.json"):
        k = json.loads(f.read_text(encoding="utf-8"))
        c = k["job"]["company"]
        k["tailoring"] = tailoring(k["tailoring"], c)
        k["letters"]["de"] = letter(k["letters"]["de"], c)
        f.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
