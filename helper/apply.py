"""Windows application helper: opens each job in a real Chrome window, fills the application form, uploads the
tailored CV and cover letter, and waits. You check the form and click Submit yourself.

Start with start.bat (or: python -m helper.apply). AUTO mode: it clicks "Apply/Bewerben", fills every field it
knows and uploads both PDFs by itself (again after each page change), and when the site shows its thank-you /
confirmation page it logs the job in APPLIED.md and opens the next one. You only check and click Submit.
Keys in this window (no Enter needed):
  f  fill again now          a  I submitted it (if no confirmation was detected) -> log, next job
  s  skip this job           q  quit
"""
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
OUT = ROOT / "out" / "helper"
SKIPPED = HERE / "skipped.txt"
AUTO = False  # AUTO_SUBMIT=1 in me.env: submit by itself when the form is complete and safe


def load_env():
    """helper/me.env holds phone and email (git-ignored)."""
    f = HERE / "me.env"
    if not f.exists():
        sys.exit(f"Missing {f}. Copy me.env.example to me.env and fill in phone and email.")
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def queue(days=45):
    """Kits not yet applied to (email ledger, APPLIED.md, skipped), best score first."""
    from hunter import applied
    data = applied.load()
    ledger = json.loads((ROOT / "data" / "applications.json").read_text()) if (ROOT / "data" / "applications.json").exists() else {}
    emailed = {v["url"] for v in ledger.values()}
    skipped = set(SKIPPED.read_text().split()) if SKIPPED.exists() else set()
    applied_md = (ROOT / "APPLIED.md").read_text(encoding="utf-8") if (ROOT / "APPLIED.md").exists() else ""
    via_form = {m.group(1) for m in re.finditer(r"(\S+) \([^)]*applied via form\)", applied_md)}
    since = (date.today() - timedelta(days=days)).isoformat()
    kits, seen = [], set()
    for f in sorted((ROOT / "applications").glob("*.json"), reverse=True):  # newest kit per job wins
        k = json.loads(f.read_text(encoding="utf-8"))
        if not k.get("lang") or k.get("skip"):
            continue  # older kit, or job closed / not in Germany  # older kit, written before the final selling standard
        j = k["job"]
        if j["url"] in seen or k.get("created", "") < since:
            continue
        seen.add(j["url"])
        # emailed jobs stay in the list: every job is ALSO applied to on the company website
        if j["url"] in skipped or j["url"] in via_form or (applied.status(j, data) == "applied" and j["url"] not in emailed):
            continue
        kits.append(k)
    # LinkedIn recruiter posts (no form: message the recruiter) go last
    return sorted(kits, key=lambda k: (k["job"]["title"].startswith("[Post]"), -int(k["job"].get("score") or 0)))


def build_pdfs(kit):
    """Render CV + cover letter (posting language) with her real contact data and photo."""
    import yaml
    from hunter import documents
    master = yaml.safe_load((ROOT / "profile" / "master.yaml").read_text(encoding="utf-8"))
    j, t = kit["job"], kit["tailoring"]
    lang = kit.get("lang") or ("de" if j.get("lang") == "de" and "de" in kit["letters"] else "en")
    lang = lang if lang in kit["letters"] else next(iter(kit["letters"]))
    slug = re.sub(r"[^a-z0-9]+", "-", f"{j['company']}-{j['title']}".lower())[:60]
    out = OUT / slug
    out.mkdir(parents=True, exist_ok=True)
    cv = out / documents.file_name("cv", j, lang).replace(".pdf", ".html")
    cl = out / documents.file_name("cl", j, lang).replace(".pdf", ".html")
    cv.write_text(documents.render_cv(master, t, lang if kit.get("lang") else "en"), encoding="utf-8")
    cl.write_text(documents.render_cover(master, kit["letters"][lang], j, lang,
                                         t.get("headline") or master["headlines"][0]), encoding="utf-8")
    pdfs = documents.to_pdf([cv, cl])
    return pdfs[0], pdfs[1], letter_text(kit["letters"][lang], lang), lang


