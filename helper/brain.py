"""The brain: an AI browser agent (browser-use + Gemini, Groq as fallback) that applies to ANY job page by itself.

helper/sites/* are the fast path (rules per ATS). Whenever they do not reach a confirmed submission (no form found,
unknown question, account wall, error, stuck), apply.run_job hands the job to apply_with_brain(), which looks at the
page like a person would: finds the job / the Apply button, logs in or registers, fills every step, uploads the PDFs,
ticks the consent boxes and submits. It stops (never solves) at a CAPTCHA.

    from helper import brain
    res = brain.apply_with_brain(url_or_page, kit, {"cv": cv_pdf, "cover": cl_pdf}, dry_run=False)
    # {"status": "submitted"|"would_submit"|"captcha"|"closed"|"account_needed"|"failed",
    #  "reason": ..., "steps": n, "final_url": ..., "seconds": s}

The agent attaches over CDP to the browser the helper already drives (apply.CDP_URL: her real Chrome, headed, on
Windows; headless Chromium in the dry run). Without a CDP URL it starts its own browser.
Keys: GEMINI_API_KEY (or GEMINI_API_KEY2 / BRAIN_GEMINI_API_KEY), GROQ_API_KEY (or BRAIN_GROQ_API_KEY).
Model: BRAIN_MODEL (default gemini-flash-latest, Google's alias for the newest free-tier Flash model).
"""
import asyncio
import json
import os
import re
import threading
import time
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_CLOUD_SYNC", "false")
os.environ.setdefault("BROWSER_USE_LOGGING_LEVEL", "warning")

ROOT = Path(__file__).resolve().parent.parent
MAX_STEPS = int(os.environ.get("BRAIN_MAX_STEPS", "40"))
MAX_SECONDS = int(os.environ.get("BRAIN_MAX_SECONDS", "360"))
STATUSES = ("submitted", "would_submit", "captcha", "closed", "account_needed", "failed")
FINAL_SUBMIT = re.compile(r"absenden|abschicken|einreichen|übermitteln|submit|send application|bewerbung senden|"
                          r"jetzt bewerben$|apply now$|finish|abschließen|bewerbung abschließen", re.I)
CONFIRM = re.compile(r"(vielen )?dank für (ihre|deine) bewerbung|bewerbung (wurde |ist )?(erfolgreich )?(eingegangen|"
                     r"versendet|übermittelt|abgeschickt|gesendet)|thank(s| you) for (your )?(applying|application|interest)|"
                     r"application (has been |was )?(successfully )?(submitted|received|sent)|we('ve| have) received your application|"
                     r"erfolgreich beworben|bewerbung erhalten", re.I)


def _key(*names):
    for n in names:
        if os.environ.get(n, "").strip():
            return os.environ[n].strip()
    return None


def _llms():
    """(primary, fallback): Gemini first, Groq when Gemini is rate-limited / down. Either may be missing."""
    from browser_use.llm.google.chat import ChatGoogle
    from browser_use.llm.groq.chat import ChatGroq
    g = _key("GEMINI_API_KEY", "GEMINI_API_KEY2", "BRAIN_GEMINI_API_KEY", "GOOGLE_API_KEY")
    q = _key("GROQ_API_KEY", "BRAIN_GROQ_API_KEY")
    gem = ChatGoogle(model=os.environ.get("BRAIN_MODEL", "gemini-flash-latest"), api_key=g, temperature=0.2) if g else None
    groq = ChatGroq(model=os.environ.get("BRAIN_GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct"),
                    api_key=q, temperature=0.2) if q else None
    if gem:
        return gem, groq
    if groq:
        return groq, None
    raise RuntimeError("brain: no GEMINI_API_KEY / GROQ_API_KEY in helper/me.env")


