"""Workday (…myworkdayjobs.com / …myworkdaysite.com) adapter.

Flow (selectors verified read-only on autodesk.wd1 and nvidia.wd5, Oct 2026):
  job page  [adventureButton] "Apply"  ->  popup  [applyManually]
  ->  /apply/applyManually  : either the Create-Account form straight away (autodesk) or a chooser
      [GoogleSignInButton | LinkedInSignInButton | SignInWithEmailButton] (nvidia) -> sign-in form
      [email] [password] [signInSubmitButton] [createAccountLink] [forgotPasswordLink]
  ->  create account: [email] [password] [verifyPassword] [createAccountCheckbox] [createAccountSubmitButton]
      (+ [beecatcher] honeypot input "website" - never touch it)
  ->  forgot password: [email] [resetPasswordButton]
  ->  verification mail (code or link) -> pages My Information / My Experience / Application Questions /
      Voluntary Disclosures / Self Identify / Review -> [bottom-navigation-next-button] ... Submit.
Page-step selectors (formField-*, file-upload-input-ref, bottom-navigation-next-button) are the stable Workday
automation ids known from the candidate flow; they could not be verified without creating an account.
"""
import os
import re
import time
from pathlib import Path

from helper.sites.base import Site

A = "[data-automation-id={}]"
HOST = re.compile(r"\.(myworkdayjobs|myworkdaysite)\.com", re.I)
NEXT_IDS = ("bottom-navigation-next-button", "pageFooterNextButton")
DISABILITY_NO = re.compile(r"^\s*(no|nein)\b.*(disab|behind|do not (have|wish)|don't have)|^\s*(no|nein)\s*,?\s*i (do not|don't)", re.I)
CODE_FIELDS = ("verificationCode", "verifyCode", "code", "oneTimeCode", "otp")
HONEYPOT = "beecatcher"


def _h(page):
    return page.url.split("://", 1)[-1].split("/", 1)[0]