def letter_text(cl, lang):
    sign = "Mit freundlichen Grüßen" if lang == "de" else "Kind regards,"
    parts = [cl["salutation"], cl["hook"]] + [f"- {b['label']}: {b['text']}" for b in cl["bullets"][:4]]
    parts += [cl.get("gap", ""), cl["logistics"], f"{sign}\nKranti Chavan"]
    return "\n\n".join(p for p in parts if p)


def answers(kit, lang):
    from hunter.kit import salary_answer
    sal = salary_answer({"salary": kit["job"].get("salary", "")})
    sal_num = re.search(r"€([\d,]+)", sal).group(1).replace(",", "")
    phone = os.environ["CANDIDATE_PHONE"]
    # (label pattern, value). First match wins; patterns are checked against the field's label text.
    return [
        (r"first.?name|vorname|given.?name", "Kranti"),
        (r"last.?name|nachname|surname|family.?name", "Chavan"),
        (r"^(full.?)?name\b|^ihr name|vollständiger name|^name\s*\*?$", "Kranti Chavan"),
        (r"e-?mail", os.environ["CANDIDATE_EMAIL"]),
        (r"phone|telefon|mobil|handy|tel\.?\b", phone),
        (r"linkedin", "https://www.linkedin.com/in/kranti-chavan-84a155191"),
        (r"\b(city|ort|stadt|wohnort|location|standort)\b", "Karlsruhe"),
        (r"postal|postleitzahl|\bplz\b|zip", "76131"),
        (r"\bcountry\b|\bland\b", "Germany" if lang == "en" else "Deutschland"),
        (r"salary|gehalt|vergütung|compensation", sal_num),
        (r"earliest|start.?date|eintritt|verfügbar|available|availability|starttermin", "16.12.2026"),
        (r"notice|kündigungsfrist", "Serving notice, last working day 15.12.2026" if lang == "en"
         else "Gekündigt, letzter Arbeitstag 15.12.2026"),
        (r"how did you hear|wie (sind sie|bist du).*aufmerksam|quelle|source", "Job board / LinkedIn"),
        (r"work.?permit|arbeitserlaubnis|visa|sponsorship", "Valid German residence & work permit, no sponsorship needed"),
    ]


SALUTATION = re.compile(r"anrede|salutation|\btitle\b|prefix", re.I)
SKIP_LABEL = re.compile(r"captcha|password|passwort|search|suche|gender|geschlecht|anrede|salutation|title|titel|"
                        r"birth|geburt|newsletter", re.I)
WHY_LABEL = re.compile(r"\bwhy\b|warum|wieso|interest in|interesse", re.I)
LETTER_LABEL = re.compile(r"cover|anschreiben|motivation|message|nachricht|additional information|zusätzliche", re.I)


LABEL_JS = """e => {
  const t = [];
  if (e.labels) for (const l of e.labels) t.push(l.innerText);
  t.push(e.getAttribute('aria-label') || '', e.placeholder || '');
  const lb = e.getAttribute('aria-labelledby');
  if (lb) for (const id of lb.split(' ')) { const x = document.getElementById(id); if (x) t.push(x.innerText); }
  if (t.join('').trim().length < 3) t.push((e.name || '').replace(/[_\\-\\[\\]]/g, ' '), e.id || '');
  let p = e.closest('div,fieldset,li,label');
  for (let i = 0; i < 2 && p && t.join('').trim().length < 3; i++) { t.push(p.innerText.slice(0, 120)); p = p.parentElement; }
  return t.join(' | ').replace(/\\s+/g, ' ').trim();
}"""


