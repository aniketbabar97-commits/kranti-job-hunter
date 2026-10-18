"""Windows application helper: opens each job in a real Chrome window, fills the application form, uploads the
tailored CV and cover letter, and waits. You check the form and click Submit yourself.

Start with start.bat (or: python -m helper.apply). AUTO mode: it detects the ATS (helper/sites), clicks
"Apply/Bewerben", fills every field it knows (fixed answers: profile/facts.yaml via helper/answers.py), ticks every
checkbox, uploads both PDFs, walks "Next" steps, clicks Submit when nothing is missing, and when the site shows its
thank-you page it logs the job in APPLIED.md and opens the next one. Parked only for a CAPTCHA, an account/password
step, or a question with no fixed answer (then logged to helper/questions.txt).
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
    # company-site forms first (fully automatic), then portals that need her login, then likely closed ones
    order = {"": 0, "arbeitsagentur": 1, "indeed": 2, "linkedin_easy": 3, "maybe_closed": 4}
    return sorted(kits, key=lambda k: (order.get(k["job"].get("channel", ""), 0), k["job"]["title"].startswith("[Post]"),
                                       -int(k["job"].get("score") or 0)))


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
        (r"^(full.?)?name\b|^(ihr|dein|your) name|vollständiger name|vor-? und nachname|^name\s*\*?", "Kranti Chavan"),
        (r"first.?name|vorname|given.?name|^first\b", "Kranti"),
        (r"last.?name|nachname|surname|family.?name|^last\b", "Chavan"),
        (r"e-?mail|mailadresse|^mail\b", os.environ["CANDIDATE_EMAIL"]),
        (r"phone|telefon|rufnummer|mobil|handy|tel\.?\b", phone),
        (r"linkedin", "https://www.linkedin.com/in/kranti-chavan-84a155191"),
        (r"\b(city|ort|stadt|wohnort|location|standort)\b", "Karlsruhe"),
        (r"postal|postleitzahl|\bplz\b|zip", "76131"),
        (r"\bcountry\b|\bland\b", "Germany" if lang == "en" else "Deutschland"),
        (r"salary|gehalt|vergütung|compensation", sal_num),
        (r"earliest|start.?date|eintritt|verfügbar|available|availability|starttermin|ab wann|when can you start|"
         r"frühest|(kannst|können|könnten) (du|sie) (bei uns )?(starten|anfangen|beginnen)", "16.12.2026"),
        (r"notice|kündigungsfrist", "Serving notice, last working day 15.12.2026" if lang == "en"
         else "Gekündigt, letzter Arbeitstag 15.12.2026"),
        (r"how did you hear|wie (sind sie|bist du).*aufmerksam|aufmerksam geworden|quelle|source|herkunft\\b", "Job board / LinkedIn"),
        (r"work.?permit|arbeitserlaubnis|visa|sponsorship", "Valid German residence & work permit, no sponsorship needed"),
    ]


SALUTATION = re.compile(r"anrede|salutation|\btitle\b|prefix", re.I)
SKIP_LABEL = re.compile(r"captcha|password|passwort|search|suche|anrede|salutation|\btitle\b|titel|"
                        r"birth|geburt|confirm.?e-?mail|e-?mail.*(wiederhol|bestätig)|^website$|honeypot|for robots|if you.?re (a )?human|"
                        r"leave (this )?(field )?(blank|empty)", re.I)
WHY_LABEL = re.compile(r"\bwhy\b|warum|wieso|interest in|interesse", re.I)
LETTER_LABEL = re.compile(r"cover|anschreiben|motivation|message|nachricht|additional information|zusätzliche", re.I)
PHOTO_LABEL = re.compile(r"photo|foto|\bbild\b|picture|portrait", re.I)
REQUIRED_LABEL = re.compile(r"\*|\(required\)|\(pflichtfeld\)|\brequired\b|\bpflicht", re.I)
PLACEHOLDER_OPT = re.compile(r"^(-+\s*)?((please )?(select|choose|pick)\b.{0,30}|bitte (aus)?wählen.{0,20}|-+|none selected|"
                             r"keine auswahl|)(\s*-+)?$", re.I)


def is_required(el, label=""):
    try:
        if el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true":
            return True
    except Exception:
        pass
    return REQUIRED_LABEL.search((label or "").split(" | ")[0]) is not None


def answer_for(label, lang):
    """A fixed answer from profile/facts.yaml (helper/answers.py); None = unknown (logged)."""
    from helper import answers as _answers
    return _answers.answer(label, lang)


def ai_for(label, kit, lang, required=False, kind="text"):
    """Free-text / motivation answer (helper/ai_answer.py, cached per question, logged). "" = leave empty, None = park."""
    from helper import ai_answer
    return ai_answer.answer_free(label, kit, lang, required, "textarea" if kind == "textarea" else
                                 ("url" if kind == "url" else "text"))


def pick_option(el, want, label=""):
    """Choose the <select> option matching a wanted answer (yes/no, Germany, Female, ...). True when chosen."""
    from helper import answers as _answers
    opts = el.evaluate("e => [...e.options].map(o => [o.label || o.text, o.value])")
    if _answers.is_yes(want):
        rx = re.compile(r"^\s*(yes|ja)\b", re.I)
    elif _answers.is_no(want):
        rx = re.compile(r"^\s*(no|nein|keine?)\b", re.I)
    else:
        rx = re.compile(re.escape(str(want).split(",")[0].strip()[:25]), re.I)
    hits = [o for o in opts if rx.search(o[0] or "") and not PLACEHOLDER_OPT.match(o[0] or "")]
    if not hits:
        hits = [o for o in opts if (o[0] or "").lower() in str(want).lower() and len(o[0] or "") > 2]
    if not hits and "/" in str(want):  # "Job board / LinkedIn": try each part
        for part in str(want).split("/"):
            part = part.strip()
            if part and pick_option(el, part, label):
                return True
    if len({h[0] for h in hits}) != 1:
        return False
    el.select_option(value=hits[0][1])
    return True


LABEL_JS = """e => {
  const t = [];
  if (e.labels) for (const l of e.labels) t.push(l.innerText);
  t.push(e.getAttribute('aria-label') || '', e.placeholder || '');
  const lb = e.getAttribute('aria-labelledby');
  if (lb) for (const id of lb.split(' ')) { const x = document.getElementById(id); if (x) t.push(x.innerText); }
  if (t.join('').trim().length < 3) {  // no label: the question wrapper's first text line (Lever, Workday, custom forms)
    const q = e.closest('.application-question, .field, .form-group, .question, [class*=question], [class*=field], fieldset, li, label');
    const lab = q && (q.querySelector('.application-label, legend, label, [class*=label]'));
    const txt = (lab ? lab.innerText : (q ? q.innerText : '')).trim().split('\\n')[0];
    if (txt) t.push(txt.slice(0, 160));
  }
  if (t.join('').trim().length < 3) t.push((e.name || '').replace(/[_\\-\\[\\]]/g, ' '), e.id || '');
  let p = e.closest('div,fieldset,li,label');
  for (let i = 0; i < 2 && p && t.join('').trim().length < 3; i++) { t.push(p.innerText.slice(0, 120)); p = p.parentElement; }
  return t.join(' | ').replace(/\\s+/g, ' ').trim();
}"""
def qsa(frame, sel):
    """frame.query_selector_all that survives a frame detaching mid-fill (consent / tracking iframes reload)."""
    try:
        return frame.query_selector_all(sel)
    except Exception:
        return []


PHONE_PREFIX_ONLY = re.compile(r"^\s*\+?\d{1,4}\s*$")  # "+49": the widget's country code, not a number


def fill(page, kit, cv, letter, text, lang, uploaded=None):
    """Fill every empty, visible field we have a confident answer for. Never clicks Submit."""
    rules = [(re.compile(p, re.I), v) for p, v in answers(kit, lang)]
    filled, unknown = [], []
    files_done = uploaded if uploaded is not None else set()  # kept per page: upload each file once
    for frame in page.frames:
        for el in qsa(frame, "input, textarea, select"):
            try:
                kind = (el.get_attribute("type") or el.evaluate("e => e.tagName")).lower()
                if kind in ("hidden", "submit", "button", "checkbox", "radio", "image", "reset"):
                    continue
                label = el.evaluate(LABEL_JS)
                if kind == "file":
                    if PHOTO_LABEL.search(label):
                        photo = ROOT / "profile" / "photo.jpg"
                        if photo.exists() and str(photo) not in files_done and is_required(el, label):
                            el.set_input_files(str(photo))
                            files_done.add(str(photo))
                            filled.append("upload photo.jpg")
                        continue
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
                if el.evaluate("e => e.matches(%s)" % json.dumps(REACT_SELECT_INPUT)):
                    continue  # react-select search box: handled by fill_react_selects
                if kind == "select":
                    if el.evaluate("e => e.selectedIndex > 0 && e.value !== ''") and \
                            not PLACEHOLDER_OPT.match(el.evaluate("e => e.options[e.selectedIndex].text") or ""):
                        continue  # already chosen
                    if re.search(r"country|land", label, re.I) and not re.search(r"code|vorwahl", label, re.I):
                        for opt in ("Germany", "Deutschland", "DE"):
                            try:
                                el.select_option(label=opt)
                                filled.append(f"{label[:30]} = {opt}")
                                break
                            except Exception:
                                pass
                        continue
                    want = answer_for(label, lang) if is_required(el, label) or len(label) > 3 else None
                    if not want:
                        want = next((v for rx, v in rules if rx.search(label.split(" | ")[0])), None)
                    if want and pick_option(el, want, label):
                        filled.append(f"{label.split(' | ')[0][:30]} = {want[:20]}")
                    elif POSITION_LABEL.search(label.split(" | ")[0]) and (opt := pick_position(el, kit["job"].get("title", ""))):
                        filled.append(f"{label.split(' | ')[0][:30]} = {opt[:30]}")
                    elif is_required(el, label):
                        unknown.append(label[:60])
                    continue
                if el.input_value().strip() and not (kind == "tel" and PHONE_PREFIX_ONLY.match(el.input_value())):
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
                    required = is_required(el, label)
                    value = answer_for(label, lang) if (required or len(label.split(' | ')[0]) > 6) else None
                    if not value and (kind in ("textarea", "url") or required or "?" in label.split(" | ")[0]):
                        value = ai_for(label, kit, lang, required, kind)  # free text: AI from cv.md + facts only
                        if value == "":
                            continue  # optional fact we do not have (GitHub, portfolio): leave empty
                    if value:
                        el.fill(value)
                        filled.append(f"{label.split(' | ')[0][:40]} = {value[:30]}")
                    elif required:
                        unknown.append(label[:60])
            except Exception:
                continue
    filled += fill_radios(page, lang)
    filled += fill_react_selects(page, lang, unknown)
    return filled, unknown


POSITION_LABEL = re.compile(r"position|stelle|bereich|vacancy|job\b|ausschreibung|role|abteilung", re.I)


def pick_position(el, title):
    """"Which position / area are you applying for" dropdown: the option closest to the job title (or the only one)."""
    from helper.sites.own import overlap
    opts = [o for o in el.evaluate("e => [...e.options].map(o => [o.label || o.text, o.value])")
            if o[1] and not PLACEHOLDER_OPT.match(o[0] or "")]
    if not opts:
        return None
    best = max(opts, key=lambda o: overlap(title, o[0]))
    if len(opts) > 1 and overlap(title, best[0]) < 0.34:
        return None
    el.select_option(value=best[1])
    return best[0]


REACT_SELECT_INPUT = "input.select__input, input[id^=react-select][id$='-input'], input[role=combobox][aria-autocomplete=list]"
REACT_SELECT_OPTION = "[class*=select__option], [class*=-option], [role=option]"


def fill_react_selects(page, lang, unknown):
    """react-select style dropdowns (Greenhouse new boards, softgarden, many custom forms): open, type, pick.
    Answer from facts; typeahead fields (school, country) take the first suggestion for the typed answer."""
    from helper import answers as _answers
    done = []
    for frame in page.frames:
        for el in qsa(frame, REACT_SELECT_INPUT):
            try:
                if not el.is_visible():
                    continue
                has_value = el.evaluate("e => { let c = e; for (let i = 0; i < 6 && c; i++) { if (c.querySelector('[class*=single-value], [class*=singleValue], [class*=multi-value]')) return true; "
            "if (c.matches('[class*=select__container], [class*=select-shell]') && i > 2) break; c = c.parentElement; } return false; }")
                if has_value:
                    continue
                label = el.evaluate(LABEL_JS)
                if SKIP_LABEL.search(label) or re.search(r"language.?select|sprache wählen|ccm-", label, re.I):
                    continue
                want = _answers.answer(label, lang)
                if not want:
                    if is_required(el, label):
                        unknown.append(label[:60])
                    continue
                if _answers.is_yes(want):
                    typed, rx = ("Ja" if lang == "de" else "Yes"), re.compile(r"^\s*(yes|ja)\b", re.I)
                elif _answers.is_no(want):
                    typed, rx = ("Nein" if lang == "de" else "No"), re.compile(r"^\s*(no|nein|none|keine?)\b", re.I)
                else:
                    typed = str(want).split(",")[0].strip()[:30]
                    rx = re.compile(re.escape(typed[:12]), re.I)
                el.click()
                frame.wait_for_timeout(300)
                opts = [o for o in frame.query_selector_all(REACT_SELECT_OPTION) if o.is_visible()]
                hit = [o for o in opts if rx.search(o.inner_text() or "") and not PLACEHOLDER_OPT.match(o.inner_text() or "")]
                if not hit:
                    el.type(typed, delay=40)
                    frame.wait_for_timeout(1200)
                    opts = [o for o in frame.query_selector_all(REACT_SELECT_OPTION) if o.is_visible()]
                    hit = [o for o in opts if rx.search(o.inner_text() or "")] or opts[:1]
                if hit and not re.search(r"no (options|results)|keine (optionen|ergebnisse)", hit[0].inner_text() or "", re.I):
                    chosen = hit[0].inner_text().strip()
                    hit[0].click()
                    frame.wait_for_timeout(300)
                    done.append(f"{label.split(' | ')[0][:30]} = {chosen[:20]}")
                else:
                    frame.keyboard.press("Escape")
                    if is_required(el, label):
                        unknown.append(label[:60])
            except Exception:
                try:
                    frame.keyboard.press("Escape")
                except Exception:
                    pass
                continue
    return done


RADIO_GROUP_JS = """e => { const g = e.closest('fieldset, [role=radiogroup], .form-group, .field, .question, div');
  const l = g && (g.querySelector('legend') || g.querySelector('label:not(:has(input))') || g);
  return (l ? l.innerText : '').split('\\n')[0].slice(0, 160); }"""


def fill_radios(page, lang):
    """Radio groups: pick the option matching the fixed answer (disability no, relocation yes, ...)."""
    from helper import answers as _answers
    done, groups = [], {}
    for frame in page.frames:
        for el in qsa(frame, "input[type=radio]"):
            try:
                if not el.is_visible():
                    continue
                groups.setdefault((id(frame), el.get_attribute("name") or el.evaluate(RADIO_GROUP_JS)), []).append(el)
            except Exception:
                continue
    for _, els in groups.items():
        try:
            if any(e.is_checked() for e in els):
                continue
            question = els[0].evaluate(RADIO_GROUP_JS)
            want = _answers.answer(question, lang)
            if not want:
                continue
            if _answers.is_yes(want):
                rx = re.compile(r"^\s*(yes|ja)\b", re.I)
            elif _answers.is_no(want):
                rx = re.compile(r"^\s*(no|nein|keine?)\b", re.I)
            else:
                rx = re.compile(re.escape(str(want)[:25]), re.I)
            hits = [e for e in els if rx.search(e.evaluate(LABEL_JS).split(" | ")[0] or e.get_attribute("value") or "")]
            if len(hits) == 1:
                try:
                    hits[0].check(timeout=2000)
                except Exception:
                    hits[0].evaluate("e => e.click()")
                done.append(f"{question[:30]} = {want[:15]}")
        except Exception:
            continue
    return done


APPLY_BTN = re.compile(r"bewerben|bewerbung starten|zur bewerbung|apply|ich bin interessiert|i'?m interested", re.I)
NOT_APPLY = re.compile(r"initiativ|unsolicited|linkedin|xing|indeed|später|later|merken|save|teilen|share", re.I)
COOKIE_BTN = re.compile(r"^\s*(alles? |alle cookies )?(akzeptieren|zustimmen|einverstanden|accept( all)?( cookies)?|allow all|"
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
# her rule: every box is a yes (privacy, terms, talent pool, keep my data, newsletter) - except a box that would
# claim a disability, and the cookie banner's own purpose boxes (accept_cookies handles those)
NEVER_TICK = re.compile(r"disab|behinder|schwerbehind|handicap|^ccm-|cookie|analyse|statistik|social media", re.I)
BLOCKER = re.compile(r"i'?m not a robot|ich bin kein roboter|anti-roboter|verify you are human|bestätigen sie, dass sie "
                     r"ein mensch sind|security check|sicherheitsüberprüfung", re.I)
CAPTCHA_FRAME = "iframe[src*=captcha], iframe[src*=turnstile], iframe[src*=captcha-delivery], .g-recaptcha, .h-captcha, .cf-turnstile"


MY_LANGS = re.compile(r"^\s*(english|englisch|german|deutsch|hindi|marathi)\b", re.I)


def tick_consent(page):
    """Tick every visible, unticked checkbox (privacy, terms, talent pool, keep my data, newsletter: all yes)."""
    n = 0
    for frame in page.frames:
        boxes = qsa(frame, "input[type=checkbox], [role=checkbox][aria-checked=false]")
        names = [b.get_attribute("name") or "" for b in boxes]
        for el in boxes:
            try:
                label = el.evaluate(LABEL_JS)
                name = (el.get_attribute("name") or el.get_attribute("id") or "")
                if name and names.count(name) > 2:  # a multi-choice question, not a consent box
                    if MY_LANGS.search(label.split(" | ")[0]) and not el.is_checked():
                        el.check(timeout=2000)  # "which languages do you speak": hers only
                        n += 1
                    continue
                if NEVER_TICK.search(label.split(" | ")[0]) or NEVER_TICK.search(name) or not el.is_visible():
                    continue
                if el.evaluate("e => e.tagName") == "INPUT" and el.is_checked():
                    continue
                try:
                    el.check(timeout=2000)
                except Exception:
                    el.evaluate("e => e.click()")
                n += 1
            except Exception:
                continue
    return n


def captcha_visible(page):
    """A CAPTCHA that actually challenges (visible widget / interstitial), not a passive invisible script."""
    for frame in page.frames:
        try:
            for el in frame.query_selector_all(CAPTCHA_FRAME):
                box = el.bounding_box()
                badge = el.evaluate("e => !!e.closest('.grecaptcha-badge')")  # invisible reCAPTCHA's corner badge
                if box and box["height"] >= 70 and box["width"] >= 70 and el.is_visible() and not badge:
                    return True
            if "captcha-delivery.com" in frame.url or BLOCKER.search(frame.inner_text("body", timeout=1000)[:20000]):
                return True
        except Exception:
            continue
    return False


def problems(page, uploads_needed, uploaded):
    """Reasons not to submit automatically ([] = safe)."""
    why = []
    if captcha_visible(page):
        why.append("CAPTCHA")
    for frame in page.frames:
        all_els = qsa(frame, "input, textarea, select")
        groups = {}
        for el in all_els:
            try:
                if el.get_attribute("type") == "checkbox" and el.get_attribute("name"):
                    groups.setdefault(el.get_attribute("name"), []).append(el)
            except Exception:
                pass
        for el in all_els:
            try:
                kind = (el.get_attribute("type") or el.evaluate("e => e.tagName")).lower()
                if kind in ("hidden", "submit", "button", "file") or not el.is_visible():
                    continue
                if el.evaluate("e => e.matches(%s)" % json.dumps(REACT_SELECT_INPUT)) or \
                        "requiredInput" in (el.get_attribute("class") or ""):
                    # react-select: the search box is always empty; a chosen value shows as single-value
                    if not el.evaluate("e => { let c = e; for (let i = 0; i < 6 && c; i++) { if (c.querySelector('[class*=single-value], [class*=singleValue], [class*=multi-value]')) return true; "
            "if (c.matches('[class*=select__container], [class*=select-shell]') && i > 2) break; c = c.parentElement; } return false; }") \
                            and is_required(el, el.evaluate(LABEL_JS)) and "requiredInput" not in (el.get_attribute("class") or ""):
                        why.append("empty: " + el.evaluate(LABEL_JS)[:40])
                    continue
                label = el.evaluate(LABEL_JS)
                grp = groups.get(el.get_attribute("name") or "", [])
                if kind == "checkbox" and len(grp) > 2:
                    if el is grp[0] and is_required(el, label) and not any(g.is_checked() for g in grp):
                        why.append("unanswered choice: " + label[:40])
                    continue
                if not is_required(el, label) or SKIP_LABEL.search(label):
                    continue
                if kind in ("checkbox", "radio"):
                    if kind == "checkbox" and not el.is_checked():
                        why.append("unticked: " + label[:40])
                    continue
                if kind == "select":
                    if not el.evaluate("e => e.selectedIndex > 0 && e.value !== ''"):
                        why.append("empty: " + label[:40])
                    continue
                if not el.input_value().strip():
                    why.append("empty: " + label[:40])
            except Exception:
                continue
    from helper.sites.base import Site
    if not why and find_button(page, SUBMIT_BTN) is None and Site.has_form(Site, page) and (dis := disabled_submit(page)):
        why.append("CAPTCHA (invisible check keeps Submit disabled)" if dis == "captcha" else "Submit stays disabled")
    if uploads_needed and not uploaded:
        why.append("files not attached")
    if page.query_selector("input[type=password]"):
        why.append("account/password")
    return why


def disabled_submit(page):
    """'captcha' / 'disabled' when the only Submit on screen is disabled (a Turnstile / hCaptcha check that did not
    pass, or a field the filler cannot see), else None."""
    for frame in page.frames:
        for el in qsa(frame, "button, input[type=submit]"):
            try:
                text = el.inner_text() if el.evaluate("e => e.tagName") != "INPUT" else el.get_attribute("value")
                if el.is_visible() and not el.is_enabled() and SUBMIT_BTN.search(text or ""):
                    turnstile = any(re.search(r"turnstile|hcaptcha|recaptcha|friendlycaptcha", f.url or "") for f in page.frames)
                    return "captcha" if turnstile else "disabled"
            except Exception:
                continue
    return None


def find_button(page, rx):
    """The first visible, enabled button (or input[type=submit]) whose text matches rx - without clicking."""
    for frame in page.frames:
        for loc in (frame.get_by_role("button"), frame.locator("input[type=submit]")):
            try:
                for i in range(min(loc.count(), 60)):
                    el = loc.nth(i)
                    text = el.inner_text(timeout=500) if el.evaluate("e => e.tagName") != "INPUT" else el.get_attribute("value")
                    if el.is_visible() and el.is_enabled() and rx.search(text or ""):
                        return el
            except Exception:
                continue
    return None


def click_button(page, rx):
    el = find_button(page, rx)
    if el is None:
        return False
    try:
        el.click(timeout=5000)
        return True
    except Exception:
        return False


def confirmed(ctx, site=None):
    rx = (site.confirm_regex if site is not None and site.confirm_regex else None) or CONFIRM
    for p in ctx.pages:
        try:
            if site is not None and hasattr(site, "confirmed") and site.confirmed(p):
                return True
            if site is not None and getattr(site, "confirm_by_text", True) is False:
                continue  # the site keeps its thank-you text in the DOM all the time: only site.confirmed() counts
            text = p.inner_text("body", timeout=1000)[:20000]
            if rx.search(text) or (rx is not CONFIRM and CONFIRM.search(text)):
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


def log_applied(kit, ats="own", page=None, proof_seen=True, mode="auto"):
    """Proof page seen -> screenshot, submissions.json 'confirmed', APPLIED.md line '(Company, website via helper – confirmed)'.
    No proof -> 'pending' in submissions.json only (hunter/inbox.py confirms it from the receipt mail, or lists it under
    'Please check' after 24 h). Also updates the per-ATS trust store. Returns 'confirmed' or 'pending'."""
    from helper import proof, trust
    j = kit["job"]
    state = proof.log_submission(j, ats, page, proof_seen, mode)
    trust.record(ats, state == "confirmed")
    return state


CLOSED_TEXT = re.compile(r"no longer (available|accepting|active|open)|nicht mehr (verfügbar|aktiv|online|ausgeschrieben)|"
                         r"(stelle|position|anzeige|stellenanzeige|job) (ist |wurde )?(bereits )?(besetzt|geschlossen|deaktiviert)|"
                         r"job (has been |is )?(closed|expired|filled)|position has been filled|has expired|abgelaufen|"
                         r"seite (wurde )?nicht gefunden|page (was )?not found|\b404\b.{0,40}(not found|nicht gefunden)|"
                         r"job (is )?not (found|available)|stellenangebot existiert nicht", re.I)


def page_closed(page):
    try:
        return CLOSED_TEXT.search(page.inner_text("body", timeout=1500)[:6000]) is not None
    except Exception:
        return False


def run_job(ctx, kit, n, total, parked, rec=None):
    """One job, start to end (the loop start.bat runs). rec: DRY_RUN record dict (filled in place).
    Returns 'next' or 'quit'."""
    import time
    from helper import sites, trust
    rec = rec if rec is not None else {}
    j = kit["job"]
    print("=" * 70)
    print(f"[{n}/{total}]  score {j['score']}  {j['title']}\n           {j['company']} · {j['location']}")
    cv, letter, text, lang = build_pdfs(kit)
    page = ctx.new_page()
    start = j.get("direct_url") or j.get("apply_url") or j["url"]
    rec.update(start_url=start, reached_form=False, filled=0, uploads=[], unanswered=[], problems=[], steps=0,
               notes=[], outcome=None)
    try:
        page.goto(start, timeout=60000)
    except Exception as ex:
        print(f"   could not open the page ({ex}); open it by hand: {j['url']}")
        rec["notes"].append(f"goto failed: {str(ex)[:100]}")
    page.wait_for_timeout(2500)
    accept_cookies(page)
    site = sites.detect(page.url, page)
    rec["ats"] = site.name
    print(f"   ATS: {site.name}")
    already = confirmed(ctx, site)  # a thank-you text on the job page itself must not count
    if site.already_applied(page):
        print("   already applied here earlier → logged, next job")
        rec["outcome"] = "ALREADY_APPLIED"
        if not DRY_RUN:
            log_applied(kit, site.name, page, False, "auto")
        return "next"
    if site.name == "own" and not site.has_form(page):  # generic careers page: search the job there first
        from helper.sites.own import find_job
        try:
            page, found, note = find_job(page, j["title"], j.get("company", ""))
            print(f"   job search on the careers page: {note}")
            rec["notes"].append("find_job: " + note)
            site = sites.detect(page.url, page)
            rec["ats"] = site.name
        except Exception as ex:
            print(f"   job search on the careers page failed ({ex})")
            rec["notes"].append(f"find_job failed: {str(ex)[:100]}")
    try:
        rec["reached_form"] = bool(site.open_form(page))
    except Exception as ex:
        print(f"   could not reach the form by itself ({ex}); click Apply yourself")
        rec["notes"].append(f"open_form failed: {str(ex)[:100]}")
    print("   AUTO: filling + uploading" + (" and submitting" if AUTO else ". Check and click Submit") + ".  keys: f a s q")
    seen, last_fill, nxt, uploads, tries, steps = {}, 0.0, None, {}, 0, 0
    ats = trust.detect(ctx.pages[-1].url or j["url"])
    if ats == "own" and site.name != "own":
        ats = site.name
    assisted = trust.mode(ats) == trust.ASSISTED and not DRY_RUN  # first job per ATS: fill, stop at Submit, she clicks
    if AUTO and assisted:
        print(f"   ASSISTED ({ats}): I fill everything and stop at Submit. Press  a  after you clicked Submit.")
    while nxt is None:
        active = ctx.pages[-1]  # the newest tab: job sites often open the form in a new tab
        if active is not page and site.name == "own":
            site = sites.detect(active.url, active)  # the form opened in a new tab on another host
            rec["ats"] = site.name
        try:
            sig = (active.url, len(active.frames), active.locator("input, textarea, select").count())
        except Exception:
            sig = None
        key = "" if DRY_RUN else key_pressed()
        if key == "f" or (sig and seen.get(id(active)) != sig and time.time() - last_fill > 2):
            seen[id(active)] = sig
            last_fill = time.time()
            accept_cookies(active)
            filled, unknown = site.fill(active, kit, cv, letter, text, lang, uploads.setdefault(active.url.split("?")[0], set()))
            tick_consent(active)
            rec["filled"] += len([x for x in filled if not x.startswith("upload")])
            rec["uploads"] += [x[7:] for x in filled if x.startswith("upload")]
            rec["unanswered"] = sorted(set(rec["unanswered"]) | set(unknown))
            if filled and not rec["reached_form"] and site.has_form(active):
                rec["reached_form"] = True
            if filled or key == "f":
                print(f"   filled {len(filled)} fields" + (": " + ", ".join(x[:25] for x in filled[:8]) if filled else ""))
                for x in unknown:  # no fixed answer in profile/facts.yaml -> logged in helper/questions.txt
                    print(f"     ✗ no answer known (see helper/questions.txt): {x}")
        if AUTO and not assisted and last_fill and not key and time.time() - last_fill > 3 and tries < 4:
            tries += 1
            ats = trust.detect(active.url) if trust.detect(active.url) != "own" else ats
            tick_consent(active)
            files_here = active.query_selector("input[type=file]") is not None
            why = site.problems(active, files_here, uploads.get(active.url.split("?")[0]))
            rec["problems"] = why
            if why:
                if tries >= 3:
                    parked.append(f"{j['company']} · {j['title'][:40]} · {', '.join(why[:3])} · {active.url}")
                    print("   ⏸ parked for you: " + ", ".join(why[:3]))
                    nxt = "next"
                    continue
            elif (btn := site.find_button(active, site.rx("submit"))) is not None:
                if DRY_RUN:
                    try:
                        label = (btn.inner_text(timeout=500) or btn.get_attribute("value") or "").strip()
                    except Exception:
                        label = "?"
                    print(f"   DRY_RUN: would submit ('{label[:30]}')")
                    rec["notes"].append(f"would submit: {label[:30]}")
                    rec["outcome"] = "WOULD_SUBMIT"
                    nxt = "next"
                    continue
                try:
                    btn.click(timeout=5000)
                    clicked = True
                except Exception:
                    clicked = False
                if clicked:
                    print("   → clicked submit")
                    active.wait_for_timeout(5000)
                    seen.pop(id(active), None)
            elif steps < 8 and site.click_next(active):  # multi-step form: next page, re-fill
                steps, tries = steps + 1, 0
                rec["steps"] = steps
                print("   → next step")
                active.wait_for_timeout(3500)
                seen.pop(id(active), None)
        if DRY_RUN and nxt is None and tries >= 4:
            nxt = "next"  # nothing left to do on this page: no problem, no Submit, no Next
            rec["notes"].append("no submit/next button found")
            continue
        if key == "a" or (last_fill and not already and confirmed(ctx, site)):
            if DRY_RUN:
                rec["notes"].append("confirmation text seen without submitting")
                nxt = "next"
                continue
            seen_page = not already and confirmed(ctx, site)
            state = log_applied(kit, ats, active, seen_page, "assisted" if assisted else "auto")
            print("   ✅ confirmation page seen → logged as applied (screenshot in out/proof), next job" if state == "confirmed"
                  else "   ⏳ no confirmation page → pending; the hunter confirms it from the receipt mail (or asks you to check)")
            nxt = "next"
        elif key == "s":
            with open(SKIPPED, "a", encoding="utf-8") as f:
                f.write(j["url"] + "\n")
            nxt = "next"
        elif key == "q":
            return "quit"
        else:
            time.sleep(1)
    try:
        active = ctx.pages[-1]
        rec["final_url"] = active.url
        if rec["outcome"] is None:
            rec["outcome"] = classify(rec, active)
    except Exception:
        pass
    if not DRY_RUN:
        for p in ctx.pages[:-1] if len(ctx.pages) > 1 else []:
            p.close()
    return "next"


def classify(rec, page):
    why = " ".join(rec["problems"])
    if "CAPTCHA" in why:
        return "PARK_CAPTCHA"
    if "account/password" in why or any("would create account" in x for x in rec["notes"]):
        return "PARK_ACCOUNT"
    if rec["problems"]:
        return "PARK_QUESTION"
    if page_closed(page):
        return "CLOSED"
    if not rec["filled"] and not rec["uploads"]:
        return "NO_FORM"
    if page_closed(page):
        return "CLOSED"
    if not rec["reached_form"] and not rec["filled"]:
        return "NO_FORM"
    return "PARK_QUESTION"


# ---------------------------------------------------------------------- DRY RUN (DRY_RUN=1)
DRY_RUN = os.environ.get("DRY_RUN") == "1"
DRY_OUT = Path(os.environ.get("DRY_OUT", "/tmp/claude-0/s/batch/dryrun.jsonl"))
DRY_NOTES = []  # "would create account at <site>" etc., collected by the patched side-effects


def dry_patch():
    """Every side effect becomes a no-op: no vault account, no Gmail polling, no APPLIED.md/submissions/trust/proof,
    no questions/answers log. PDFs: the test pair (TEST_CV / TEST_CL)."""
    import tempfile
    from helper import answers as _answers, ai_answer, mailcodes, proof, trust, vault
    from helper.sites import base
    tmp = Path(tempfile.mkdtemp(prefix="dryrun-"))
    _answers.QUESTIONS = tmp / "questions.txt"
    ai_answer.LOG = tmp / "answers.txt"
    os.environ["VAULT_KEY"] = "dry-run-only"
    vault.VAULT = tmp / "vault.enc"
    vault.get = lambda site: None

    def no_vault_set(site, email, password):
        DRY_NOTES.append(f"would create account at {site}")
        raise RuntimeError(f"DRY_RUN: would create account at {site}")
    vault.set = no_vault_set
    mailcodes._poll = lambda *a, **k: None
    proof.log_submission = lambda *a, **k: "dry"
    trust.record = lambda *a, **k: None
    from helper.sites import all_sites
    for s in all_sites():
        if hasattr(s, "ensure_account"):
            def ensure(page, _s=s):
                host = page.url.split("://", 1)[-1].split("/", 1)[0]
                DRY_NOTES.append(f"would create account at {host}")
                return False
            s.ensure_account = ensure
    global build_pdfs
    build_pdfs = lambda kit: (base.TEST_CV, base.TEST_CL, letter_text(
        kit["letters"].get(kit.get("lang")) or next(iter(kit["letters"].values())), kit.get("lang") or "en"),
        kit.get("lang") if kit.get("lang") in kit["letters"] else next(iter(kit["letters"])))


def dry_one(args):
    """Worker process: own headless browser, one job, hard timeout. Returns the record."""
    n, total, kit, timeout = args
    import signal
    import time
    global AUTO
    AUTO = True
    dry_patch()
    j = kit["job"]
    rec = {"n": n, "company": j.get("company"), "title": j.get("title"), "channel": j.get("channel", ""), "ats": None}
    t0 = time.time()

    def boom(*_):
        raise TimeoutError(f"job timeout {timeout}s")
    signal.signal(signal.SIGALRM, boom)
    signal.alarm(timeout)
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM", "/opt/pw-browsers/chromium"), headless=True)
            ctx = b.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE", accept_downloads=True)
            try:
                run_job(ctx, kit, n, total, [], rec)
                if rec.get("outcome") is None:
                    rec["outcome"] = classify(rec, ctx.pages[-1])
            finally:
                try:
                    rec.setdefault("final_url", ctx.pages[-1].url)
                except Exception:
                    pass
                signal.alarm(0)
                try:
                    b.close()
                except Exception:
                    pass
    except Exception as ex:
        rec["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
        if rec.get("outcome") is None:
            rec["outcome"] = "ERROR"
    signal.alarm(0)
    rec["notes"] = rec.get("notes", []) + DRY_NOTES
    if any("would create account" in x for x in DRY_NOTES) and rec["outcome"] in ("NO_FORM", "PARK_QUESTION", "ERROR"):
        rec["outcome"] = "PARK_ACCOUNT"
    rec["seconds"] = round(time.time() - t0)
    return rec


def dry_main(only=None, workers=4, timeout=240):
    """DRY_RUN=1 python -m helper.apply [n ...]: the whole queue (or jobs n...), 4 browsers in parallel."""
    import multiprocessing as mp
    os.environ.setdefault("CANDIDATE_EMAIL", "test@example.com")
    os.environ.setdefault("CANDIDATE_PHONE", "+49 000 0000000")
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    kits = queue()
    jobs = [(n, len(kits), k, timeout) for n, k in enumerate(kits, 1) if not only or n in only]
    DRY_OUT.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if only else "w"
    import time
    with open(DRY_OUT, mode, encoding="utf-8") as out, mp.get_context("spawn").Pool(workers, maxtasksperchild=1) as pool:
        pending = {a[0]: (a, pool.apply_async(dry_one, (a,)), None) for a in jobs}
        while pending:  # a hung browser can swallow SIGALRM: the parent enforces the limit too
            for n, (a, res, t0) in list(pending.items()):
                if t0 is None and not res.ready():
                    continue
                if res.ready():
                    try:
                        rec = res.get()
                    except Exception as ex:
                        rec = {"n": n, "company": a[2]["job"].get("company"), "title": a[2]["job"].get("title"),
                               "outcome": "ERROR", "error": str(ex)[:200], "seconds": None}
                    pending.pop(n)
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    print(f"## {rec['n']:>3} {rec['outcome']:<13} {rec.get('ats')} {rec['seconds']}s {rec['company']}", flush=True)
            time.sleep(2)
            if len(pending) <= workers:  # only the last jobs are left: give each its timeout + 90 s from now
                for n, (a, res, t0) in list(pending.items()):
                    if t0 is None:
                        pending[n] = (a, res, time.time())
                    elif time.time() - t0 > timeout + 90 and not res.ready():
                        pending.pop(n)
                        j = a[2]["job"]
                        rec = {"n": n, "company": j.get("company"), "title": j.get("title"), "channel": j.get("channel", ""),
                               "start_url": j.get("direct_url") or j.get("apply_url") or j["url"], "outcome": "ERROR",
                               "error": "hung past the job timeout", "seconds": timeout + 90}
                        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        out.flush()
                        print(f"## {n:>3} ERROR (hung) {j.get('company')}", flush=True)
        pool.terminate()


def main():
    global AUTO
    if DRY_RUN:
        return dry_main([int(a) for a in sys.argv[1:] if a.isdigit()] or None)
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
            if run_job(ctx, kit, n, len(kits), parked) == "quit":
                ctx.close()
                return
        ctx.close()
    if parked:
        (HERE / "parked.txt").write_text("\n".join(parked) + "\n", encoding="utf-8")
        print(f"\n⏸ {len(parked)} jobs need you (also in helper/parked.txt):")
        for x in parked:
            print("   " + x)
    print("\nAll done for today. 🎉")


if __name__ == "__main__":
    main()
