"""AI answers for free-text / opinion / motivation questions in application forms (approved by Kranti).

answer_free(question, job, lang, required=False, kind="textarea") -> str | None
  - fixed facts first (helper/answers.py) - this module is only for what facts.yaml cannot answer
  - factual questions not in facts.yaml (GitHub, portfolio, website ...): "" when optional, her LinkedIn URL when a
    required URL field, None (= park) for an uncovered yes/no question
  - everything else: Gemini, then Groq (hunter/score.py), keys GEMINI_API_KEY / GROQ_API_KEY from helper/me.env.
    The prompt allows ONLY cv.md + profile/facts.yaml + the job's tailoring.why_company; nothing invented.
Every AI answer is appended to helper/ai_answers.log (question, answer) for review. Cached per question text.
Tests can set ai_answer.LLM = lambda prompt: '{"answer": "..."}' to stub the providers.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = Path(__file__).resolve().parent / "ai_answers.log"
LLM = None  # test stub: f(prompt) -> text
_CACHE = {}

URL_Q = re.compile(r"\burl\b|github|gitlab|portfolio|website|webseite|homepage|\blink\b|stack ?overflow|blog|xing", re.I)
YES_NO_Q = re.compile(r"^\s*(are|do|did|have|has|will|would|can|could|is|were|bist|sind|haben|hast|können|kannst|würden|"
                      r"wärst|waren|darf|dürfen)\b|\b(yes|no|ja|nein)\s*/\s*(no|yes|nein|ja)\b", re.I)
FACTUAL_Q = re.compile(r"\b(github|gitlab|portfolio|website|webseite|homepage|blog|twitter|xing|stack ?overflow|"
                       r"address|adresse|straße|street|birth|geburt|reference|referenz)\b", re.I)


def _llm(prompt):
    if LLM is not None:
        return LLM(prompt)
    from hunter import score
    errors = []
    for name, fn, key in (("gemini", score._gemini, "GEMINI_API_KEY"), ("groq", score._groq, "GROQ_API_KEY")):
        if not os.environ.get(key):
            continue
        try:
            return fn(prompt) if name == "gemini" else fn(prompt, json_object=True)
        except Exception as ex:
            errors.append(f"{name}: {ex}")
    raise RuntimeError("no AI provider worked (" + ("; ".join(errors) or "GEMINI_API_KEY / GROQ_API_KEY missing in helper/me.env") + ")")


def _context():
    cv = (ROOT / "cv.md").read_text(encoding="utf-8")
    facts = (ROOT / "profile" / "facts.yaml").read_text(encoding="utf-8")
    return cv, facts


def prompt_for(question, job, lang):
    cv, facts = _context()
    job = job or {}
    j = job.get("job", job)
    why = (job.get("tailoring") or {}).get("why_company", "")
    language = "German (Sie-form, natural business German)" if lang == "de" else "English"
    return f"""You fill in a job application form as the candidate Kranti Chavan (first person, "I").
Answer this form question in {language}, 2-4 sentences, confident and selling, specific to the role.

QUESTION: {question}
ROLE: {j.get('title', '')} at {j.get('company', '')}
WHY THIS COMPANY (written for her, may be reused): {why or '(none)'}

STRICT RULES:
- Use ONLY facts from the CV and FACTS below and the WHY THIS COMPANY text. Never invent anything: no numbers,
  percentages, team sizes, projects, clients, certificates, tools or language levels that are not written there.
- Do not claim German above B1. No salary or dates unless they are in FACTS.
- If the question asks for a fact that is not in CV/FACTS (a URL, a reference, an address ...), answer "".
- Plain text, no markdown, no greeting, no signature.
Return JSON only: {{"answer": "..."}}

CV:
{cv}

FACTS:
{facts}
"""


def _parse(text):
    try:
        m = re.search(r"\{.*\}", text or "", re.S)
        return str(json.loads(m.group(0)).get("answer", "")).strip() if m else (text or "").strip()
    except Exception:
        return (text or "").strip().strip('"')


def log_answer(question, answer, source="ai"):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] ({source}) Q: {re.sub(r'\s+', ' ', question)[:300]}\n"
                    f"    A: {re.sub(r'\s+', ' ', answer)}\n")
    except Exception:
        pass


def answer_free(question, job=None, lang="en", required=False, kind="textarea"):
    """Answer for a question facts.yaml cannot answer. "" = leave empty, None = park (unknown yes/no / AI failed)."""
    q = re.sub(r"\s+", " ", (question or "").split(" | ")[0]).strip(" *")
    if len(q) < 4:
        return None
    if q in _CACHE:
        return _CACHE[q]
    from helper import answers
    f = answers.facts()
    if kind == "url" or URL_Q.search(q) and kind != "textarea" or FACTUAL_Q.search(q) and len(q) < 60:
        # a fact we do not have: optional -> empty; required URL -> her LinkedIn; anything else required -> park
        res = "" if not required else (f["linkedin"] if (kind == "url" or URL_Q.search(q)) else None)
        if res:
            log_answer(q, res, "linkedin-fallback")
        _CACHE[q] = res
        return res
    if YES_NO_Q.search(q) and kind != "textarea":
        _CACHE[q] = None  # a yes/no question facts.yaml does not cover: a human decides
        return None
    try:
        res = _parse(_llm(prompt_for(q, job, lang)))
    except Exception as ex:
        print(f"     (AI answer failed: {str(ex)[:120]})")
        return None
    res = re.sub(r"\s+", " ", res).strip()
    if not res:
        res = None if required else ""
    else:
        log_answer(q, res)
    _CACHE[q] = res
    return res