def fill(page, kit, cv, letter, text, lang, uploaded=None):
    """Fill every empty, visible field we have a confident answer for. Never clicks Submit."""
    rules = [(re.compile(p, re.I), v) for p, v in answers(kit, lang)]
    filled, unknown = [], []
    files_done = uploaded if uploaded is not None else set()  # kept per page: upload each file once
    for frame in page.frames:
        for el in frame.query_selector_all("input, textarea, select"):
            try:
                kind = (el.get_attribute("type") or el.evaluate("e => e.tagName")).lower()
                if kind in ("hidden", "submit", "button", "checkbox", "radio", "image", "reset"):
                    continue
                label = el.evaluate(LABEL_JS)
                if kind == "file":
                    target = letter if LETTER_LABEL.search(label) else cv
                    if target in files_done and target == cv and letter not in files_done:
                        target = letter  # second upload field without a clear label -> cover letter
                    if target not in files_done:
                        el.set_input_files(target)
                        files_done.add(target)
                        filled.append(f"upload {Path(target).name}")
                    continue
                if kind == "select" and el.is_visible() and SALUTATION.search(label):
                    if el.evaluate("e => e.selectedIndex > 0 && e.value !== ''"):
                        continue  # already chosen
                    for opt in ("Frau", "Ms.", "Ms", "Mrs.", "Mrs"):
                        try:
                            el.select_option(label=opt)
                            filled.append(f"{label[:30]} = {opt}")
                            break
                        except Exception:
                            pass
                    continue
                if not el.is_visible() or SKIP_LABEL.search(label):
                    continue
                if kind == "select":
                    if re.search(r"country|land", label, re.I):
                        for opt in ("Germany", "Deutschland", "DE"):
                            try:
                                el.select_option(label=opt)
                                filled.append(f"{label[:30]} = {opt}")
                                break
                            except Exception:
                                pass
                    continue
                if el.input_value().strip():
                    continue
                if kind == "textarea" and WHY_LABEL.search(label) and kit["tailoring"].get("why_company"):
                    el.fill(kit["tailoring"]["why_company"])
                    filled.append(f"{label[:30]} = why-this-company text")
                    continue
                if kind == "textarea" and LETTER_LABEL.search(label):
                    el.fill(text)
                    filled.append(f"{label[:30]} = cover letter text")
                    continue
                for rx, value in rules:
                    if rx.search(label):
                        el.fill(value)
                        filled.append(f"{label.split(' | ')[0][:40]} = {value}")
                        break
                else:
                    if el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true":
                        unknown.append(label[:60])
            except Exception:
                continue
    return filled, unknown


APPLY_BTN = re.compile(r"bewerben|bewerbung starten|zur bewerbung|apply|ich bin interessiert|i'?m interested", re.I)
NOT_APPLY = re.compile(r"initiativ|unsolicited|linkedin|xing|indeed|später|later|merken|save|teilen|share", re.I)
COOKIE_BTN = re.compile(r"^\s*(alle )?(akzeptieren|zustimmen|einverstanden|accept( all)?( cookies)?|allow all|"
                        r"alle cookies akzeptieren|ok|verstanden|agree)\s*!?\s*$", re.I)


def accept_cookies(page):
    for frame in page.frames:
        try:
            loc = frame.get_by_role("button")
            for i in range(min(loc.count(), 40)):
                el = loc.nth(i)
                if el.is_visible() and COOKIE_BTN.search(el.inner_text(timeout=500) or ""):
                    el.click(timeout=2000)
                    return True
        except Exception:
            continue
    return False


CONFIRM = re.compile(r"(vielen )?dank für ihre bewerbung|bewerbung (wurde |ist )?(erfolgreich )?(eingegangen|"
                     r"übermittelt|versendet|abgeschickt)|thank you for (your )?appl|application (has been )?"
                     r"(submitted|received|sent)|we have received your application|successfully (submitted|applied)", re.I)


def click_apply(page):
    """Click an obvious Apply / Bewerben button once (job pages that show the form only after it)."""
    for loc in (page.get_by_role("link"), page.get_by_role("button")):
        try:
            for i in range(min(loc.count(), 80)):
                el = loc.nth(i)
                t = (el.inner_text(timeout=500) or "").strip()
                if len(t) <= 40 and el.is_visible() and APPLY_BTN.search(t) and not NOT_APPLY.search(t):
                    el.click(timeout=3000)
                    return True
        except Exception:
            continue
    return False


SUBMIT_BTN = re.compile(r"^\s*(bewerbung )?(jetzt )?(absenden|abschicken|senden|einreichen|übermitteln)|"
                        r"^\s*(submit|send)( (my |your )?application)?\s*$|^\s*apply( now)?\s*$|"
                        r"^\s*(jetzt )?bewerben\s*$", re.I)
NEXT_BTN = re.compile(r"^\s*(weiter|next|continue|fortfahren|nächster schritt)\s*$", re.I)
CONSENT = re.compile(r"datenschutz|privacy|data protection|einwillig|consent|zustimm|agree|akzeptier|"
                     r"terms|bedingungen|dsgvo|gdpr", re.I)
