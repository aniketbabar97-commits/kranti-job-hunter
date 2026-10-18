"""SAP SuccessFactors career sites (*.successfactors.eu / .com career portals, RMK "jobs.<company>.com" sites).
Techniques: helper/knowledge/successfactors_selectors.md.

VERIFIED read-only on career5.successfactors.eu (company=SAP, Oct 2026):
  sign in:   #username  #password  button "Sign In"  links "Create an account" (login_ns=register), "Forgot your password?"
  register:  #fbclc_userName #fbclc_emailConf #fbclc_pwd #fbclc_pwdConf #fbclc_fName #fbclc_lName
             select#fbclc_country  radios name=fbclc_searPref  checkboxes #fbclc_emailEnabled #fbclc_campaignEmailEnabled
             link/button #dataPrivacyId ("Read and acknowledge the data privacy statement")  button #fbclc_createAccountButton
  forgot:    #username (name=cEmail)  button "Submit"  -> mail with reset link
  cookie:    #truste-consent-button ("Understood") - an overlay that blocks every click until dismissed
  password rules: 8-20 chars, upper+lower, number or punctuation, no spaces/unicode.
NOTE jobs.sap.com itself moved to SmartRecruiters in 2026 (job URLs jobs.sap.com/en/jobs/<id>/...); this adapter
matches it only for the legacy /job/ and /talentcommunity/ paths.
ASSUMED (not verifiable without an account): application form name= attributes (cellPhone, address, zip, state),
label-anchored work history, generated ids ..._fieldNNN, "Apply" / "Save and Continue" button texts.
"""
import os
import re
import time

from helper.sites.base import Site

HOST = re.compile(r"\.successfactors\.(eu|com)|/sfcareer/|/talentcommunity/|/career\?company=|jobs\.sap\.com/(job|talentcommunity)/",
                  re.I)
APPLY = re.compile(r"^\s*(apply( now)?|jetzt bewerben|bewerben)\s*$", re.I)


def _host(page):
    return page.url.split("://", 1)[-1].split("/", 1)[0]


