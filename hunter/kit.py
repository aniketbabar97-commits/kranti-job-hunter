"""Application kits for strong jobs: tailored ATS-friendly CV + cover letter(s) as PDF, copy-paste answers for
application forms, LinkedIn note and email draft.

Nothing is sent or submitted automatically. PDFs contain phone/email/photo, so they are written to the git-ignored
out/ folder and attached to the (private) digest email — never committed to the public repository.
"""
import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

import requests
import yaml

from . import documents, score

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "applications"          # kit notes (no personal contact data) — committed
OUT = ROOT / "out"                   # PDFs with contact data/photo — git-ignored, emailed
MIN_SCORE = 80
MAX_PER_RUN = 6
log = logging.getLogger(__name__)

# Technologies worth flagging if a letter mentions them but her CV doesn't.
TECH = ["Kafka", "Kotlin", "TypeScript", "React", "Angular", "Vue", "Node.js", "Python", "Golang", "AWS", "Azure", "GCP",
        "Terraform", "GraphQL", "MongoDB", "PostgreSQL", "Elasticsearch", "Spryker", "Salesforce", "SFCC",
        "commercetools", "Magento", "Shopware", "Intershop", "Spartacus", "Composable Storefront", "Next.js", "PHP",
        "Kubernetes", "Docker", "Hybris", "S/4HANA", "SAP CPI", "Integration Suite", "BTP", "Akeneo", "Salsify"]

PROMPT = """You tailor job applications for this candidate. ACCURACY RULES (most important, never break):
- Use ONLY facts from her master CV below. Never invent employers, numbers, projects, tools or certificates.
- Keep her own verbs ("developed", "configured", "executed", "led database query refactoring" ...). Do not upgrade.
  Example: she EXECUTED CI/CD deployment cycles on CCv2 — never write that she set up / built / introduced CI/CD pipelines.
- If the job asks for something she lacks, do NOT claim it; mention honestly that she is keen to learn it (gap paragraph).
- She is SERVING NOTICE; last working day 15.12.2026, earliest start 16.12.2026. Never say "available immediately".
- German level B1. Never claim more, and never invent goals or plans (no "aiming for C1", no courses she didn't name).
- German letters: salutation "Sehr geehrte Damen und Herren," unless the posting names a contact person
  ("Sehr geehrte Frau <Nachname>," / "Sehr geehrter Herr <Nachname>," — surname only). English letters: "Dear Hiring Team,"
  unless a person is named ("Dear Ms <Surname>,"). The "closing" field must NOT contain a sign-off or her name.

MASTER CV (YAML):
{master}

JOB:
Title: {title}
Company: {company}
Location: {location}
Posting language: {lang}
Posting text: {description}

Return ONLY a JSON object:
{{
 "headline": "CV headline, max 110 chars, mirror the job title words where truthful",
 "summary": "CV summary 60-90 words, mirror the job's keywords that she truly has (ATS), only master-CV facts",
 "skills": {{"<label from master>": ["items copied EXACTLY from that master list, most relevant first"], ...}}  (order the labels by relevance; keep 5-7 labels),
 "bullet_order": {{"rockwell": [indexes 0-5 most relevant first], "shell": [0-5], "cognizant": [0-3]}},
 "keywords_matched": ["job keywords her CV truly covers"],
 "keywords_missing": ["important job keywords she does NOT have"],
 "cover_en": {{"subject": "Application: <exact job title>", "salutation": "Dear Hiring Team, (or named person from posting)",
   "hook": "2-3 sentences: why this company/role specifically + 5+ years SAP Commerce at Rockwell Automation and Shell",
   "bullets": [{{"label": "short bold label", "text": "1-2 sentences mapping her real experience to a job requirement"}} x4],
   "gap": "honest 1-2 sentences about missing items + willingness to learn (empty string if none)",
   "logistics": "Karlsruhe, valid work permit, serving notice until 15 December 2026, invitation to talk",
   "closing": ""}},
 "cover_de": {de_rule},
 "why_company": "answer for 'Why do you want to work for us?' in English, 300-500 characters, specific to this company",
 "motivation_short": "max 300 characters motivation statement",
 "linkedin_message": "max 280 characters to recruiter/team lead",
 "email_subject": "subject for an email application",
 "email_body": "60-90 words, says CV and cover letter are attached"
}}"""