class Workday(Site):
    name = "workday"
    needs_account = True
    submit_regex = re.compile(r"^\s*(submit|absenden|einreichen)\s*$", re.I)
    next_regex = re.compile(r"^\s*(next|save and continue|weiter|continue)\s*$", re.I)
    confirm_regex = re.compile(r"congratulations|thank you for applying|application (has been )?submitted|"
                               r"you('ve| have) (successfully )?applied|vielen dank für ihre bewerbung|erfolgreich", re.I)

    def match(self, url):
        return bool(HOST.search(url or ""))

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _click(page, aid, timeout=4000):
        loc = page.locator(A.format(aid))
        if loc.count() and loc.first.is_visible():
            loc.first.click(timeout=timeout)
            return True
        return False

    @staticmethod
    def _fill(page, aid, value):
        loc = page.locator(A.format(aid))
        if loc.count() and loc.first.is_visible():
            loc.first.fill(value)
            return True
        return False

    @staticmethod
    def _has(page, aid):
        loc = page.locator(A.format(aid))
        return loc.count() > 0 and loc.first.is_visible()

    def _tick_all(self, page):
        """Every visible, unticked checkbox (privacy, terms, talent community, retention, marketing): yes."""
        n = 0
        for el in page.query_selector_all("input[type=checkbox]"):
            try:
                if el.is_visible() and not el.is_checked():
                    try:
                        el.check(timeout=1500)
                    except Exception:
                        el.evaluate("e => e.click()")
                    n += 1
            except Exception:
                continue
        return n

    # ---------------------------------------------------------------- account
    def _email(self):
        return os.environ["CANDIDATE_EMAIL"]

    def _create_account(self, page):
        from helper import vault
        email, pw = self._email(), vault.new_password(_h(page))
        if not self._has(page, "verifyPassword"):
            return False
        self._fill(page, "email", email)
        self._fill(page, "password", pw)
        self._fill(page, "verifyPassword", pw)
        self._tick_all(page)  # createAccountCheckbox (candidate acknowledgment)
        t0 = time.time()
        self._click(page, "createAccountSubmitButton")
        page.wait_for_timeout(4000)
        body = page.inner_text("body")[:5000]
        if re.search(r"already (exists|has an account|registered|in use)|bereits", body, re.I):
            return "exists"
        vault.set(_h(page), email, pw)  # stored before verification: the account now exists on their side
        self._verify_mail(page, t0)
        return True

    def _verify_mail(self, page, since_ts):
        """Workday either mails a code (typed into the page) or a link (opened in the same tab)."""
        from helper import mailcodes
        page.wait_for_timeout(2000)
        body = page.inner_text("body")[:5000].lower()
        wants_code = any(self._has(page, f) for f in CODE_FIELDS) or "code" in body and "verif" in body
        if wants_code:
            code = mailcodes.wait_for_code("workday", since_ts, timeout=180) or \
                mailcodes.wait_for_code(_h(page).split(".")[0], since_ts, timeout=60)
            if code:
                for f in CODE_FIELDS:
                    if self._fill(page, f, code):
                        break
                else:
                    page.locator("input[type=text], input[type=tel], input:not([type])").first.fill(code)
                for aid in ("verifyButton", "submitButton", "continueButton"):
                    if self._click(page, aid):
                        break
                else:
                    page.get_by_role("button", name=re.compile(r"verify|submit|continue|weiter", re.I)).first.click()
                page.wait_for_timeout(4000)
                return True
            return False
        if re.search(r"verif|confirm|activat", body) and re.search(r"e-?mail", body):
            link = mailcodes.wait_for_link("workday", r"myworkday|verif|activat|confirm", since_ts, timeout=180)
            if link:
                page.goto(link, timeout=60000)
                page.wait_for_timeout(5000)
                return True
            return False
        return True  # no verification step shown: Workday logged her in straight away

    def _sign_in(self, page, email, pw):
        if not self._has(page, "signInSubmitButton"):
            self._click(page, "signInLink") or self._click(page, "SignInWithEmailButton")
            page.wait_for_timeout(2000)
        self._fill(page, "email", email)
        self._fill(page, "password", pw)
        self._click(page, "signInSubmitButton")
        page.wait_for_timeout(5000)
        return not self._has(page, "signInSubmitButton")  # the form is gone -> logged in

    def _reset_password(self, page, email):
        """Forgot password -> mail link -> new password -> vault."""
        from helper import mailcodes, vault
        if not self._click(page, "forgotPasswordLink"):
            return False
        page.wait_for_timeout(2000)
        self._fill(page, "email", email)
        t0 = time.time()
        self._click(page, "resetPasswordButton")
        link = mailcodes.wait_for_link("workday", r"myworkday|reset|password", t0, timeout=180)
        if not link:
            return False
        page.goto(link, timeout=60000)
        page.wait_for_timeout(5000)
        new = vault.new_password(_h(page))
        ok = self._fill(page, "password", new) or self._fill(page, "newPassword", new)
        self._fill(page, "verifyPassword", new) or self._fill(page, "confirmPassword", new)
        if not ok:
            return False
        for aid in ("resetPasswordButton", "changePasswordButton", "submitButton"):
            if self._click(page, aid):
                break
        else:
            page.get_by_role("button", name=re.compile(r"reset|change|save|submit", re.I)).first.click()
        page.wait_for_timeout(5000)
        vault.set(_h(page), email, new)
        return self._sign_in(page, email, new) if self._has(page, "signInSubmitButton") else True

    def ensure_account(self, page):
        """On the /apply/applyManually page: sign in with the vault password, else create the account,
        else reset the password. Returns True when the account step is behind us."""
        from helper import vault
        if self._has(page, "SignInWithEmailButton"):
            self._click(page, "SignInWithEmailButton")
            page.wait_for_timeout(2500)
        acct = vault.get(_h(page))
        if acct:  # known account: sign in
            if self._sign_in(page, acct["email"], acct["password"]):
                return True
            return self._reset_password(page, acct["email"])
        # no account yet: create one
        if not self._has(page, "verifyPassword"):
            self._click(page, "createAccountLink")
            page.wait_for_timeout(2500)
        res = self._create_account(page)
        if res == "exists":  # she registered here by hand earlier: reset the password into the vault
            self._click(page, "signInLink")
            page.wait_for_timeout(2000)
            return self._reset_password(page, self._email())
        return bool(res)

    # ---------------------------------------------------------------- flow
    def open_form(self, page, ctx=None):
        from helper import apply
        apply.accept_cookies(page)
        if "/apply" not in page.url:
            if not self._click(page, "adventureButton"):
                apply.click_apply(page)
            page.wait_for_timeout(2500)
            if not self._click(page, "applyManually"):
                page.get_by_role("button", name=re.compile(r"apply manually|manuell", re.I)).first.click()
            page.wait_for_timeout(4000)
        if self._has(page, "signInSubmitButton") or self._has(page, "createAccountSubmitButton") or \
                self._has(page, "SignInWithEmailButton"):
            if not self.ensure_account(page):
                return False
        page.wait_for_timeout(3000)
        if "/apply" in page.url and not page.url.rstrip("/").endswith("applyManually"):
            return True
        return self._has(page, "bottom-navigation-next-button") or self._has(page, "file-upload-input-ref")

    def step_name(self, page):
        try:
            t = page.locator(A.format("progressBarActiveStep")).first.inner_text(timeout=1000)
        except Exception:
            t = ""
        return (t or page.url.rsplit("/", 1)[-1]).strip().lower()

    def fill(self, page, kit, cv, letter, text, lang, uploaded=None):
        from helper import apply
        files_done = uploaded if uploaded is not None else set()
        filled, unknown = [], []
        step = self.step_name(page)
        if "experience" in step or self._has(page, "file-upload-input-ref"):  # My Experience: resume + letter
            for inp in page.locator(A.format("file-upload-input-ref")).all():
                for target in (cv, letter):
                    if target not in files_done:
                        inp.set_input_files(target)
                        files_done.add(target)
                        filled.append(f"upload {Path(target).name}")
                        page.wait_for_timeout(2500)
        # text fields: the generic filler (labels via aria-labelledby work on Workday)
        f, u = apply.fill(page, kit, cv, letter, text, lang, files_done)
        filled += f
        unknown += u
        filled += self._dropdowns_and_radios(page, kit, lang)
        self._tick_all(page)
        return filled, unknown

    def _dropdowns_and_radios(self, page, kit, lang):
        """Workday 'button' dropdowns (role=button + aria-haspopup=listbox) and radio groups."""
        facts = _facts()
        done = []
        for btn in page.locator("button[aria-haspopup='listbox']").all():
            try:
                label = btn.evaluate(apply_label_js())
                cur = (btn.inner_text(timeout=500) or "").strip().lower()
                if cur and cur not in ("select one", "select", "bitte auswählen", "auswählen"):
                    continue
                want = _choice_for(label, facts, lang)
                if not want:
                    continue
                btn.click(timeout=2000)
                page.wait_for_timeout(600)
                opt = page.get_by_role("option", name=re.compile(want, re.I))
                if opt.count():
                    opt.first.click(timeout=2000)
                    done.append(f"{label[:30]} = {want}")
                else:
                    page.keyboard.press("Escape")
            except Exception:
                continue
        for grp in page.locator("[role=radiogroup], fieldset").all():
            try:
                label = grp.evaluate("e => (e.querySelector('legend')||e).innerText.slice(0,160)")
                want = _choice_for(label, facts, lang)
                if not want or grp.locator("input[type=radio]:checked").count():
                    continue
                radio = grp.get_by_label(re.compile(want, re.I))
                if radio.count():
                    radio.first.check(timeout=2000)
                    done.append(f"{label[:30]} = {want}")
            except Exception:
                continue
        return done


