"""Application kits: tailored cover letter(s), CV focus points, LinkedIn note and email draft per strong job.

Nothing is ever sent or submitted automatically — the kit is a ready-to-review draft the candidate sends herself.
"""
import json
import logging
import os
import re
from datetime import date
from pathlib import Path

from . import score

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "applications"
MIN_SCORE = 80
MAX_PER_RUN = 8
log = logging.getLogger(__name__)

PROMPT = """You write job application material for this candidate. Accuracy rules (most important):
- Use ONLY facts from her profile. Never invent employers, numbers, projects, tools, certificates or practices.
- Keep her own verbs: do not upgrade "managed/developed/configured/executed" to "delivered/introduced/built from scratch/owned".
- Do not claim experience with anything the job asks for unless it is in her profile; say she is keen to learn it instead.
- All her jobs are PAST roles (Rockwell ended 09/2026); she is available immediately — never say "current role".
- German level is B1 — never claim more. Keep it specific to the job; no clichés.

Candidate profile:
{cv}

Job:
Title: {title}
Company: {company}
Location: {location}
Posting language: {lang}
Posting text (may be partial): {description}

Return ONLY a JSON object with these keys:
- "cover_letter_en": cover letter in English, 180-250 words, greeting "Dear Hiring Team," (or a named person if the
  posting names one), 3 short paragraphs (why this role/company, 2-3 matching experiences with concrete SAP Commerce
  details from her profile, availability: Karlsruhe, work permit, available immediately), closing "Kind regards,\\nKranti Chavan"
- "cover_letter_de": {de_rule}
- "cv_points": list of exactly 3 short bullet points: which of her experiences to put first for THIS job
- "linkedin_message": max 280 characters, to the recruiter or hiring manager, friendly and specific
- "email_subject": subject line for an email application
- "email_body": short email (60-90 words) introducing her and saying CV and cover letter are attached"""


def _call(prompt):
    for name, fn, key in (("gemini", score._gemini, "GEMINI_API_KEY"), ("groq", score._groq, "GROQ_API_KEY")):
        if not os.getenv(key):
            continue
        try:
            text = fn(prompt)
            return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        except Exception as e:
            log.warning("kit via %s failed: %s", name, e)
    return None


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50]


def render(job, k):
    lines = [f"# Application kit — {job['title']}", "",
             f"**{job['company']}** · {job['location'] or 'location n/a'} · score {job['score']} · "
             f"[open the job posting]({job['url']})", "",
             "> Read and adjust before sending. Replace [placeholders]. Attach your CV.", "",
             "## Put these first in your CV", ""] + [f"- {p}" for p in k.get("cv_points", [])][:3] + [
             "", "## Cover letter (English)", "", k.get("cover_letter_en", "").strip()]
    if k.get("cover_letter_de"):
        lines += ["", "## Anschreiben (Deutsch)", "",
                  "> Only use this if you are comfortable answering German questions in the interview.", "",
                  k["cover_letter_de"].strip()]
    lines += ["", "## LinkedIn message to the recruiter / team lead", "", k.get("linkedin_message", "").strip()]
    if job.get("contact"):
        lines += ["", f"## Email application → {job['contact']}", "",
                  f"**Subject:** {k.get('email_subject', '').strip()}", "", k.get("email_body", "").strip(), "",
                  "Kranti Chavan · Karlsruhe · [phone] · [email] · [LinkedIn]"]
    return "\n".join(lines) + "\n"


def make_kits(jobs, cv, today=None):
    """Create kit files for strong jobs; sets job['kit'] to the repo-relative path."""
    today = today or date.today().isoformat()
    DIR.mkdir(exist_ok=True)
    made = 0
    for job in sorted(jobs, key=lambda j: -j["score"]):
        if job["score"] < MIN_SCORE or job.get("applied") == "applied" or made >= MAX_PER_RUN:
            continue
        path = DIR / f"{today}-{_slug(job['company'])}-{_slug(job['title'])}.md"
        if not path.exists():
            k = _call(PROMPT.format(
                cv=cv, title=job["title"], company=job["company"], location=job["location"],
                lang="German" if job.get("lang") == "de" else "English", description=job["description"][:2500],
                de_rule=("the same cover letter in professional German (Sie-Form), closing 'Mit freundlichen Grüßen\\nKranti Chavan'"
                         if job.get("lang") == "de" else 'empty string ""')))
            if not k:
                continue
            path.write_text(render(job, k))
            made += 1
        job["kit"] = str(path.relative_to(ROOT))
    log.info("application kits created: %d", made)
    return jobs
