"""Score jobs 0-100 against cv.md. Gemini first, Groq second, keyword rules last."""
import json
import logging
import os
import re
import time

import requests

log = logging.getLogger(__name__)

# Model names get retired often, so if the preferred one is gone we pick the
# best available one from the provider's model list at runtime.
GEMINI_PREFS = [os.getenv("GEMINI_MODEL", ""), "gemini-flash-latest", "gemini-2.5-flash", "flash"]
GROQ_PREFS = [os.getenv("GROQ_MODEL", ""), "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "gpt-oss", "llama"]
_models = {}
BATCH = 15

PROMPT = """You rate job postings for one candidate. Candidate profile:
{cv}

For each job below give:
- score: 0-100 fit, using this scale:
  90-100: SAP Commerce Cloud / Hybris / SAP CX Commerce / Spartacus role (developer, consultant, architect, lead, product owner)
  75-89: other SAP CX roles; Salesforce Commerce Cloud, commercetools, Spryker, Intershop, Adobe Commerce roles; Java backend for e-commerce; e-commerce business analyst / functional or technical consultant
  55-74: other e-commerce / PIM / shop roles that are technical or analytical (incl. PHP shops like Shopware/Magento)
  30-54: loosely related (generic IT, e-commerce marketing/operations)
  0-29: not relevant (warehouse, sales, customer service, accounting, non-IT)
  Subtract 10 if fluent/native German is clearly required (she has B1). Subtract 15 if the job is outside Germany and not remote.
- why: one short sentence

Return ONLY a JSON array: [{{"id": <id>, "score": <int>, "why": "<text>"}}, ...]

Jobs:
{jobs}"""

KEYWORD_POINTS = [
    (r"hybris|sap commerce|commerce cloud|ccv2|spartacus|composable storefront|sap cx", 50),
    (r"salesforce commerce|sfcc|demandware|commercetools|spryker|intershop|adobe commerce|magento|shopware", 30),
    (r"e-?commerce|digital commerce|onlineshop|webshop", 20),
    (r"developer|entwickler|engineer|consultant|berater|analyst|architect|product owner", 10),
    (r"java|spring|solr|impex|occ", 10),
    (r"karlsruhe|baden|stuttgart|mannheim|heidelberg|frankfurt|remote|home ?office", 10),
]


def _keyword_score(job):
    text = f"{job['title']} {job['description']} {job['location']}".lower()
    score = sum(p for rx, p in KEYWORD_POINTS if re.search(rx, text))
    return min(score, 100), "keyword match (AI scoring unavailable)"


def _pick(available, prefs):
    for p in filter(None, prefs):
        if p in available:
            return p
        match = sorted(m for m in available if p in m)
        if match:
            return match[-1]
    raise RuntimeError(f"no usable model among {available[:20]}")


def _gemini_candidates(key):
    """Usable Gemini models, preferred first. Some listed models 404 on generateContent
    (retired/restricted), so callers try them in order and drop the ones that fail."""
    if "gemini" not in _models:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200}, timeout=30)
        r.raise_for_status()
        names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini" in m["name"]
                 and not any(x in m["name"] for x in ("tts", "image", "live", "audio", "embedding", "preview", "exp"))]
        ordered = []
        for p in filter(None, GEMINI_PREFS):
            ordered += [n for n in sorted(names, reverse=True) if p in n and n not in ordered]
        _models["gemini"] = ordered
        log.info("gemini candidates: %s", ordered[:6])
    return _models["gemini"]


def _groq_model(key):
    if "groq" not in _models:
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        r.raise_for_status()
        names = [m["id"] for m in r.json()["data"] if m.get("active", True)
                 and not any(x in m["id"] for x in ("guard", "whisper", "tts", "orpheus", "safeguard"))]
        _models["groq"] = _pick(names, GROQ_PREFS)
        log.info("groq model: %s", _models["groq"])
    return _models["groq"]


def _gemini(prompt):
    key = os.environ["GEMINI_API_KEY"]
    candidates = _gemini_candidates(key)
    while candidates:
        model = candidates[0]
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
            timeout=90,
        )
        if r.status_code in (400, 403, 404):  # model unavailable for this key -> try the next one
            log.warning("gemini model %s unavailable (%s), trying next", model, r.status_code)
            candidates.pop(0)
            continue
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise RuntimeError("no working Gemini model")


def _groq(prompt):
    key = os.environ["GROQ_API_KEY"]
    model = _groq_model(key)
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse(text):
    m = re.search(r"\[.*\]", text, re.S)
    return {int(x["id"]): x for x in json.loads(m.group(0))}


def score_jobs(jobs, cv):
    providers = [(n, f) for n, f, k in [("gemini", _gemini, "GEMINI_API_KEY"), ("groq", _groq, "GROQ_API_KEY")]
                 if os.getenv(k)]
    for start in range(0, len(jobs), BATCH):
        batch = jobs[start:start + BATCH]
        listing = "\n".join(
            f"id={i} | {j['title']} | {j['company']} | {j['location']} | remote={j['remote']} | {j['description'][:600]}"
            for i, j in enumerate(batch))
        results = None
        for name, call in providers:
            for attempt in range(3):
                try:
                    results = _parse(call(PROMPT.format(cv=cv, jobs=listing)))
                    break
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code == 429 and attempt < 2:
                        time.sleep(30)  # free-tier rate limit, wait and retry
                        continue
                    log.warning("%s scoring failed: %s", name, e)
                    break
                except Exception as e:  # bad JSON, outage -> next provider
                    log.warning("%s scoring failed: %s", name, e)
                    break
            if results:
                break
        for i, job in enumerate(batch):
            if results and i in results:
                job["score"] = int(results[i].get("score", 0))
                job["why"] = results[i].get("why", "")
            else:
                job["score"], job["why"] = _keyword_score(job)
        time.sleep(4)  # stay under free-tier rate limits
    return jobs
