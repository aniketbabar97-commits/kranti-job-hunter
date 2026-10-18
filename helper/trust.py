"""Per-ATS autonomy: how much the helper may do by itself on each applicant-tracking system.

data/ats_trust.json: {ats: {"mode": "assisted|auto", "ok": n, "unconfirmed_streak": n}}
Rule: the first job on an ATS is "assisted" (fill everything, stop before Submit, she clicks it and presses `a`).
After one confirmed submission the ATS becomes "auto" (the helper clicks Submit itself).
Three unconfirmed submissions in a row send it back to "assisted".
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "ats_trust.json"
ASSISTED, AUTO = "assisted", "auto"
STREAK_LIMIT = 3

# fallback ATS detection when helper/sites has no detect() yet
_KNOWN = [("greenhouse", r"greenhouse\.io"), ("lever", r"lever\.co"), ("workday", r"myworkdayjobs\.com|workday"),
          ("smartrecruiters", r"smartrecruiters\.com"), ("personio", r"personio\.(de|com)|jobs\.personio"),
          ("softgarden", r"softgarden"), ("successfactors", r"successfactors|sapsf|jobs\.sap\.com"),
          ("recruitee", r"recruitee\.com"), ("workable", r"workable\.com"), ("teamtailor", r"teamtailor\.com"),
          ("join", r"join\.com"), ("onlyfy", r"onlyfy|prescreen"), ("umantis", r"umantis|haufe"),
          ("rexx", r"rexx-systems|rexx"), ("d.vinci", r"dvinci|d-vinci"), ("concludis", r"concludis"),
          ("taleo", r"taleo\.net"), ("icims", r"icims\.com"), ("bamboohr", r"bamboohr\.com"),
          ("ashby", r"ashbyhq\.com"), ("linkedin", r"linkedin\.com"), ("indeed", r"indeed\."),
          ("stepstone", r"stepstone\."), ("arbeitsagentur", r"arbeitsagentur\.de")]


def detect(url):
    """ATS name for a URL: helper.sites.detect when the sites package provides it, else a host-pattern guess, else 'own'."""
    try:
        from helper import sites  # other agents build this package
        d = getattr(sites, "detect", None)
        if d:
            found = d(url)
            if found:
                name = found if isinstance(found, str) else getattr(found, "name", None) or getattr(found, "__name__", None)
                if name:
                    return str(name).lower()
    except Exception:
        pass
    u = (url or "").lower()
    for name, rx in _KNOWN:
        if re.search(rx, u):
            return name
    return "own"


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except Exception:
        return {}


def save(data):
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def entry(ats, data=None):
    data = load() if data is None else data
    return data.setdefault(ats or "own", {"mode": ASSISTED, "ok": 0, "unconfirmed_streak": 0})


def mode(ats):
    """'assisted' (stop before Submit) or 'auto' (submit by itself)."""
    return entry(ats).get("mode", ASSISTED)


def record(ats, confirmed):
    """Update the store after a submission attempt; returns the new mode."""
    data = load()
    e = entry(ats, data)
    if confirmed:
        e["ok"] = e.get("ok", 0) + 1
        e["unconfirmed_streak"] = 0
        e["mode"] = AUTO
    else:
        e["unconfirmed_streak"] = e.get("unconfirmed_streak", 0) + 1
        if e["unconfirmed_streak"] >= STREAK_LIMIT:
            e["mode"] = ASSISTED
    save(data)
    return e["mode"]