NO_TICK = re.compile(r"newsletter|talent ?pool|talentpool|marketing|werbung|future (jobs|opportunit)|"
                     r"weitere (stellen|angebote)|job alert", re.I)
BLOCKER = re.compile(r"captcha|recaptcha|hcaptcha|turnstile|i'?m not a robot|ich bin kein roboter", re.I)


def tick_consent(page):
    """Tick required privacy/terms boxes only (never newsletter / talent pool)."""
    n = 0
    for frame in page.frames:
        for el in frame.query_selector_all("input[type=checkbox]"):
            try:
                label = el.evaluate(LABEL_JS)
                required = el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true"
                if not el.is_checked() and CONSENT.search(label) and not NO_TICK.search(label) and \
                        (required or re.search(r"datenschutz|privacy|data protection|dsgvo|gdpr", label, re.I)):
                    try:
                        el.check(timeout=2000)
                    except Exception:
                        el.evaluate("e => e.click()")
                    n += 1
            except Exception:
                continue
    return n


def problems(page, uploads_needed, uploaded):
    """Reasons not to submit automatically ([] = safe)."""
    why = []
    for frame in page.frames:
        try:
            if frame.query_selector("iframe[src*=captcha], iframe[src*=turnstile], .g-recaptcha, .h-captcha") or \
                    BLOCKER.search(frame.inner_text("body", timeout=1000)[:20000]):
                why.append("CAPTCHA")
                break
        except Exception:
            pass
    for frame in page.frames:
        for el in frame.query_selector_all("input, textarea, select"):
            try:
                kind = (el.get_attribute("type") or el.evaluate("e => e.tagName")).lower()
                req = el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true"
                if not req or kind in ("hidden", "submit", "button", "file") or not el.is_visible():
                    continue
                if kind in ("checkbox", "radio"):
                    if kind == "checkbox" and not el.is_checked():
                        why.append("unticked: " + el.evaluate(LABEL_JS)[:40])
                    continue
                if not el.input_value().strip():
                    why.append("empty: " + el.evaluate(LABEL_JS)[:40])
            except Exception:
                continue
    if uploads_needed and not uploaded:
        why.append("files not attached")
    if page.query_selector("input[type=password]"):
        why.append("account/password")
    return why


def click_button(page, rx):
    for frame in page.frames:
        for loc in (frame.get_by_role("button"), frame.locator("input[type=submit]")):
            try:
                for i in range(min(loc.count(), 60)):
                    el = loc.nth(i)
                    text = el.inner_text(timeout=500) if el.evaluate("e => e.tagName") != "INPUT" else el.get_attribute("value")
                    if el.is_visible() and el.is_enabled() and rx.search(text or ""):
                        el.click(timeout=5000)
                        return True
            except Exception:
                continue
    return False


def confirmed(ctx):
    for p in ctx.pages:
        try:
            if CONFIRM.search(p.inner_text("body", timeout=1000)[:20000]):
                return True
        except Exception:
            continue
    return False


def key_pressed():
    """Non-blocking key read (Windows); returns '' when no key was pressed."""
    try:
        import msvcrt
        return msvcrt.getwch().lower() if msvcrt.kbhit() else ""
    except ImportError:  # not Windows: fall back to a blocking prompt
        return input("   [f]ill [a]pplied [s]kip [q]uit > ").strip().lower()[:1]