def _facts_text(kit):
    """Everything the agent may state about her. It must not invent anything beyond this."""
    j, t = kit["job"], kit.get("tailoring", {})
    facts = (ROOT / "profile" / "facts.yaml").read_text(encoding="utf-8")
    cv = (ROOT / "cv.md").read_text(encoding="utf-8")[:3500] if (ROOT / "cv.md").exists() else ""
    try:
        from hunter.kit import salary_answer
        salary = salary_answer({"salary": j.get("salary", "")})
    except Exception:
        salary = "60000 EUR gross per year (negotiable)"
    env = {k: os.environ.get(k, "") for k in ("CANDIDATE_EMAIL", "CANDIDATE_PHONE", "CANDIDATE_STREET", "CANDIDATE_POSTCODE")}
    lang = kit.get("lang") or j.get("lang") or "de"
    return f"""CANDIDATE (the only facts you may use — never invent anything else):
Name: Kranti Chavan (Frau / Ms, female). Email: {env['CANDIDATE_EMAIL']}. Phone: {env['CANDIDATE_PHONE']}.
Street: {env['CANDIDATE_STREET'] or '(not given: leave optional street fields empty)'}. Postcode: {env['CANDIDATE_POSTCODE'] or '76131'}.
City: Karlsruhe, Germany. LinkedIn: https://www.linkedin.com/in/kranti-chavan-84a155191
Salary expectation: {salary}. Earliest start 16.12.2026 (serving notice, last day 15.12.2026).
German level: B1. English C2. Disability: no. Work permit: valid German residence + work permit, no sponsorship.
How did you hear: Job board / LinkedIn. Posting language: {'German' if lang == 'de' else 'English'} — answer free text in it.
Why this company (use for motivation / free-text questions, 2-4 selling sentences): {t.get('why_company', '')}
Headline: {t.get('headline', '')}

profile/facts.yaml:
{facts}

CV summary (cv.md):
{cv}
"""


def _task(kit, start_url, files, dry_run, account_email, no_submit=False):
    j = kit["job"]
    stop = ("THIS IS A DRY RUN: do everything EXCEPT the final submit. As soon as the last page of the application is "
            "filled and the final submit/send button ('Absenden', 'Bewerbung senden', 'Submit application', ...) is "
            "visible and enabled, do NOT click it: call done with status would_submit. If an account (registration/"
            "login) is required to apply, do NOT create one: call done with status account_needed."
            if dry_run else
            "Do everything EXCEPT the final submit (the candidate clicks it herself): when the final submit button is "
            "visible and enabled, do NOT click it; call done with status would_submit."
            if no_submit else
            "Click the final submit button when everything is filled. Then wait for the confirmation / thank-you "
            "page and call done with status submitted only when a thank-you / 'application received' text is visible.")
    return f"""Apply for this job on behalf of the candidate and submit the application.
Job: "{j.get('title')}" at {j.get('company')} ({j.get('location', '')}). Posting: {j.get('url')}
Start page: {start_url}

HOW:
1. Accept cookie banners. If this is a job board / careers overview / company homepage, find THIS job (search the
   careers page by title, follow 'Apply on company website', 'Jetzt bewerben', 'Zur Bewerbung', 'Apply'). Ignore
   LinkedIn/XING/Indeed 'easy apply' and 'apply with profile' buttons; use the normal form (manual entry).
2. If the job says it is closed / no longer available / 404 and you cannot find it → done with status closed.
3. Fill every field of the form from the CANDIDATE facts. Multi-step forms: fill each step, then 'Weiter'/'Next'.
   Upload the CV to the CV/Lebenslauf/resume field and the cover letter to Anschreiben/cover letter/motivation fields
   with upload_file (paths below). If there is only one upload field, upload the CV. Photo fields: skip.
   Free-text 'why us / motivation / message' fields: 2-4 selling sentences from 'Why this company'.
   Unknown factual questions: choose the honest answer from the facts; never make up degrees, years or skills.
   Dropdowns: choose the closest option (salutation Frau/Ms, country Germany/Deutschland, German B1, disability no).
4. Tick ALL consent / privacy / data protection / talent-pool / keep-my-data checkboxes.
5. Accounts: if the site requires login or registration, register with email {account_email} and the password
   <secret>account_password</secret> (use exactly this placeholder in the password fields), then call save_account.
   If the account already exists, log in with the same. If the password is wrong, use 'forgot password', call
   get_email_code to get the reset link, open it, and set the same password again. Verification code or link by
   email → get_email_code(sender_hint=<company or ATS name>).
6. CAPTCHA (reCAPTCHA, hCaptcha, Cloudflare Turnstile, 'I'm not a robot', puzzle/image challenge) → STOP immediately
   and call done with status captcha. Never try to solve it.
7. {stop}

FILES (absolute paths for upload_file): CV: {files.get('cv')}   Cover letter: {files.get('cover')}

FINISH by calling done with text EXACTLY as JSON: {{"status": "<one of {', '.join(STATUSES)}>", "reason": "<short>"}}
Use failed only when you are truly stuck (explain why in reason).

{_facts_text(kit)}"""