def _call(prompt):
    providers = (("gemini", score._gemini, "GEMINI_API_KEY"),
                 ("groq", lambda p: score._groq(p, json_object=True), "GROQ_API_KEY"),
                 ("groq-plain", score._groq, "GROQ_API_KEY"))  # JSON mode can 400 on malformed output
    for name, fn, key in providers:
        if not os.getenv(key):
            continue
        for attempt in range(3):
            try:
                m = re.search(r"\{.*\}", fn(prompt) or "", re.S)
                data = json.loads(m.group(0)) if m else None
                if data and data.get("cover_en", {}).get("hook"):
                    return data
                log.warning("kit via %s: unusable answer (attempt %d)", name, attempt + 1)
            except requests.HTTPError as ex:
                code = ex.response.status_code if ex.response is not None else 0
                log.warning("kit via %s failed: %s", name, ex)
                if code not in (429, 500, 502, 503):
                    break
                time.sleep(30 * (attempt + 1))
            except Exception as ex:
                log.warning("kit via %s failed: %s", name, ex)
    return None


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:45]


HYPHENS = str.maketrans({"\u2011": "-", "\u2010": "-", "\u2012": "-", "\u00ad": "", "\u00a0": " "})


def _normalize(obj):
    """ATS keyword matching breaks on non-breaking/soft hyphens ("E‑Commerce" != "E-Commerce")."""
    if isinstance(obj, str):
        return obj.translate(HYPHENS)
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    return obj


LOGISTICS = {
    "en": "I live in Karlsruhe and hold a valid German residence and work permit. I am currently serving my notice "
          "period; my last working day is 15 December 2026. I would welcome the opportunity to discuss the role with you.",
    "de": "Ich lebe in Karlsruhe und habe eine gültige Aufenthalts- und Arbeitserlaubnis für Deutschland. Aktuell befinde "
          "ich mich in der Kündigungsfrist, mein letzter Arbeitstag ist der 15.12.2026. Über ein persönliches Gespräch "
          "freue ich mich sehr.",
}


SIGN_OFF = re.compile(r"(?i)(mit freundlichen gr|kind regards|best regards|sincerely|viele gr)")


def _salutation(text, lang):
    """'Sehr geehrte Frau Annika Jürs,' -> 'Sehr geehrte Frau Jürs,' (German letters use the surname only)."""
    m = re.match(r"^(Sehr geehrte Frau|Sehr geehrter Herr|Dear Ms\.?|Dear Mr\.?|Dear Mrs\.?)\s+(.+?),?\s*$", text.strip())
    if m:
        parts = m.group(2).split()
        titles = [w for w in parts[:-1] if w.rstrip(".").lower() in ("dr", "prof")]
        return f"{m.group(1)} {' '.join(titles + [parts[-1]])},"
    return text.strip()


def complete_letter(cl, lang, job):
    """Return a letter with all parts, or None if the AI answer is too incomplete to use."""
    if not isinstance(cl, dict) or not cl.get("hook") or len(cl.get("bullets") or []) < 2:
        return None
    bullets = [b for b in cl["bullets"] if isinstance(b, dict) and b.get("label") and b.get("text")]
    if len(bullets) < 2:
        return None
    return {"subject": cl.get("subject") or (f"Bewerbung als {job['title']}" if lang == "de" else f"Application: {job['title']}"),
            "salutation": _salutation(cl.get("salutation") or ("Sehr geehrte Damen und Herren," if lang == "de" else "Dear Hiring Team,"), lang),
            "hook": cl["hook"], "bullets": bullets[:4], "gap": cl.get("gap", ""),
            "logistics": cl.get("logistics") or LOGISTICS[lang],
            "closing": "" if SIGN_OFF.search(cl.get("closing", "")) else cl.get("closing", "")}