def apply_label_js():
    from helper.apply import LABEL_JS
    return LABEL_JS


def _facts():
    import yaml
    from helper.apply import ROOT
    f = ROOT / "profile" / "facts.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}


def _choice_for(label, facts, lang):
    """Regex for the option to pick, from helper.answers (if present) or profile/facts.yaml."""
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
    if re.search(r"country|land\b|staat", L) and not re.search(r"phone|code", L):
        return r"^(germany|deutschland)$"
    if re.search(r"phone device|device type|telefontyp", L):
        return r"mobile|mobil"
    if re.search(r"gender|geschlecht", L):
        return r"^(female|weiblich)$"
    if re.search(r"how did you hear|source|quelle|aufmerksam", L):
        return r"linkedin|job board|jobbörse"
    if re.search(r"previously (worked|employed)|former employee|ehemals|früher.*beschäftigt|worked (at|for)", L):
        return r"^(no|nein)$"
    if re.search(r"sponsor|visa|work (permit|authori[sz])|arbeitserlaubnis", L):
        return r"^(no|nein)$" if re.search(r"require|need|benötig|sponsor", L) else r"^(yes|ja)$"
    if re.search(r"legally authori[sz]ed|eligible to work|berechtigt", L):
        return r"^(yes|ja)$"
    if re.search(r"relocat|umzug", L):
        return r"^(yes|ja)$"
    if re.search(r"willing to travel|reisebereit", L):
        return r"^(yes|ja)$"
    if re.search(r"veteran|ethnic|race|hispanic", L):
        return r"decline|do not wish|prefer not|keine angabe"
    if re.search(r"salutation|anrede|prefix", L):
        return r"^(ms\.?|frau)$"
    if re.search(r"english|englisch", L) and re.search(r"level|niveau|proficien", L):
        return r"fluent|c2|native|verhandlungssicher"
    if re.search(r"german|deutsch", L) and re.search(r"level|niveau|proficien", L):
        return r"intermediate|b1"
    if re.search(r"18|age|volljährig", L):
        return r"^(yes|ja)$"
    if re.search(r"driv|führerschein", L):
        return r"^(no|nein)$"
    if re.search(r"terms|privacy|datenschutz|consent|agree|zustimm|accept", L):
        return r"^(yes|ja|i agree|accept)"
    return None


SITE = Workday()