def _tools(dry_run, site_holder):
    from browser_use import ActionResult, Tools
    tools = Tools()

    @tools.action("Wait for a verification email and return the code or link it contains. sender_hint: company or "
                  "ATS name (e.g. 'workday', 'personio', 'Siemens'). kind: 'code' or 'link'.")
    def get_email_code(sender_hint: str, kind: str = "code") -> ActionResult:
        if dry_run:
            return ActionResult(extracted_content="DRY RUN: no email access. Call done with status account_needed.")
        from helper import mailcodes
        since = time.time() - 300
        found = (mailcodes.wait_for_link(sender_hint, since_ts=since, timeout=150) if kind == "link"
                 else mailcodes.wait_for_code(sender_hint, since, timeout=150) or
                 mailcodes.wait_for_link(sender_hint, since_ts=since, timeout=20))
        return ActionResult(extracted_content=f"email {kind}: {found}" if found else "no email arrived (150 s)")

    @tools.action("Store the account you just created/used on this site (call right after registering or "
                  "resetting the password). site: the host name of the login page.")
    def save_account(site: str) -> ActionResult:
        if dry_run:
            return ActionResult(extracted_content="DRY RUN: not stored")
        from helper import vault
        vault.set(site, os.environ.get("CANDIDATE_EMAIL", ""), _password())
        site_holder.append(site)
        return ActionResult(extracted_content=f"account for {site} stored")
    return tools


def _password():
    from helper import vault
    return os.environ.get("ACCOUNT_PASSWORD", "").strip() or vault.new_password()


def _guard_submit(agent, dry_run, log):
    """Dry-run safety net: the agent's click on a final-submit button is refused (the prompt alone is not trusted)."""
    if not dry_run:
        return
    actions = agent.tools.registry.registry.actions
    reg = actions.get("click")
    if reg is None:
        return
    orig = reg.function

    async def guarded(params=None, **kw):
        from browser_use import ActionResult
        idx = getattr(params, "index", None)
        bs = kw.get("browser_session")
        if idx is not None and bs is not None:
            try:
                node = await bs.get_element_by_index(idx)
                label = (node.get_meaningful_text_for_llm() if node else "") or ""
                attrs = node.attributes if node else {}
                typ = (attrs or {}).get("type", "")
                if FINAL_SUBMIT.search(label.strip()[:60]) or (typ == "submit" and not re.search(
                        r"weiter|next|continue|fortfahren|search|suche|login|anmelden|register|registrier|cookie|accept|akzept", label, re.I)):
                    log(f"   brain: DRY RUN guard blocked click on '{label[:40]}'")
                    return ActionResult(extracted_content=(
                        f"DRY RUN: '{label[:40]}' looks like the final submit button: NOT clicked. If the form is complete,"
                        " call done with status would_submit now; if this is only a 'next step' button and more steps"
                        " follow, say so in your next thought and use send_keys or another element."), error=None)
            except Exception:
                pass
        return await orig(params=params, **kw)
    reg.function = guarded


def _parse(text):
    text = text or ""
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            if d.get("status") in STATUSES:
                return d["status"], str(d.get("reason", ""))[:300]
        except Exception:
            pass
    low = text.lower()
    for s in STATUSES:
        if s in low:
            return s, text[:300]
    return "failed", text[:300] or "no final answer"


async def _page_text(session):
    try:
        cdp = await session.get_or_create_cdp_session()
        r = await cdp.cdp_client.send.Runtime.evaluate(
            params={"expression": "document.body ? document.body.innerText.slice(0, 8000) : ''", "returnByValue": True},
            session_id=cdp.session_id)
        return r.get("result", {}).get("value", "") or ""
    except Exception:
        return ""