class SuccessFactors(Site):
    name = "successfactors"
    FIXTURE = "https://career5.successfactors.eu/career?company=SAP"
    needs_account = True
    submit_regex = re.compile(r"^\s*(apply|submit( application)?|bewerbung (ab)?senden|absenden|bewerben)\s*$", re.I)
    next_regex = re.compile(r"^\s*(save and continue|next|continue|weiter|speichern und weiter)\s*$", re.I)
    confirm_regex = re.compile(r"thank you for (applying|your application|your interest)|application (has been )?"
                               r"(submitted|received)|successfully (submitted|applied)|vielen dank für ihre bewerbung|"
                               r"bewerbung (wurde )?(eingereicht|übermittelt)", re.I)

    def match(self, url, page=None):
        return bool(HOST.search(url or ""))

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _cookies(page):
        for sel in ("#truste-consent-button", "#onetrust-accept-btn-handler", "button:has-text('Understood')",
                    "button:has-text('Accept All')", "button:has-text('Alle akzeptieren')"):
            try:
                loc = page.locator(sel)
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=2000)
                    page.wait_for_timeout(800)
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _vis(page, sel):
        loc = page.locator(sel)
        return loc.first if loc.count() and loc.first.is_visible() else None

    def _button(self, page, rx, timeout=4000):
        for loc in (page.get_by_role("button"), page.locator("input[type=submit], input[type=button], a.button, a.btn")):
            for i in range(min(loc.count(), 60)):
                el = loc.nth(i)
                try:
                    txt = el.inner_text(timeout=300) if el.evaluate("e => e.tagName") != "INPUT" else el.get_attribute("value")
                    if el.is_visible() and el.is_enabled() and rx.search((txt or "").strip()):
                        el.click(timeout=timeout)
                        return True
                except Exception:
                    continue
        return False

    def _link(self, page, rx):
        loc = page.get_by_role("link", name=rx)
        if loc.count():
            loc.first.click(timeout=4000)
            return True
        return False

    def _tick_all(self, page):
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

    @staticmethod
    def _password_ok(pw):
        return 8 <= len(pw) <= 20 and re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw) and \
            re.search(r"[\d\W]", pw) and not re.search(r"\s|[^\x21-\x7e]", pw)

    def _new_password(self, site):
        from helper import vault
        pw = vault.new_password(site)
        return pw if self._password_ok(pw) else vault.new_password(None)[:20]

    # ---------------------------------------------------------------- account
    def _email(self):
        return os.environ["CANDIDATE_EMAIL"]

    def on_sign_in(self, page):
        return self._vis(page, "#username") is not None and self._vis(page, "#password") is not None

    def _sign_in(self, page, email, pw):
        if not self.on_sign_in(page):
            return False
        page.fill("#username", email)
        page.fill("#password", pw)
        self._button(page, re.compile(r"^\s*sign in|anmelden\s*$", re.I))
        page.wait_for_timeout(5000)
        return not self.on_sign_in(page)

    def _create_account(self, page):
        from helper import vault
        if self._vis(page, "#fbclc_userName") is None:
            if not self._link(page, re.compile(r"create an account|create account|register|registrieren|konto erstellen", re.I)):
                return False
            page.wait_for_timeout(4000)
        email, pw = self._email(), self._new_password(_host(page))
        facts = _facts()
        name = facts.get("name", {})
        page.fill("#fbclc_userName", email)
        page.fill("#fbclc_emailConf", email)
        page.fill("#fbclc_pwd", pw)
        page.fill("#fbclc_pwdConf", pw)
        page.fill("#fbclc_fName", name.get("first", "Kranti"))
        page.fill("#fbclc_lName", name.get("last", "Chavan"))
        for opt in ("Germany", "Deutschland"):
            try:
                page.select_option("#fbclc_country", label=opt)
                break
            except Exception:
                continue
        # recruiter visibility: the widest option (first radio) - she wants to be found
        radios = page.locator("input[name=fbclc_searPref]")
        if radios.count() and not page.locator("input[name=fbclc_searPref]:checked").count():
            radios.first.check()
        self._tick_all(page)  # notification + campaign mails: yes (user rule: tick everything)
        dp = self._vis(page, "#dataPrivacyId")
        if dp is not None:  # the statement opens in a dialog with an Accept button
            dp.click(timeout=3000)
            page.wait_for_timeout(1500)
            self._button(page, re.compile(r"^\s*(accept|i accept|agree|akzeptieren|zustimmen|ok)\s*$", re.I))
            page.wait_for_timeout(800)
        t0 = time.time()
        page.click("#fbclc_createAccountButton")
        page.wait_for_timeout(5000)
        body = page.inner_text("body")[:6000]
        if re.search(r"already (exists|registered|in use|has an account)|bereits (registriert|vorhanden)", body, re.I):
            return "exists"
        if page.locator(".fieldError, .errorMessage, [class*=error]:visible").count() and self._vis(page, "#fbclc_userName"):
            return False
        vault.set(_host(page), email, pw)
        self._verify_mail(page, t0)
        return True

    def _verify_mail(self, page, since_ts):
        """SF sends an activation/verification link (sometimes a code). Follow it, then continue the flow."""
        from helper import mailcodes
        body = page.inner_text("body")[:6000].lower()
        if not re.search(r"verif|confirm|activat|bestätig", body) or not re.search(r"e-?mail", body):
            return True
        hint = "successfactors" if "successfactors" in _host(page) else _host(page).split(".")[-2]
        if re.search(r"code|pin", body):
            code = mailcodes.wait_for_code(hint, since_ts, timeout=180) or mailcodes.wait_for_code("", since_ts, timeout=30)
            if code:
                inp = self._vis(page, "input[type=text]:not([id^=fbclc]), input[type=tel]")
                if inp is not None:
                    inp.fill(code)
                    self._button(page, re.compile(r"verify|submit|continue|weiter|bestätigen", re.I))
                    page.wait_for_timeout(4000)
                    return True
        link = mailcodes.wait_for_link(hint, r"verif|activat|confirm|career|bestätig", since_ts, timeout=180)
        if link:
            page.goto(link, timeout=60000)
            page.wait_for_timeout(5000)
            return True
        return False

    def _reset_password(self, page, email):
        from helper import mailcodes, vault
        if self._vis(page, "input[name=cEmail]") is None:
            if not self._link(page, re.compile(r"forgot|passwort vergessen", re.I)):
                return False
            page.wait_for_timeout(3000)
        page.fill("input[name=cEmail], #username", email)
        t0 = time.time()
        self._button(page, re.compile(r"^\s*(submit|senden|absenden)\s*$", re.I))
        link = mailcodes.wait_for_link("successfactors", r"reset|password|passwort|career", t0, timeout=180) or \
            mailcodes.wait_for_link("", r"successfactors.*(reset|password)", t0, timeout=30)
        if not link:
            return False
        page.goto(link, timeout=60000)
        page.wait_for_timeout(5000)
        new = self._new_password(_host(page))
        pws = page.locator("input[type=password]")
        if pws.count() < 1:
            return False
        for i in range(min(pws.count(), 3)):
            if pws.nth(i).is_visible():
                pws.nth(i).fill(new)
        self._button(page, re.compile(r"^\s*(submit|save|reset|change|speichern|senden)", re.I))
        page.wait_for_timeout(5000)
        vault.set(_host(page), email, new)
        return self._sign_in(page, email, new) if self.on_sign_in(page) else True

    def ensure_account(self, page):
        from helper import vault
        acct = vault.get(_host(page))
        if acct and self.on_sign_in(page):
            return self._sign_in(page, acct["email"], acct["password"]) or self._reset_password(page, acct["email"])
        res = self._create_account(page)
        if res == "exists":
            self._link(page, re.compile(r"sign in|anmelden", re.I))
            page.wait_for_timeout(3000)
            return self._reset_password(page, self._email())
        return bool(res)

    # ---------------------------------------------------------------- flow
    def open_form(self, page, ctx=None):
        self._cookies(page)
        if not self.on_sign_in(page) and self._vis(page, "#fbclc_userName") is None:
            if not (self._link(page, APPLY) or self._button(page, APPLY)):
                from helper import apply
                apply.click_apply(page)
            page.wait_for_timeout(5000)
            if ctx is not None and len(ctx.pages) > 1:
                page = ctx.pages[-1]
            self._cookies(page)
        if self.on_sign_in(page) or self._vis(page, "#fbclc_userName") is not None:
            if not self.ensure_account(page):
                return False
            page.wait_for_timeout(4000)
            self._cookies(page)
        return page.locator("input:not([type=hidden]), textarea, select").count() > 0

    def fill(self, page, kit, cv, letter, text, lang, uploaded=None):
        from helper import apply
        files_done = uploaded if uploaded is not None else set()
        filled, unknown = [], []
        self._cookies(page)
        phone = os.environ.get("CANDIDATE_PHONE", "")
        facts = _facts()
        loc = facts.get("location", {})
        for name, val in (("cellPhone", phone), ("zip", str(loc.get("postal_code", ""))), ("city", loc.get("city", "")),
                          ("address", os.environ.get("CANDIDATE_STREET", ""))):
            el = self._vis(page, f"input[name={name}]")
            try:
                if el is not None and val and not el.input_value().strip():
                    el.fill(val)
                    filled.append(f"{name} = {val}")
            except Exception:
                pass
        for sel in page.locator("select[name=state], select[name=country]").all():
            try:
                for opt in ("Baden-Württemberg", "Baden-Wurttemberg", "Germany", "Deutschland"):
                    try:
                        sel.select_option(label=opt)
                        filled.append(f"select = {opt}")
                        break
                    except Exception:
                        continue
            except Exception:
                pass
        f, u = apply.fill(page, kit, cv, letter, text, lang, files_done)
        filled += f
        unknown += u
        filled += self._disability_no(page)
        self._tick_all(page)
        return filled, unknown

    def _disability_no(self, page):
        done = []
        for grp in page.locator("fieldset, [role=radiogroup], tr, div").all()[:400]:
            try:
                if not grp.locator("input[type=radio]").count():
                    continue
                label = grp.evaluate("e => e.innerText.slice(0,200)")
                if not re.search(r"disab|behinder", label, re.I) or grp.locator("input[type=radio]:checked").count():
                    continue
                r = grp.get_by_label(re.compile(r"^\s*(no|nein)\b", re.I))
                if r.count():
                    r.first.check(timeout=1500)
                    done.append("disability = No")
                    break
            except Exception:
                continue
        return done


def _facts():
    import yaml
    from helper.apply import ROOT
    f = ROOT / "profile" / "facts.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}


SITE = SuccessFactors()