def log_applied(kit):
    j = kit["job"]
    f = ROOT / "APPLIED.md"
    line = f"- {date.today().isoformat()} {j['url']} ({j['company']}, applied via form)\n"
    text = f.read_text(encoding="utf-8")
    if j["url"] not in text:
        f.write_text(text.rstrip("\n") + "\n" + line, encoding="utf-8")
    try:  # share with the daily hunter so it stops suggesting this job
        subprocess.run(["git", "-C", str(ROOT), "add", "APPLIED.md"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-m", f"applied: {j['company']}"], capture_output=True)
        subprocess.run(["git", "-C", str(ROOT), "pull", "--rebase", "-q"], capture_output=True, timeout=60)
        subprocess.run(["git", "-C", str(ROOT), "push", "-q"], capture_output=True, timeout=60)
    except Exception:
        print("   (saved locally; could not push to GitHub — that's fine)")


def main():
    global AUTO
    load_env()
    AUTO = os.environ.get("AUTO_SUBMIT") == "1"
    print("AUTO SUBMIT is ON" if AUTO else "Review mode (AUTO_SUBMIT=1 in me.env submits by itself)")
    from playwright.sync_api import sync_playwright
    kits = queue()
    print(f"\n{len(kits)} jobs waiting for an application (best first).\n")
    if not kits:
        return
    with sync_playwright() as pw:
        kwargs = dict(user_data_dir=str(HERE / ".browser"), headless=False, viewport=None, accept_downloads=True)
        try:  # her installed Chrome looks like a normal person to job sites
            ctx = pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
        except Exception:
            ctx = pw.chromium.launch_persistent_context(**kwargs)
        parked = []
        for n, kit in enumerate(kits, 1):
            j = kit["job"]
            print("=" * 70)
            print(f"[{n}/{len(kits)}]  score {j['score']}  {j['title']}\n           {j['company']} · {j['location']}")
            cv, letter, text, lang = build_pdfs(kit)
            page = ctx.new_page()
            try:
                page.goto(j.get("direct_url") or j.get("apply_url") or j["url"], timeout=60000)
            except Exception as ex:
                print(f"   could not open the page ({ex}); open it by hand: {j['url']}")
            import time
            page.wait_for_timeout(2500)
            accept_cookies(page)
            if click_apply(page):
                page.wait_for_timeout(2500)
            print("   AUTO: filling + uploading. Check, tick the privacy box, click Submit.  keys: f a s q")
            seen, last_fill, nxt, uploads, tries = {}, 0.0, None, {}, 0
            already = confirmed(ctx)  # a thank-you text on the job page itself must not count
            while nxt is None:
                active = ctx.pages[-1]  # the newest tab: job sites often open the form in a new tab
                try:
                    sig = (active.url, len(active.frames), active.locator("input, textarea, select").count())
                except Exception:
                    sig = None
                key = key_pressed()
                if key == "f" or (sig and seen.get(id(active)) != sig and time.time() - last_fill > 2):
                    seen[id(active)] = sig
                    last_fill = time.time()
                    filled, unknown = fill(active, kit, cv, letter, text, lang, uploads.setdefault(active.url.split("?")[0], set()))
                    if filled or key == "f":
                        print(f"   filled {len(filled)} fields" + (": " + ", ".join(x[:25] for x in filled[:8]) if filled else ""))
                        for x in unknown:
                            print(f"     ✗ please fill yourself: {x}")
                if AUTO and last_fill and not key and time.time() - last_fill > 3 and tries < 4:
                    tries += 1
                    tick_consent(active)
                    files_here = active.query_selector("input[type=file]") is not None
                    why = problems(active, files_here, uploads.get(active.url.split("?")[0]))
                    if why:
                        if tries >= 3:
                            parked.append(f"{j['company']} · {j['title'][:40]} · {', '.join(why[:3])} · {active.url}")
                            print("   ⏸ parked for you: " + ", ".join(why[:3]))
                            nxt = "next"
                            continue
                    elif click_button(active, SUBMIT_BTN) or click_button(active, NEXT_BTN):
                        print("   → clicked submit/next")
                        active.wait_for_timeout(4000)
                        seen.pop(id(active), None)
                if key == "a" or (last_fill and not already and confirmed(ctx)):
                    log_applied(kit)
                    print("   ✅ confirmation seen → logged as applied, next job")
                    nxt = "next"
                elif key == "s":
                    with open(SKIPPED, "a", encoding="utf-8") as f:
                        f.write(j["url"] + "\n")
                    nxt = "next"
                elif key == "q":
                    ctx.close()
                    return
                else:
                    time.sleep(1)
            for p in ctx.pages[:-1] if len(ctx.pages) > 1 else []:
                p.close()
        ctx.close()
    if parked:
        (HERE / "parked.txt").write_text("\n".join(parked) + "\n", encoding="utf-8")
        print(f"\n⏸ {len(parked)} jobs need you (also in helper/parked.txt):")
        for x in parked:
            print("   " + x)
    print("\nAll done for today. 🎉")


if __name__ == "__main__":
    main()