def validate(master, t):
    """Enforce 'select and reorder only': drop skills/bullets that are not in the master CV."""
    allowed = {label: {s.lower(): s for s in items} for label, items in master["skills"].items()}
    skills = {}
    for label, items in (t.get("skills") or {}).items():
        if label in allowed:
            kept = [allowed[label][i.lower()] for i in items if isinstance(i, str) and i.lower() in allowed[label]]
            kept += [s for s in master["skills"][label] if s not in kept]  # never lose real skills
            skills[label] = kept
    for label, items in master["skills"].items():
        skills.setdefault(label, items)
    t["skills"] = skills
    order = {}
    for job in master["jobs"]:
        n = len(job["bullets"])
        given = [i for i in (t.get("bullet_order") or {}).get(job["key"], []) if isinstance(i, int) and 0 <= i < n]
        seen = list(dict.fromkeys(given))
        order[job["key"]] = seen + [i for i in range(n) if i not in seen]
    t["bullet_order"] = order
    return t


def unverified_tech(master, texts):
    """Technologies mentioned in generated texts that the master CV doesn't contain — for manual review."""
    cv = yaml.safe_dump(master).lower()
    blob = " ".join(texts)
    return [t.strip() for t in TECH if t.strip().lower() in blob.lower() and t.strip().lower() not in cv]


def _cover_text(cl):
    """Claims of experience — the honest 'gap' paragraph (missing skills) is deliberately excluded."""
    return " ".join([cl.get("hook", ""), cl.get("logistics", "")]
                    + [b.get("text", "") for b in cl.get("bullets", [])])


def render_note(job, t, files, flags):
    lines = [f"# Application kit — {job['title']}", "",
             f"**{job['company']}** · {job['location'] or 'location n/a'} · score {job['score']} · "
             f"[open the job posting]({job['url']})", "",
             "> The tailored **CV and cover letter PDFs are attached to the digest email** (they contain your phone/photo, "
             "so they are not stored in this public repository). Read them once before sending.", ""]
    if flags:
        lines += [f"> ⚠️ **Check before sending:** the letter mentions {', '.join(flags)}, which is not in your CV. "
                  "Make sure it is phrased as *willing to learn*, not as experience.", ""]
    lines += ["## ATS keyword match", "",
              f"- ✅ Covered: {', '.join(t.get('keywords_matched', [])) or '—'}",
              f"- ⚠️ Missing (don't claim; mention willingness to learn): {', '.join(t.get('keywords_missing', [])) or '—'}", "",
              "## Copy-paste answers for the application form", "",
              "| Field | Answer |", "|---|---|",
              "| First name / Last name | Kranti / Chavan |",
              "| City / Country | Karlsruhe, Germany |",
              "| Phone / Email | see the standard answers block in the digest email |",
              "| LinkedIn | https://linkedin.com/in/kranti-chavan-84a155191 |",
              "| Work permit for Germany | Yes — valid residence & work permit, no sponsorship required |",
              "| Earliest start date | 16.12.2026 (serving notice, last working day 15.12.2026) |",
              "| Notice period | Serving notice, last working day 15.12.2026 |",
              "| Years of experience | 5+ years (SAP Commerce Cloud / Hybris since 2020) |",
              "| Languages | English C2, German B1 (improving), Hindi & Marathi native |",
              "| Willing to relocate / work mode | Remote, hybrid or on-site anywhere in Germany |",
              f"| Salary expectation | {salary_answer(job)} |",
              f"| How did you hear about us? | {job['source'].replace(' careers', ' careers page')} |", "",
              "**Why do you want to work for us?**", "", "```", t.get("why_company", "").strip(), "```", "",
              "**Short motivation**", "", "```", t.get("motivation_short", "").strip(), "```", "",
              "## LinkedIn message to the recruiter / team lead", "", "```", t.get("linkedin_message", "").strip(), "```"]
    if job.get("contact"):
        lines += ["", f"## Email application → {job['contact']}", "",
                  f"**Subject:** {t.get('email_subject', '').strip()}", "", "```", t.get("email_body", "").strip(), "```"]
    lines += ["", "## Files in the email", ""] + [f"- {Path(f).name}" for f in files]
    return "\n".join(lines) + "\n"


TARGET_SALARY = 60000


