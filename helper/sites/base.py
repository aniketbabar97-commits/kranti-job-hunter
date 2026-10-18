"""Site adapters: one small class per applicant-tracking system (ATS). The generic filler in helper/apply.py does
most of the work; a Site adds how to detect the ATS, how to reach the form, site-specific selectors, and the
button / confirmation texts. Rules (from the owner): tick every checkbox, accept all cookies, disability = no.
The only reasons to park a job: a CAPTCHA challenge, or an account / password step."""
import os
import re
from pathlib import Path

CHROMIUM = os.environ.get("PW_CHROMIUM", "/opt/pw-browsers/chromium")
TEST_CV = os.environ.get("TEST_CV", "/tmp/claude-0/t/cv.pdf")
TEST_CL = os.environ.get("TEST_CL", "/tmp/claude-0/t/cl.pdf")
ALREADY_APPLIED = re.compile(r"already applied|you('ve| have) already applied|bereits beworben|sie haben sich bereits|"
                             r"bewerbung liegt bereits vor", re.I)


class Site:
    """Base adapter = generic behaviour ("own" career sites)."""
    name = "own"
    FIXTURE = None            # a live job URL used by test_fixture()
    needs_account = False     # True: the ATS forces a login / password step -> park
    HOST = None               # regex on the URL
    MARKER = None             # regex on the page HTML (custom domains)
    # css selectors for fields the generic label matcher may miss: key -> css (see VALUES in fill)
    selectors = {}
    submit_regex = None       # default: apply.SUBMIT_BTN
    next_regex = None         # default: apply.NEXT_BTN
    confirm_regex = None      # default: apply.CONFIRM
    form_url = None           # f(url) -> url of the form page (skip the job page), or None

    # ------------------------------------------------------------------ detection
    def match(self, url, page=None):
        if self.HOST and re.search(self.HOST, url or "", re.I):
            return True
        if self.MARKER and page is not None:
            try:
                return re.search(self.MARKER, page.content()[:400000], re.I) is not None
            except Exception:
                return False
        return False

    # ------------------------------------------------------------------ flow
    def open_form(self, page, ctx=None):
        """From the job page to the form. Returns True when a form seems to be on screen."""
        from helper import apply
        if self.form_url:
            try:
                target = self.form_url(page.url)
                if target and target != page.url:
                    page.goto(target, timeout=60000)
                    page.wait_for_timeout(2500)
            except Exception:
                pass
        apply.accept_cookies(page)
        if not self.has_form(page) and apply.click_apply(page):
            page.wait_for_timeout(3000)
            page = page.context.pages[-1]  # some sites open the form in a new tab
            apply.accept_cookies(page)
        return self.has_form(page)

    def has_form(self, page):
        """A real application form: a file input, or at least two visible fields that are not a site search."""
        try:
            for f in page.query_selector_all("input[type=file]"):
                if f.evaluate("e => (e.closest('form') || e.parentElement).getClientRects().length > 0"):
                    return True  # the file input itself is often hidden behind a styled button
            n = 0
            for el in page.query_selector_all("input:not([type=hidden]):not([type=search]), textarea, select"):
                try:
                    if el.is_visible() and not re.search(r"search|suche|ccm-|cookie", el.get_attribute("name") or el.get_attribute("id") or "", re.I):
                        n += 1
                except Exception:
                    continue
            return n >= 2
        except Exception:
            return False

    def values(self, kit, cv, letter, text, lang):
        from helper import answers
        f = answers.facts()
        return {
            "first_name": f["name"]["first"], "last_name": f["name"]["last"],
            "name": f"{f['name']['first']} {f['name']['last']}",
            "email": os.environ.get("CANDIDATE_EMAIL", ""), "phone": os.environ.get("CANDIDATE_PHONE", ""),
            "linkedin": f["linkedin"], "city": f["location"]["city"], "postal": f["location"]["postal_code"],
            "country": "Deutschland" if lang == "de" else f["location"]["country"],
            "salary": str(f["salary"]["default_eur"]), "start": answers.de_date(f["notice"]["earliest_start"]),
            "letter_text": text or "", "cv": cv, "letter": letter,
        }

    def fill(self, page, kit, cv, letter, text, lang, uploaded=None):
        """Generic filler first, then the site's own selectors for whatever is still empty."""
        from helper import apply
        files_done = uploaded if uploaded is not None else set()
        filled, unknown = apply.fill(page, kit, cv, letter, text, lang, files_done)
        vals = self.values(kit, cv, letter, text, lang)
        for key, css in self.selectors.items():
            v = vals.get(key)
            if not v:
                continue
            for frame in page.frames:
                try:
                    el = frame.query_selector(css)
                    if el is None:
                        continue
                    if key in ("cv", "letter"):
                        if v not in files_done:
                            el.set_input_files(v)
                            files_done.add(v)
                            filled.append(f"upload {Path(v).name}")
                    elif el.is_visible() and not el.input_value().strip():
                        el.fill(v)
                        filled.append(f"{key} = {v}")
                    break
                except Exception:
                    continue
        self.after_fill(page, lang)
        return filled, unknown

    def after_fill(self, page, lang):
        """Hook for site-specific widgets (custom dropdowns, yes/no buttons)."""

    def already_applied(self, page):
        try:
            return ALREADY_APPLIED.search(page.inner_text("body", timeout=1000)[:20000]) is not None
        except Exception:
            return False

    def problems(self, page, uploads_needed, uploaded):
        from helper import apply
        why = apply.problems(page, uploads_needed, uploaded)
        if self.needs_account and self.account_step(page) and "account/password" not in why:
            why.append("account/password")
        return why

    def account_step(self, page):
        return page.query_selector("input[type=password]") is not None

    def find_button(self, page, rx):
        """Visible+enabled button matching rx (no click), or None."""
        from helper import apply
        return apply.find_button(page, rx)

    def rx(self, which):
        from helper import apply
        return getattr(self, which + "_regex") or {"submit": apply.SUBMIT_BTN, "next": apply.NEXT_BTN,
                                                   "confirm": apply.CONFIRM}[which]

    # ------------------------------------------------------------------ test
    def test_fixture(self, headless=True, url=None):
        """Open the fixture, fill up to the Submit button, never click it. Returns a report dict."""
        from playwright.sync_api import sync_playwright
        from helper import apply
        os.environ.setdefault("CANDIDATE_EMAIL", "test@example.com")
        os.environ.setdefault("CANDIDATE_PHONE", "+49 000")
        url = url or self.FIXTURE
        kit = {"job": {"salary": "", "url": url, "company": "test", "title": "test"}, "tailoring": {}, "lang": "de"}
        rep = {"ats": self.name, "fixture": url, "filled": 0, "uploads": 0, "problems": [], "submit": False,
               "steps": 0, "detail": []}
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROMIUM, headless=headless)
            ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="de-DE")
            page = ctx.new_page()
            try:
                page.goto(url, timeout=60000)
                page.wait_for_timeout(3000)
                rep["form"] = self.open_form(page)
                page = ctx.pages[-1]
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
                uploads = set()
                for step in range(4):
                    rep["steps"] = step + 1
                    apply.accept_cookies(page)
                    filled, unknown = self.fill(page, kit, TEST_CV, TEST_CL, "Sehr geehrte Damen und Herren, ...", "de", uploads)
                    apply.tick_consent(page)
                    page.wait_for_timeout(2000)  # React forms enable Submit a moment after the last field
                    rep["filled"] += len([x for x in filled if not x.startswith("upload")])
                    rep["detail"] += filled
                    rep["unknown"] = unknown
                    rep["problems"] = self.problems(page, page.query_selector("input[type=file]") is not None, uploads)
                    rep["submit"] = self.find_button(page, self.rx("submit")) is not None
                    if rep["submit"] or rep["problems"] and "CAPTCHA" in rep["problems"]:
                        break
                    if self.find_button(page, self.rx("next")) is not None and apply.click_button(page, self.rx("next")):
                        page.wait_for_timeout(3500)
                        continue
                    break
                rep["uploads"] = len(uploads)
                rep["url"] = page.url
                if self.needs_account and self.account_step(page) and "account/password" not in rep["problems"]:
                    rep["problems"].append("account/password")
            except Exception as ex:
                rep["error"] = f"{type(ex).__name__}: {str(ex)[:120]}"
            finally:
                b.close()
        return rep
