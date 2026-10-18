"""JOIN (join.com/companies/<company>/<id>-<slug>). Verified live (Oct 2026): "Apply" leads to
/apply/authentication - an e-mail + "Continue" step guarded by reCAPTCHA (plus "Continue with Google"), i.e. an
account step before the form. Per the owner's rules that is a reason to park the job (no CAPTCHA solving).
Should JOIN show the plain form (some companies embed it on their own site), the generic filler handles it."""
import re

from helper.sites.base import Site


class JoinCom(Site):
    name = "join.com"
    FIXTURE = "https://join.com/companies/join/16817388-senior-backend-engineer"
    HOST = r"//(www\.)?join\.com/"
    MARKER = r"join\.com/companies/|data-join-widget"
    needs_account = True
    selectors = {"email": "input[name=email]", "first_name": "input[name=firstName]", "last_name": "input[name=lastName]",
                 "phone": "input[name=phone]", "cv": "input[type=file][name*=cv i], input[type=file][accept*=pdf]"}
    submit_regex = re.compile(r"^\s*(submit( application)?|send application|bewerbung (absenden|senden)|absenden|apply( now)?)\s*$", re.I)
    next_regex = re.compile(r"^\s*(next|weiter|continue)\s*$", re.I)  # "Continue" on the auth page is not a form step
    confirm_regex = re.compile(r"application (sent|submitted)|thank you for applying|bewerbung (gesendet|abgeschickt|versendet)|"
                               r"vielen dank für (ihre|deine) bewerbung", re.I)

    def account_step(self, page):
        return "/apply/authentication" in page.url or page.query_selector("input[type=password]") is not None or \
            page.get_by_role("button", name=re.compile(r"continue with google|sign in|log ?in|anmelden", re.I)).count() > 0

    def problems(self, page, uploads_needed, uploaded):
        why = super().problems(page, uploads_needed, uploaded)
        if self.account_step(page) and "account/password" not in why:
            why.append("account/password")
        return why


SITE = JoinCom()
