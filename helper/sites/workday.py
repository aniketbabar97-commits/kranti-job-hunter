"""Workday (…myworkdayjobs.com / …myworkdaysite.com) adapter. Techniques: helper/knowledge/workday_selectors.md.

VERIFIED read-only on autodesk.wd1 + nvidia.wd5 (Oct 2026):
  job page [adventureButton] "Apply" -> popup [applyManually | autofillWithResume | useMyLastApplication]
  -> /apply/applyManually: Create-Account form straight away (autodesk) or chooser
     [GoogleSignInButton | LinkedInSignInButton | SignInWithEmailButton] (nvidia) -> sign-in form
  sign in:        [email] [password] [signInSubmitButton] [createAccountLink] [forgotPasswordLink]
  create account: [email] [password] [verifyPassword] [createAccountCheckbox] [createAccountSubmitButton] [signInLink]
  forgot:         [email] [resetPasswordButton]
  all three forms: [click_filter] overlay on the submit button, [beecatcher] honeypot input name=website (never fill),
  [progressBar] [progressBarActiveStep] [progressBarInactiveStep]
ASSUMED (knowledge file, could not be verified without creating an account): formField-*, file-upload-input-ref,
  file-upload-successful, bottom-navigation-next-button, promptOption/promptLeafNode, dateSection*-input, inputError.
"""
import os
import re
import time
from pathlib import Path

from helper.sites.base import Site

A = "[data-automation-id={}]"
HOST = re.compile(r"\.(myworkdayjobs|myworkdaysite)\.com", re.I)
FIXTURE = "https://autodesk.wd1.myworkdayjobs.com/en-US/Ext/job/Germany---Remote/Principal-Enterprise-Account-Executive-Mobility_26WD100944-1"
PLACEHOLDER = re.compile(r"^\s*(select one|select|--+|bitte auswählen|auswählen|)\s*$", re.I)
CODE_FIELDS = ("verificationCode", "verifyCode", "code", "oneTimeCode", "otp")
STEP_RX = {
    "information": r"my information|personal information|contact information|meine informationen|kontakt",
    "experience": r"my experience|meine erfahrung|erfahrung",
    "questions": r"application questions|additional questions|questionnaire|bewerbungsfragen|fragen",
    "disclosures": r"voluntary disclosure|freiwillige angaben",
    "selfid": r"self[\s-]?identif|selbstidentifi",
    "review": r"\breview\b|überprüfen|prüfen",
}
DECLINE = r"not\s+(wish|want)\s+to|decline|prefer\s+not|choose\s+not|rather\s+not|don'?t\s+wish|keine angabe"


def _host(page):
    return page.url.split("://", 1)[-1].split("/", 1)[0]