def salary_answer(job, target=TARGET_SALARY):
    """Her target (60k) unless the posting gives a yearly range; then ask in its upper part, never below 60k
    unless the whole range is lower."""
    nums = [int(n.replace(",", "").replace(".", "")) for n in re.findall(r"\d[\d.,]{3,}", job.get("salary") or "")]
    nums = [n for n in nums if 20000 <= n <= 300000]  # yearly figures only; hourly/monthly ignored
    ask = target
    if nums:
        lo, hi = min(nums), max(nums)
        ask = hi if hi < target else max(target, lo + (hi - lo) * 3 // 4)
    ask = round(ask / 1000) * 1000
    de = f"{ask:,}".replace(",", ".")
    return f"€{ask:,} gross per year (negotiable) · DE: {de} € brutto/Jahr (verhandelbar)"


def make_kits(jobs, cv_text=None, today=None, force=False):
    """Create kits for strong new jobs. Sets job['kit'] (repo note) and job['attachments'] (PDF paths)."""
    today = today or date.today().isoformat()
    master = yaml.safe_load((ROOT / "profile" / "master.yaml").read_text())
    DIR.mkdir(exist_ok=True)
    made = 0
    for job in sorted(jobs, key=lambda j: -j["score"]):
        try:
            made += _make_one(job, master, today, force, made)
        except Exception as ex:  # a kit must never break the daily email
            log.warning("kit for %s failed: %s", job.get("title"), ex)
    log.info("application kits created: %d", made)
    return jobs


def _make_one(job, master, today, force, made):
    """Create one kit; returns 1 if a new kit was made, else 0."""
    if job["score"] < MIN_SCORE or job.get("applied") == "applied" or made >= MAX_PER_RUN:
        return 0
    slug = f"{today}-{_slug(job['company'])}-{_slug(job['title'])}"
    existing = sorted(DIR.glob(f"*-{_slug(job['company'])}-{_slug(job['title'])}.md"))
    if existing and not force:  # kit already made on an earlier day
        job["kit"] = str(existing[-1].relative_to(ROOT))
        return 0
    german = job.get("lang") == "de"
    t = _call(PROMPT.format(
        master=yaml.safe_dump(master, allow_unicode=True, sort_keys=False), title=job["title"],
        company=job["company"], location=job["location"], lang="German" if german else "English",
        description=(job.get("description") or "")[:3000],
        de_rule=('the same structure as cover_en, written in professional German (Sie-Form), subject "Bewerbung als <Titel>", '
                 'logistics mentions "letzter Arbeitstag 15.12.2026"' if german else '{}')))
    if not t:
        return 0
    t = validate(master, _normalize(t))
    out = OUT / slug
    out.mkdir(parents=True, exist_ok=True)
    htmls = [out / "Kranti_Chavan_CV.html"]
    htmls[0].write_text(documents.render_cv(master, t))
    letters = [(lang, complete_letter(t.get(f"cover_{lang}"), lang, job)) for lang in (["en", "de"] if german else ["en"])]
    letters = [(lang, cl) for lang, cl in letters if cl]
    if not letters:
        log.warning("kit for %s skipped: incomplete letters", job["title"])
        return 0
    for lang, cl in letters:
        f = out / f"Kranti_Chavan_Cover_Letter_{lang.upper()}.html"
        f.write_text(documents.render_cover(master, cl, job, lang, t.get("headline") or master["headlines"][0]))
        htmls.append(f)
    try:
        files = documents.to_pdf(htmls)
    except Exception as ex:  # no browser available: send HTML instead (open in browser -> print to PDF)
        log.warning("PDF rendering failed, attaching HTML: %s", ex)
        files = [str(h) for h in htmls]
    flags = unverified_tech(master, [_cover_text(cl) for _, cl in letters])
    note = DIR / f"{slug}.md"
    note.write_text(render_note(job, t, files, flags))
    job["kit"] = str(note.relative_to(ROOT))
    # PDFs without her phone/email would look unfinished: only attach them once the secrets are set
    job["attachments"] = files if os.getenv("CANDIDATE_PHONE") and os.getenv("CANDIDATE_EMAIL") else []
    job["letters"] = dict(letters)  # completed letters, reused for the email application
    time.sleep(8)  # long answers: stay under free-tier tokens-per-minute
    return 1
