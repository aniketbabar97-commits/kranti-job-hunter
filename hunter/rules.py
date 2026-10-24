"""Deterministic score corrections applied after AI scoring.

The AI judges fit; these rules enforce hard facts it tends to under-weight:
on-site jobs outside Germany and vague LinkedIn posts must not rank as strong matches.
"""
import re

GERMANY = re.compile(
    r"\b(germany|deutschland|baden|bayern|bavaria|berlin|brandenburg|bremen|hamburg|hessen|hesse|"
    r"niedersachsen|lower saxony|mecklenburg|nordrhein|north rhine|rheinland|rhineland|saarland|sachsen|"
    r"saxony|schleswig|th[uü]ringen|thuringia|westfalen|westphalia|w[uü]rttemberg|"
    r"m[uü]nchen|munich|k[oö]ln|cologne|frankfurt|stuttgart|d[uü]sseldorf|dortmund|essen|leipzig|"
    r"dresden|hannover|hanover|n[uü]rnberg|nuremberg|karlsruhe|mannheim|heidelberg|bonn|m[uü]nster|"
    r"wiesbaden|mainz|augsburg|freiburg|aachen|bielefeld|bochum|kiel|l[uü]beck|rostock|ulm|regensburg|"
    r"darmstadt|ingolstadt|wolfsburg|braunschweig|g[uü]tersloh|paderborn|osnabr[uü]ck|kassel|erfurt|"
    r"magdeburg|potsdam|saarbr[uü]cken|koblenz|trier|w[uü]rzburg|heilbronn|pforzheim|reutlingen)\b", re.I)
REMOTE = re.compile(r"\b(remote|home ?office|homeoffice|mobiles arbeiten|work from home|wfh|100 ?% remote|fully remote)\b", re.I)
OUTSIDE_EU_REMOTE = re.compile(
    r"\b(india|bangalore|bengaluru|pune|hyderabad|chennai|noida|gurgaon|gurugram|mumbai|delhi|kolkata|"
    r"usa|united states|canada|philippines|vietnam|brazil|mexico|uae|dubai|singapore|australia|"
    r"colombia|bogota|argentina|buenos aires|chile|santiago|peru|lima|sao paulo|são paulo|latam|latin america|"
    r"china|shanghai|japan|malaysia|kuala lumpur|south africa|egypt|cairo|morocco)\b", re.I)
# Workday-style "5 Locations": we can't tell where, so it is not a sure best fit
UNKNOWN_PLACES = re.compile(r"^\s*\d+\s+(locations|standorte)\s*$", re.I)
CAP_UNKNOWN_PLACE = 65
HIRING = re.compile(r"\b(hiring|we.?re looking|looking for|job|role|position|opening|vacanc|stelle|wir suchen|join (our|us))\b", re.I)
COMMERCE_CORE = re.compile(r"\b(hybris|sap commerce|commerce cloud|sap cx|ccv2|spartacus|composable storefront)\b", re.I)

JAVA_COMMERCE = re.compile(r"(?i)\b(java|kotlin|spring)\b.*\b(commerce|shop|onlineshop|webshop)|\b(commerce|shop|onlineshop|webshop)\b.*\b(java|kotlin|spring)\b")

# Floors: a real SAP Commerce role in Germany/remote is always worth applying to, even if German is required.
FLOOR_CORE_TITLE = 80
FLOOR_JAVA_COMMERCE = 60

CAP_ONSITE_ABROAD = 35
CAP_FAR_AWAY = 25
CAP_VAGUE_POST = 45
CAP_POST_NO_LOCATION = 65


def adjust(job):
    """Return (score, note) after hard caps. `job` needs title/location/description/source/remote."""
    score = int(job.get("score") or 0)
    text = f"{job.get('title', '')} {job.get('location', '')} {job.get('description', '')}"
    is_post = job.get("source") == "LinkedIn post"
    in_germany = job.get("source") == "Arbeitsagentur" or bool(GERMANY.search(f"{job.get('location', '')} {text}"))
    remote = str(job.get("remote")) == "True" or bool(REMOTE.search(text))
    notes = []

    if OUTSIDE_EU_REMOTE.search(text) and not in_germany:
        score, notes = min(score, CAP_FAR_AWAY), ["outside Europe"]
    elif is_post:
        if not (HIRING.search(text) and COMMERCE_CORE.search(text) or HIRING.search(text) and score >= 60):
            score, notes = min(score, CAP_VAGUE_POST), ["post doesn't clearly name an open role"]
        elif not (in_germany or remote):
            score, notes = min(score, CAP_POST_NO_LOCATION), ["post doesn't say Germany or remote"]
    elif not in_germany and UNKNOWN_PLACES.search(job.get("location", "")):
        score, notes = min(score, CAP_UNKNOWN_PLACE), ["location not stated (several sites)"]
    elif not in_germany and not remote and job.get("location"):
        score, notes = min(score, CAP_ONSITE_ABROAD), ["on-site outside Germany"]
    elif not is_post and (in_germany or remote):
        title = job.get("title", "")
        if COMMERCE_CORE.search(title) and not re.search(r"(?i)\b(sales|vertrieb|account executive|praktik|intern|werkstudent)\b", title):
            score = max(score, FLOOR_CORE_TITLE)
        elif JAVA_COMMERCE.search(title):
            score = max(score, FLOOR_JAVA_COMMERCE)
    return score, "; ".join(notes)


def apply(jobs):
    for j in jobs:
        old = int(j.get("score") or 0)
        new, note = adjust(j)
        if new < old:
            j["why"] = f"{j.get('why', '')} [capped: {note}]".strip()
        j["score"] = new
    return jobs
