"""Fixed answers for application-form questions, taken from profile/facts.yaml. Never invents a fact.

answer(label, lang) -> str | None.  None = unknown question: it is logged to helper/questions.txt so it can be added
to facts.yaml once, and the job is parked for a human.
"""
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = Path(__file__).resolve().parent / "questions.txt"
_FACTS = None


def facts():
    global _FACTS
    if _FACTS is None:
        import yaml
        _FACTS = yaml.safe_load((ROOT / "profile" / "facts.yaml").read_text(encoding="utf-8"))
    return _FACTS


def master_job(key):
    """Current / most recent position from profile/master.yaml (jobs[0])."""
    try:
        import yaml
        m = yaml.safe_load((ROOT / "profile" / "master.yaml").read_text(encoding="utf-8"))
        return m["jobs"][0][key]
    except Exception:
        return None


def yes_no(value, lang):
    if isinstance(value, str) and not re.fullmatch(r"(yes|no|ja|nein)", value.strip(), re.I):
        return value  # a sentence such as "yes, up to 50 %"
    truthy = value is True or str(value).lower() in ("yes", "ja", "true")
    return ("Ja" if truthy else "Nein") if lang == "de" else ("Yes" if truthy else "No")


def de_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return iso


# (label regex, function(facts, lang) -> str). First match wins. Order matters: specific before generic.
RULES = [
    (r"disab|behinder|handicap|gleichgestellt", lambda f, l: yes_no(f["disability"], l)),
    (r"nationalit|staatsangehörigkeit|staatsbürgerschaft|citizenship", lambda f, l: "Indisch" if l == "de" else f["nationality"]),
    (r"security clearance|sicherheitsüberprüfung|sicherheitsfreigabe|\bsü ?[123]\b", lambda f, l: yes_no(f.get("security_clearance", False), l)),
    (r"criminal|vorstrafe|polizeiliche|führungszeugnis|convict|background check", lambda f, l: yes_no(f["criminal_record"], l)),
    (r"\breferr|empfohlen|empfehlung|referred by|mitarbeiterempfehlung", lambda f, l: yes_no(f["referral"], l)),
    (r"travel|reise|dienstreise|reisebereit", lambda f, l: yes_no(f["travel"], l)),
    # relocation: yes within Germany, no when the question names another country / city abroad
    (r"(reloca|umzug|umzieh|umzugsbereit).{0,60}\b(to|nach)\b(?!.{0,40}(germany|deutschland|berlin|m[üu]nchen|munich|hamburg|"
     r"frankfurt|k[öo]ln|cologne|stuttgart|d[üu]sseldorf|karlsruhe|leipzig|n[üu]rnberg|hannover|bremen|dresden))",
     lambda f, l: yes_no("no", l)),
    (r"reloca|umzug|umzieh|umzugsbereit|wohnortwechsel", lambda f, l: yes_no(f["relocation_within_germany"], l)),
    # language-level yes/no questions: German C1/C2 / fluent -> no (B1); English fluent -> yes
    (r"(german|deutsch).{0,60}\b(c1|c2|fluent|fließend|verhandlungssicher|native|muttersprach)|"
     r"\b(c1|c2|fluent|fließend|verhandlungssicher).{0,40}(german|deutsch)", lambda f, l: yes_no("no", l)),
    (r"(english|englisch).{0,60}\b(c1|c2|fluent|fließend|verhandlungssicher|business)|"
     r"\b(c1|c2|fluent|fließend|verhandlungssicher).{0,40}(english|englisch)", lambda f, l: yes_no("yes", l)),
    (r"most recent (job )?title|current (job )?title|(aktuelle|letzte) position|jobtitel|job title",
     lambda f, l: master_job("title")),
    (r"most recent employer|current (employer|company)|(aktueller|letzter) arbeitgeber|\bemployer\b|\barbeitgeber\b|^company\b|^org\b",
     lambda f, l: master_job("company")),
    (r"^school|universit|hochschule|college", lambda f, l: f["education"]["university"]),
    (r"^degree|abschluss|highest (level of )?education", lambda f, l: "Bachelor"),
    (r"discipline|field of study|major|studienrichtung|studienfach|fachrichtung", lambda f, l: "Computer Engineering"),
    (r"campus event|career fair|karrieremesse|which event", lambda f, l: "None"),
    (r"\bpronouns?\b", lambda f, l: "she/her"),
    (r"preferred (first )?name|rufname|what would you like us to call you", lambda f, l: f["name"]["first"]),
    (r"i confirm|ich bestätige|hereby confirm|is true and correct|wahrheitsgemäß", lambda f, l: "Ja" if l == "de" else "Yes"),
    (r"remote|hybrid|home.?office|mobiles arbeiten|on.?site|vor ort", lambda f, l: yes_no(f["remote_or_hybrid"], l)),
    (r"previously (worked|employed|applied)|ever (worked|been employed)|former employee|schon einmal|bereits (bei|für) uns|"
     r"zuvor (bei|für)|früher (bei|für)|ehemalige", lambda f, l: yes_no(f["previous_employment_at_company"], l)),
    (r"driv(ing|er'?s?) licen[cs]e|führerschein|fahrerlaubnis", lambda f, l: yes_no(f["driving_licence"], l)),
    # yes/no phrasings first: "do you need sponsorship" -> No, "are you authorised to work" -> Yes
    (r"(need|require|benötig|erforderlich|brauch).{0,40}(sponsor|visa|visum|arbeitserlaubnis)|"
     r"(sponsor|visa|visum).{0,40}(need|require|benötig|erforderlich)", lambda f, l: yes_no("no", l)),
    (r"(authori[sz]ed|eligible|permitted|legally (able|allowed|entitled)|berechtigt|erlaubt).{0,30}(to work|work|arbeit)|"
     r"right to work|work authori[sz]ation|(besitzen|haben) sie .*arbeitserlaubnis", lambda f, l: yes_no("yes", l)),
    (r"work.?permit|arbeitserlaubnis|arbeitsgenehmigung|visa|sponsorship|aufenthaltstitel|right to work|"
     r"authori[sz]ed to work|legally (allowed|entitled)|eligible to work",
     lambda f, l: ("Gültige Aufenthalts- und Arbeitserlaubnis für Deutschland, kein Visa-Sponsoring nötig" if l == "de"
                   else f["work_permit"])),
    (r"german|deutsch(kenntnisse)?\b|sprachniveau deutsch", lambda f, l: f"German {f['languages']['german']}" if l == "en"
     else f"Deutsch {f['languages']['german']}"),
    (r"english|englisch", lambda f, l: f"English {f['languages']['english']}" if l == "en" else f"Englisch {f['languages']['english']}"),
    (r"language|sprach", lambda f, l: ", ".join(
        f"{k.capitalize()} {v}" if l == "en" else {"english": "Englisch", "german": "Deutsch", "hindi": "Hindi", "marathi": "Marathi"}.get(k, k) + f" {v}"
        for k, v in f["languages"].items()).replace("native", "Muttersprache" if l == "de" else "native")),
    (r"sap commerce|hybris", lambda f, l: str(f["experience_years"]["sap_commerce"])),
    (r"\bjava\b", lambda f, l: str(f["experience_years"]["java"])),
    (r"spring", lambda f, l: str(f["experience_years"]["spring"])),
    (r"years? of|jahre|berufserfahrung|experience|erfahrung|seniority", lambda f, l: str(f["experience_years"]["total"])),
    (r"degree|education|abschluss|ausbildung|studium|qualification|university|hochschule|graduat",
     lambda f, l: f"{f['education']['degree']}, {f['education']['university']} ({f['education']['year']})"),
    (r"salary|gehalt|vergütung|compensation|verdienst|einkommen", lambda f, l: str(f["salary"]["default_eur"])),
    (r"notice|kündigungsfrist", lambda f, l: (f"Gekündigt, letzter Arbeitstag {de_date(f['notice']['last_day'])}" if l == "de"
                                              else f"Serving notice, last working day {de_date(f['notice']['last_day'])}")),
    (r"earliest|start|eintritt|verfügbar|available|availab|beginn|antritt", lambda f, l: de_date(f["notice"]["earliest_start"])),
    (r"linkedin", lambda f, l: f["linkedin"]),
    (r"^(full.?)?name\b|^ihr name|vollständiger name|vor-? und nachname|^name\s*\*?", lambda f, l: f"{f['name']['first']} {f['name']['last']}"),
    (r"first.?name|vorname|given.?name|^first\b", lambda f, l: f["name"]["first"]),
    (r"last.?name|nachname|surname|family.?name|^last\b", lambda f, l: f["name"]["last"]),
    (r"e-?mail", lambda f, l: os.environ.get("CANDIDATE_EMAIL")),
    (r"phone|telefon|mobil|handy|tel\.?\b", lambda f, l: os.environ.get("CANDIDATE_PHONE")),
    (r"gender|geschlecht", lambda f, l: ("Weiblich" if l == "de" else "Female")),
    (r"anrede|salutation", lambda f, l: f["name"]["salutation"]),
    (r"postal|postleitzahl|\bplz\b|zip", lambda f, l: f["location"]["postal_code"]),
    (r"\b(city|ort|stadt|wohnort|location|standort)\b", lambda f, l: f["location"]["city"]),
    (r"\bcountry\b|\bland\b", lambda f, l: "Deutschland" if l == "de" else f["location"]["country"]),
    (r"how (did )?you (hear|heard|find|found|learn)|wie (sind sie|bist du|hast du|haben sie).*(aufmerksam|gefunden)|quelle|source|woher",
     lambda f, l: f["source"]),
    (r"privacy|datenschutz|consent|einwillig|terms|bedingungen|talent ?pool|keep .*data|daten .*speichern|newsletter",
     lambda f, l: "Ja" if l == "de" else "Yes"),
]
_RULES = [(re.compile(p, re.I), fn) for p, fn in RULES]


def answer(question_label, lang="en"):
    """Answer for a form question, or None (unknown: logged to helper/questions.txt)."""
    label = (question_label or "").strip()
    if not label:
        return None
    for rx, fn in _RULES:
        if rx.search(label):
            try:
                v = fn(facts(), "de" if lang == "de" else "en")
            except Exception:
                v = None
            if v:
                return str(v)
    log_question(label)
    return None


def log_question(label):
    line = re.sub(r"\s+", " ", label)[:200]
    try:
        old = QUESTIONS.read_text(encoding="utf-8") if QUESTIONS.exists() else ""
        if line not in old:
            with open(QUESTIONS, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def is_yes(value):
    return bool(re.match(r"\s*(yes|ja|true)", str(value), re.I))


def is_no(value):
    return bool(re.match(r"\s*(no|nein|false)", str(value), re.I))