async def _run(start_url, kit, files, dry_run, cdp_url, headless, log, no_submit=False):
    from browser_use import Agent, BrowserSession
    primary, fallback = _llms()
    if cdp_url:
        session = BrowserSession(cdp_url=cdp_url, keep_alive=True)
    else:
        session = BrowserSession(headless=headless, keep_alive=False,
                                 executable_path=os.environ.get("PW_CHROMIUM") or None)
    sites = []
    t0 = time.time()

    def on_step(state, output, n):
        try:
            acts = [next(iter(a.model_dump(exclude_none=True).items())) for a in output.action]
            desc = "; ".join(f"{k}({json.dumps(v, ensure_ascii=False)[:70]})" for k, v in acts)
            goal = (output.next_goal or "")[:90] if hasattr(output, "next_goal") else ""
            log(f"   brain step {n} ({round(time.time() - t0)}s): {desc[:180]}" + (f"  — {goal}" if goal else ""))
        except Exception:
            pass

    files = {k: str(Path(v).resolve()) for k, v in files.items() if v}
    agent = Agent(
        task=_task(kit, start_url, files, dry_run, os.environ.get("CANDIDATE_EMAIL", ""), no_submit),
        llm=primary, fallback_llm=fallback, browser_session=session, tools=_tools(dry_run, sites),
        available_file_paths=list(files.values()), sensitive_data={"account_password": _password() if not dry_run else "dry-run"},
        initial_actions=[{"navigate": {"url": start_url, "new_tab": False}}],
        directly_open_url=False, use_vision=True, vision_detail_level="low", max_actions_per_step=4,
        use_thinking=False, use_judge=False, max_failures=4, step_timeout=90, llm_timeout=60,
        register_new_step_callback=on_step,
    )
    _guard_submit(agent, dry_run or no_submit, log)
    hist = None
    try:
        hist = await asyncio.wait_for(agent.run(max_steps=MAX_STEPS), timeout=MAX_SECONDS)
        status, reason = _parse(hist.final_result()) if hist.is_done() else ("failed", "step budget used up")
    except asyncio.TimeoutError:
        status, reason = "failed", f"time budget ({MAX_SECONDS}s) used up"
    except Exception as ex:
        status, reason = "failed", f"{type(ex).__name__}: {str(ex)[:200]}"
    text = await _page_text(session)
    if status == "submitted" and not CONFIRM.search(text):
        status, reason = "failed", "agent says submitted but no thank-you text is visible: " + reason
    if status == "would_submit" and not (dry_run or no_submit):
        status = "failed"
    final_url = ""
    try:
        final_url = await session.get_current_page_url()
    except Exception:
        pass
    steps = len(agent.history.history) if agent.history else 0
    try:
        if cdp_url:
            await session.stop() if hasattr(session, "stop") else None  # disconnect only (keep_alive)
        else:
            await session.kill()
    except Exception:
        pass
    return {"status": status, "reason": reason, "steps": steps, "final_url": final_url,
            "seconds": round(time.time() - t0), "accounts": sites}


def apply_with_brain(page_or_url, kit, files, dry_run=False, cdp_url=None, headless=None, log=print, no_submit=False):
    """Synchronous entry point (safe to call from Playwright's sync API: the agent runs in its own thread/loop).
    page_or_url: a Playwright page (its current URL is the start) or a URL. files: {"cv": path, "cover": path}."""
    url = page_or_url if isinstance(page_or_url, str) else page_or_url.url
    if not url or url == "about:blank":
        j = kit["job"]
        url = j.get("direct_url") or j.get("apply_url") or j["url"]
    if cdp_url is None:
        try:
            from helper import apply
            cdp_url = apply.CDP_URL
        except Exception:
            cdp_url = None
    headless = (os.environ.get("BRAIN_HEADLESS", "1" if os.name != "nt" else "0") == "1") if headless is None else headless
    out = {}

    def target():
        try:
            out.update(asyncio.run(_run(url, kit, files, dry_run, cdp_url, headless, log, no_submit)))
        except Exception as ex:
            out.update(status="failed", reason=f"{type(ex).__name__}: {str(ex)[:200]}", steps=0, final_url=url)
    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(MAX_SECONDS + 60)
    if not out:
        out.update(status="failed", reason="brain hung", steps=0, final_url=url)
    return out


if __name__ == "__main__":  # python -m helper.brain <kit.json> [--dry]: one job, own browser
    import sys
    kit = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    from helper.sites.base import TEST_CV, TEST_CL
    print(apply_with_brain(kit["job"].get("direct_url") or kit["job"]["url"], kit, {"cv": TEST_CV, "cover": TEST_CL},
                           dry_run="--dry" in sys.argv, cdp_url=None))
