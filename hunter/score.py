"""Score jobs 0-100 against cv.md. Gemini first, Groq second, keyword rules last."""
import json
import logging
import os
import re
import time

import requests

log = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
BATCH = 15

PROMPT = """You rate job postings for one candidate. Candidate profile:
{cv}

For each job below give:
- score: 0-100 fit (90+ = SAP Commerce/Hybris role she can do today; 60-89 = commerce/e-commerce role she could do or learn quickly; 30-59 = loosely related; <30 = not relevant)
- why: one short sentence (mention German-language requirement if it looks stricter than B1)

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


def _gemini(prompt):
    key = os.environ["GEMINI_API_KEY"]
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        params={"key": key},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt):
    key = os.environ["GROQ_API_KEY"]
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": GROQ_MODEL, "temperature": 0,
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
            try:
                results = _parse(call(PROMPT.format(cv=cv, jobs=listing)))
                break
            except Exception as e:  # rate limit, bad JSON, outage -> next provider
                log.warning("%s scoring failed: %s", name, e)
        for i, job in enumerate(batch):
            if results and i in results:
                job["score"] = int(results[i].get("score", 0))
                job["why"] = results[i].get("why", "")
            else:
                job["score"], job["why"] = _keyword_score(job)
        time.sleep(4)  # stay under free-tier rate limits
    return jobs