def posting_open(url):
    """Closed-posting check without a browser: GET /wday/cxs/<tenant>/<site>/job/<slug> (None = unknown)."""
    import requests
    m = re.match(r"https?://([^./]+)\.(wd\d+)\.myworkday(?:jobs|site)\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/job/(?:[^/]+/)?([^/?#]+)", url)
    if not m:
        return None
    tenant, _, site, slug = m.groups()
    host = url.split("://", 1)[1].split("/", 1)[0]
    try:
        r = requests.get(f"https://{host}/wday/cxs/{tenant}/{site}/job/{slug}", timeout=20,
                         headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
        if r.status_code == 404:
            return False
        if r.ok:
            return "jobPostingInfo" in r.text
    except Exception:
        return None
    return None


class Workday(Site):
    name = "workday"
    FIXTURE = FIXTURE
    needs_account = True
    submit_regex = re.compile(r"^\s*(submit|absenden|senden|einreichen)\s*$", re.I)
    next_regex = re.compile(r"^\s*(next|save and continue|weiter|continue|fortfahren)\s*$", re.I)
    confirm_regex = re.compile(r"congratulations|thank you for applying|application submitted|"
                               r"you('ve| have) (successfully )?applied|bewerbung eingereicht|vielen dank für ihre bewerbung", re.I)

    def match(self, url, page=None):
        return bool(HOST.search(url or ""))

    # ---------------------------------------------------------------- low-level
    @staticmethod
    def _loc(page, key):
        """Resolver: formField-<k> wrapper -> [data-automation-id=k] -> [id=k] -> [id$=--k] -> [name=k]. First visible."""
        for sel in (f'[data-automation-id="formField-{key}"] input, [data-automation-id="formField-{key}"] button, '
                    f'[data-automation-id="formField-{key}"] textarea',
                    f'[data-automation-id="{key}"]', f'[id="{key}"]', f'[id$="--{key}"]', f'[name="{key}"]'):
            loc = page.locator(sel)
            for i in range(min(loc.count(), 5)):
                if loc.nth(i).is_visible():
                    return loc.nth(i)
        return None

    def _has(self, page, key):
        return self._loc(page, key) is not None

    def _fill(self, page, key, value):
        el = self._loc(page, key)
        if el is None:
            return False
        tag = el.evaluate("e => e.tagName").lower()
        if tag == "button":
            return self._listbox(page, el, re.escape(value))
        if (el.input_value() or "").strip():
            return True  # already there (profile prefill)
        el.fill(value)
        el.press("Tab")  # Workday validates on blur
        return True

    def _click(self, page, key, timeout=4000):
        """Click a button by automation id; when a click_filter overlay sits on it, click the overlay instead."""
        el = self._loc(page, key)
        if el is None:
            return False
        overlay = el.locator("xpath=..").locator(A.format("click_filter"))
        try:
            if overlay.count() and overlay.first.is_visible():
                overlay.first.click(timeout=timeout)
            else:
                el.click(timeout=timeout)
        except Exception:
            el.click(timeout=timeout, force=True)
        return True

    @staticmethod
    def _close_popup(page):
        """NEVER Escape (rolls the selection back): click neutral whitespace instead."""
        try:
            page.locator(A.format("jobTitleHeading")).first.click(timeout=1000)
        except Exception:
            page.mouse.click(5, 5)

    def _listbox(self, page, btn, want_rx):
        """button[aria-haspopup=listbox]: options render at the END of <body> as ul[role=listbox] [role=option]."""
        cur = (btn.inner_text(timeout=500) or "").strip()
        if not PLACEHOLDER.match(cur):
            return True
        btn.click(timeout=2000)
        page.wait_for_timeout(500)
        opts = page.locator('ul[role="listbox"]:not([data-automation-id*="selectedItem"]) [role="option"], '
                            'ul[role="listbox"]:not([data-automation-id*="selectedItem"]) li')
        rx = re.compile(want_rx, re.I)
        for i in range(opts.count()):
            o = opts.nth(i)
            if rx.search((o.inner_text(timeout=300) or "").strip()):
                o.click(timeout=2000)
                page.wait_for_timeout(400)
                return not PLACEHOLDER.match((btn.inner_text(timeout=500) or "").strip())
        self._close_popup(page)
        return False

    def _prompt(self, page, inp, text, want_rx=None, group_rx=None):
        """Searchable prompt (source, phone code, field of study, skills): type, Enter, pick promptOption/LeafNode."""
        inp.click(timeout=2000)
        inp.fill(text)
        inp.press("Enter")
        page.wait_for_timeout(1200)
        rx = re.compile(want_rx or re.escape(text), re.I)
        if group_rx:  # hierarchical ("How did you hear": Job Board -> LinkedIn)
            grp = page.locator(A.format("promptOption") + ", " + A.format("promptOptionGroup") + ", " + A.format("promptTitle"))
            for i in range(grp.count()):
                if re.search(group_rx, grp.nth(i).inner_text(timeout=300) or "", re.I):
                    grp.nth(i).click(timeout=2000)
                    page.wait_for_timeout(800)
                    break
        opts = page.locator(A.format("promptLeafNode") + ", " + A.format("promptOption") + ", [role=option]")
        for i in range(opts.count()):
            o = opts.nth(i)
            if rx.search((o.inner_text(timeout=300) or "").strip()):
                o.click(timeout=2000)
                page.wait_for_timeout(500)
                return True
        if opts.count() == 1:
            opts.first.click(timeout=2000)
            return True
        self._close_popup(page)
        return False

    @staticmethod
    def _date(page, wrapper, mm, yyyy, dd=None):
        """Spinbutton date: click the month section and TYPE the digits (never set .value)."""
        sec = wrapper.locator(A.format("dateSectionMonth-input"))
        if not sec.count():
            return False
        sec.first.click(timeout=2000)
        page.keyboard.type(mm + (dd or "") + yyyy, delay=40)
        page.keyboard.press("Tab")
        return True

    def _tick_all(self, page):
        """Every visible unticked checkbox (acknowledgment, privacy, terms, retention, talent community): yes."""
        n = 0
        for el in page.query_selector_all("input[type=checkbox], [role=checkbox]"):
            try:
                if not el.is_visible():
                    continue
                checked = el.get_attribute("aria-checked") == "true" or (el.get_attribute("type") == "checkbox" and el.is_checked())
                if not checked:
                    try:
                        el.click(timeout=1500)
                    except Exception:
                        el.evaluate("e => e.click()")
                    n += 1
            except Exception:
                continue
        return n

    def errors(self, page):
        out = []
        for key in ("inputError", "errorMessage", "inputAlert", "errorBanner"):
            for el in page.locator(A.format(key)).all():
                try:
                    if el.is_visible():
                        out.append((el.inner_text(timeout=300) or key)[:80])
                except Exception:
                    pass
        return out

    # ---------------------------------------------------------------- account
    def _email(self):
        return os.environ["CANDIDATE_EMAIL"]

    def _create_account(self, page):
        from helper import vault
        email, pw = self._email(), vault.new_password(_host(page))
        if not self._has(page, "verifyPassword"):
            return False
        self._fill(page, "email", email)
        self._fill(page, "password", pw)
        self._fill(page, "verifyPassword", pw)
        self._tick_all(page)  # createAccountCheckbox (never the beecatcher: it is an input, not a checkbox)
        t0 = time.time()
        self._click(page, "createAccountSubmitButton")
        page.wait_for_timeout(4000)
        body = page.inner_text("body")[:6000]
        if re.search(r"already (exists|has an account|registered|in use)|bereits (registriert|vorhanden)", body, re.I):
            return "exists"
        vault.set(_host(page), email, pw)  # stored before verification: the account exists on their side now
        return self._verify_mail(page, t0)

    def _verify_mail(self, page, since_ts):
        """Workday mails either a code (typed in) or a link (opened in this tab); some tenants skip it."""
        from helper import mailcodes
        page.wait_for_timeout(2000)
        body = page.inner_text("body")[:6000].lower()
        hint = _host(page).split(".")[0]
        if any(self._has(page, f) for f in CODE_FIELDS) or ("code" in body and "verif" in body):
            code = mailcodes.wait_for_code("workday", since_ts, timeout=180) or \
                mailcodes.wait_for_code(hint, since_ts, timeout=60)
            if not code:
                return False
            for f in CODE_FIELDS:
                if self._fill(page, f, code):
                    break
            else:
                page.locator("input[type=text], input[type=tel], input:not([type])").first.fill(code)
            for key in ("verifyButton", "submitButton", "continueButton"):
                if self._click(page, key):
                    break
            else:
                page.get_by_role("button", name=re.compile(r"verify|submit|continue|weiter", re.I)).first.click()
            page.wait_for_timeout(4000)
            return True
        if re.search(r"verif|confirm|activat|bestätig", body) and re.search(r"e-?mail", body):
            link = mailcodes.wait_for_link("workday", r"myworkday|verif|activat|confirm", since_ts, timeout=180) or \
                mailcodes.wait_for_link(hint, r"myworkday|verif|activat|confirm", since_ts, timeout=60)
            if not link:
                return False
            page.goto(link, timeout=60000)
            page.wait_for_timeout(5000)
        return True

    def _sign_in(self, page, email, pw):
        if not self._has(page, "signInSubmitButton"):
            self._click(page, "signInLink") or self._click(page, "SignInWithEmailButton")
            page.wait_for_timeout(2000)
        self._fill(page, "email", email)
        self._fill(page, "password", pw)
        self._click(page, "signInSubmitButton")
        page.wait_for_timeout(5000)
        return not self._has(page, "signInSubmitButton")

    def _reset_password(self, page, email):
        """Forgot password -> mail link -> new password -> vault -> sign in."""
        from helper import mailcodes, vault
        if not self._has(page, "resetPasswordButton") and not self._click(page, "forgotPasswordLink"):
            return False
        page.wait_for_timeout(2000)
        self._fill(page, "email", email)
        t0 = time.time()
        self._click(page, "resetPasswordButton")
        link = mailcodes.wait_for_link("workday", r"myworkday|reset|password", t0, timeout=180) or \
            mailcodes.wait_for_link(_host(page).split(".")[0], r"reset|password", t0, timeout=60)
        if not link:
            return False
        page.goto(link, timeout=60000)
        page.wait_for_timeout(5000)
        new = vault.new_password(_host(page))
        if not (self._fill(page, "password", new) or self._fill(page, "newPassword", new)):
            return False
        self._fill(page, "verifyPassword", new) or self._fill(page, "confirmPassword", new)
        for key in ("resetPasswordButton", "changePasswordButton", "submitButton"):
            if self._click(page, key):
                break
        else:
            page.get_by_role("button", name=re.compile(r"reset|change|save|submit", re.I)).first.click()
        page.wait_for_timeout(5000)
        vault.set(_host(page), email, new)
        return self._sign_in(page, email, new) if self._has(page, "signInSubmitButton") else True

    def ensure_account(self, page):
        """Known account -> sign in (reset on failure). Unknown -> create (reset when it already exists)."""
        from helper import vault
        if os.environ.get("HELPER_READONLY") == "1":
            return False  # fixture test: stop at the account step, never create / sign in
        if self._has(page, "SignInWithEmailButton"):
            self._click(page, "SignInWithEmailButton")
            page.wait_for_timeout(2500)
        acct = vault.get(_host(page))
        if acct:
            return self._sign_in(page, acct["email"], acct["password"]) or self._reset_password(page, acct["email"])
        if not self._has(page, "verifyPassword"):
            self._click(page, "createAccountLink")
            page.wait_for_timeout(2500)
        res = self._create_account(page)
        if res == "exists":
            self._click(page, "signInLink")
            page.wait_for_timeout(2000)
            return self._reset_password(page, self._email())
        return bool(res)

    # ---------------------------------------------------------------- test
    def test_fixture(self, headless=True, url=None):
        """Read-only run up to the account step: a throw-away VAULT_KEY + vault file, no account is created."""
        import tempfile
        from helper import vault
        keep = {k: os.environ.get(k) for k in ("VAULT_KEY", "HELPER_READONLY")}
        keep_vault = vault.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["VAULT_KEY"] = "fixture-test-only-" + os.urandom(8).hex()
            os.environ["HELPER_READONLY"] = "1"
            vault.VAULT = Path(tmp) / "vault.enc"
            try:
                return super().test_fixture(headless, url)
            finally:
                vault.VAULT = keep_vault
                for k, v in keep.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    # ---------------------------------------------------------------- flow
    def open_form(self, page, ctx=None):
        from helper import apply
        apply.accept_cookies(page)
        if "/apply" not in page.url:
            if not (self._click(page, "adventureButton") or self._click(page, "applyButton")):
                apply.click_apply(page)
            page.wait_for_timeout(2500)
            if not self._click(page, "applyManually"):
                try:
                    page.get_by_role("button", name=re.compile(r"apply manually|manuell", re.I)).first.click(timeout=3000)
                except Exception:
                    pass
            page.wait_for_timeout(4000)
        if any(self._has(page, k) for k in ("signInSubmitButton", "createAccountSubmitButton", "SignInWithEmailButton")):
            if not self.ensure_account(page):
                return False
        page.wait_for_timeout(3000)
        return self.step(page) is not None or self._has(page, "bottom-navigation-next-button")

    def step(self, page):
        """'information' | 'experience' | 'questions' | 'disclosures' | 'selfid' | 'review' | None."""
        txt = ""
        for sel in (A.format("progressBarActiveStep"), '[aria-current="step"]', A.format("currentPage"), A.format("stepTitle")):
            try:
                loc = page.locator(sel)
                vis = [loc.nth(i) for i in range(min(loc.count(), 8)) if loc.nth(i).is_visible()]
                if vis:
                    txt = vis[0].inner_text(timeout=800) or ""
                    break
            except Exception:
                continue
        for key, rx in STEP_RX.items():
            if re.search(rx, txt, re.I):
                return key
        for key, pg in (("review", "applyFlowReviewPage"), ("information", "contactInformationPage"),
                        ("information", "personalInformationPage"), ("questions", "applicationQuestionsPage")):
            loc = page.locator(A.format(pg))
            if loc.count() and loc.first.is_visible():
                return key
        return None

    def fill(self, page, kit, cv, letter, text, lang, uploaded=None):
        from helper import apply
        files_done = uploaded if uploaded is not None else set()
        filled, unknown = [], []
        step = self.step(page)
        facts = _facts()
        phone = os.environ.get("CANDIDATE_PHONE", "")
        if step != "review":  # id-based: each helper only touches fields that are visible on this page
            filled += self._my_information(page, facts, phone, lang)
            filled += self._upload(page, cv, letter, files_done)
        if step == "experience":
            filled += self._experience_extras(page, facts)
        # whatever is left: the generic label filler (works through aria-labelledby on Workday)
        f, u = apply.fill(page, kit, cv, letter, text, lang, files_done)
        filled += f
        unknown += u
        filled += self._choices(page, facts, lang)
        filled += self._dates(page, facts)
        self._tick_all(page)
        return filled, unknown

    def _my_information(self, page, facts, phone, lang):
        done = []
        name, loc = facts.get("name", {}), facts.get("location", {})
        for keys, val in ((("legalNameSection_firstName", "firstName"), name.get("first", "Kranti")),
                          (("legalNameSection_lastName", "lastName"), name.get("last", "Chavan")),
                          (("addressSection_addressLine1", "addressLine1"), os.environ.get("CANDIDATE_STREET", "")),
                          (("addressSection_city", "city"), loc.get("city", "Karlsruhe")),
                          (("addressSection_postalCode", "postalCode"), str(loc.get("postal_code", "76131"))),
                          (("email", "emailAddress"), os.environ.get("CANDIDATE_EMAIL", ""))):
            if val:
                for k in keys:
                    if self._fill(page, k, val):
                        done.append(f"{k} = {val}")
                        break
        # country / state: button listbox or prompt
        for k in ("countryDropdown", "country", "addressSection_country"):
            el = self._loc(page, k)
            if el is not None and el.evaluate("e => e.tagName").lower() == "button" and self._listbox(page, el, r"^(germany|deutschland)$"):
                done.append("country = Germany")
                break
        for k in ("addressSection_countryRegion", "countryRegion"):  # "State" is countryRegion
            el = self._loc(page, k)
            if el is not None:
                state = facts.get("location", {}).get("state", "Baden-Württemberg")
                if el.evaluate("e => e.tagName").lower() == "button":
                    self._listbox(page, el, re.escape(state)) and done.append(f"state = {state}")
                else:
                    self._prompt(page, el, state) and done.append(f"state = {state}")
                break
        for k in ("phone-device-type", "phoneType"):
            el = self._loc(page, k)
            if el is not None and self._listbox(page, el, r"mobile|cell|mobil"):
                done.append("phone type = Mobile")
                break
        code_prompt = None
        for k in ("country-phone-code", "countryPhoneCode"):
            code_prompt = self._loc(page, k)
            if code_prompt is not None:
                if self._prompt(page, code_prompt, "Germany", r"germany|deutschland|\+49"):
                    done.append("phone code = +49")
                break
        for k in ("phone-number", "phoneNumber"):
            el = self._loc(page, k)
            if el is not None and phone:
                num = re.sub(r"^\+?49\s*", "", phone) if code_prompt is not None else phone
                self._fill(page, k, re.sub(r"[^\d+ ]", "", num).strip()) and done.append("phone")
                break
        for k in ("source", "sourcePrompt"):
            el = self._loc(page, k)
            if el is not None:
                tag = el.evaluate("e => e.tagName").lower()
                ok = self._listbox(page, el, r"linkedin|job board") if tag == "button" else \
                    self._prompt(page, el, "LinkedIn", r"^linkedin", group_rx=r"^(job boards?|social media|social networks?)$")
                ok and done.append("source = LinkedIn")
                break
        for k in ("candidateIsPreviousWorker", "previousWorker"):
            if self._radio(page, k, r"^(no|nein)\b"):
                done.append("previous worker = No")
                break
        return done

    def _radio(self, page, key, want_rx):
        wrap = page.locator(f'[data-automation-id="formField-{key}"], [data-automation-id="{key}"], [id$="--{key}"]')
        if not wrap.count():
            return False
        rx = re.compile(want_rx, re.I)
        if wrap.first.locator('[aria-checked="true"], input[type=radio]:checked').count():
            return True
        for r in wrap.first.locator("[role=radio], input[type=radio], label").all():
            try:
                lab = r.evaluate("e => (e.labels && e.labels[0] ? e.labels[0].innerText : '') + ' ' + (e.getAttribute('aria-label')||'') + ' ' + e.innerText")
                if rx.search(lab.strip()):
                    r.click(timeout=1500)
                    return True
            except Exception:
                continue
        return False

    def _upload(self, page, cv, letter, files_done):
        done = []
        inputs = page.locator(A.format("file-upload-input-ref") + ", " + A.format("resumeUpload") + " input[type=file], "
                              + A.format("quickApplyUpload") + " input[type=file], [id$='--attachments'] input[type=file]")
        if not inputs.count():
            return done
        for target in (cv, letter):
            if target in files_done:
                continue
            idx = min(len(files_done), inputs.count() - 1)
            inputs.nth(idx).set_input_files(target)
            files_done.add(target)
            done.append(f"upload {Path(target).name}")
            self._wait_upload(page)
        return done

    def _wait_upload(self, page, timeout=20):
        """Accepted only after file-upload-successful shows and no busy indicator; inputError = rejected."""
        end = time.time() + timeout
        while time.time() < end:
            busy = page.locator('[aria-busy="true"], [role=progressbar]')
            ok = page.locator(A.format("file-upload-successful") + ", " + A.format("file-upload-item"))
            if page.locator(A.format("inputError") + ', [aria-invalid="true"]').count():
                return False
            if ok.count() and not busy.count():
                return True
            page.wait_for_timeout(500)
        return False

    def _experience_extras(self, page, facts):
        done = []
        for k in ("linkedinQuestion", "linkedInAccount"):
            if facts.get("linkedin") and self._fill(page, k, facts["linkedin"]):
                done.append("linkedin")
                break
        return done

    def _choices(self, page, facts, lang):
        """Remaining button listboxes + radio groups, by label (answers.answer if present, else facts)."""
        from helper.apply import LABEL_JS
        done = []
        for btn in page.locator('button[aria-haspopup="listbox"]').all():
            try:
                if not btn.is_visible() or not PLACEHOLDER.match((btn.inner_text(timeout=300) or "").strip()):
                    continue
                label = btn.evaluate(LABEL_JS)
                want = _choice_for(label, facts, lang)
                if want and self._listbox(page, btn, want):
                    done.append(f"{label[:30]} = {want}")
            except Exception:
                continue
        for grp in page.locator('[role=radiogroup], fieldset, [data-automation-id^="formField-"]:has([role=radio])').all():
            try:
                if grp.locator('[aria-checked="true"], input[type=radio]:checked').count() or not grp.locator("[role=radio], input[type=radio]").count():
                    continue
                label = grp.evaluate("e => (e.querySelector('legend, label, [id$=\"-label\"]')||e).innerText.slice(0,200)")
                want = _choice_for(label, facts, lang)
                if not want:
                    continue
                rx = re.compile(want, re.I)
                for r in grp.locator("[role=radio], input[type=radio]").all():
                    lab = r.evaluate("e => ((e.labels && e.labels[0]) ? e.labels[0].innerText : '') + ' ' + (e.getAttribute('aria-label')||'') + ' ' + (document.getElementById(e.getAttribute('aria-labelledby')||'')||{}).innerText")
                    if rx.search(lab or ""):
                        r.click(timeout=1500)
                        done.append(f"{label[:30]} = {want}")
                        break
            except Exception:
                continue
        return done

    def _dates(self, page, facts):
        """Self-identify 'Today's date' and similar empty date widgets (type digits, never .value)."""
        done = []
        today = time.strftime("%m%d%Y")
        for w in page.locator(A.format("dateInputWrapper") + ", " + A.format("dateSectionGroup")).all():
            try:
                if not w.is_visible():
                    continue
                vals = [i.input_value() for i in w.locator("input").all()]
                if any(v.strip() for v in vals):
                    continue
                label = w.evaluate("e => (e.closest('[data-automation-id^=\"formField-\"]')||e).innerText.slice(0,120)")
                if re.search(r"today|date signed|heutiges datum|datum", label, re.I):
                    m = w.locator(A.format("dateSectionMonth-input"))
                    if m.count():
                        m.first.click(timeout=1500)
                        page.keyboard.type(today if w.locator(A.format("dateSectionDay-input")).count() else today[:2] + today[4:], delay=40)
                        done.append("today's date")
            except Exception:
                continue
        return done

    # ---------------------------------------------------------------- navigation
    def next_button(self, page):
        """The footer button: on the review page it has the same id but says 'Submit' -> gate on the text."""
        for k in ("bottom-navigation-next-button", "pageFooterNextButton", "wd-CommandButton_next", "saveAndContinueButton"):
            el = self._loc(page, k)
            if el is not None:
                txt = (el.inner_text(timeout=500) or "").strip()
                return el, ("submit" if self.submit_regex.search(txt) else "next")
        return None, None

    def click_next(self, page, allow_submit=False, wait=15):
        el, kind = self.next_button(page)
        if el is None or (kind == "submit" and not allow_submit):
            return None
        end = time.time() + wait  # Continue can stay disabled ~15 s after a save
        while time.time() < end and not el.is_enabled():
            page.wait_for_timeout(500)
        if not el.is_enabled():
            return None
        el.click(timeout=5000)
        page.wait_for_timeout(4000)
        return kind


def _facts():
    import yaml
    from helper.apply import ROOT
    f = ROOT / "profile" / "facts.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}


def _choice_for(label, facts, lang):
    """Regex for the option to pick, from helper.answers.answer (if that module exists) or profile/facts.yaml."""
    try:
        from helper import answers as _ans
        a = _ans.answer(label)
        if a:
            return re.escape(str(a))
    except Exception:
        pass
    L = label.lower()
    if re.search(r"disab|behinder", L):
        return r"^\s*(no|nein)\b"
    if re.search(r"veteran|ethnic|race|hispanic|latino", L):
        return DECLINE
    if re.search(r"gender|geschlecht", L):
        return r"^(female|weiblich)$"
    if re.search(r"country|land\b|staat", L) and not re.search(r"phone|code", L):
        return r"^(germany|deutschland)$"
    if re.search(r"phone device|device type|telefontyp", L):
        return r"mobile|cell|mobil"
    if re.search(r"how did you hear|source|quelle|aufmerksam|erfahren", L):
        return r"linkedin|job board|jobbörse"
    if re.search(r"previously (worked|been employed)|former (employee|worker)|worked (here|for us|at|for) before|"
                 r"bereits .*gearbeitet|ehemals", L):
        return r"^(no|nein)\b"
    if re.search(r"sponsor", L):
        return r"^(no|nein)\b"
    if re.search(r"legally authori[sz]ed|eligible to work|work (permit|authori[sz])|arbeitserlaubnis|berechtigt", L):
        return r"^(yes|ja)\b"
    if re.search(r"relocat|umzug", L):
        return r"^(yes|ja)\b"
    if re.search(r"travel|reise", L):
        return r"^(yes|ja)\b"
    if re.search(r"salutation|anrede|prefix", L):
        return r"^(ms\.?|frau)$"
    if re.search(r"english|englisch", L) and re.search(r"level|niveau|proficien|kenntnis", L):
        return r"fluent|c2|native|verhandlungssicher|advanced"
    if re.search(r"german|deutsch", L) and re.search(r"level|niveau|proficien|kenntnis", L):
        return r"intermediate|b1|gut"
    if re.search(r"\b18\b|age of|volljährig|legal age", L):
        return r"^(yes|ja)\b"
    if re.search(r"driv|führerschein", L):
        return r"^(no|nein)\b"
    if re.search(r"criminal|vorstrafe", L):
        return r"^(no|nein)\b"
    if re.search(r"remote|hybrid|home ?office", L):
        return r"^(yes|ja)\b"
    if re.search(r"degree|abschluss", L):
        return r"bachelor"
    if re.search(r"notice|kündigungsfrist|availab|start", L):
        return r"3 months|more than|3 monate|other|sonstige"
    if re.search(r"terms|privacy|datenschutz|consent|agree|zustimm|accept|talent|retain|keep my", L):
        return r"^(yes|ja|i agree|accept|i acknowledge)"
    return None


SITE = Workday()
