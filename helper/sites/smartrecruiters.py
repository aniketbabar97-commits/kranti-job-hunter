"""SmartRecruiters: jobs.smartrecruiters.com/<Company>/<id>-<slug>  ->  "I'm interested" ->
jobs.smartrecruiters.com/oneclick-ui/company/<Company>/publication/<uuid>.
The oneclick form (web components spl-input, inputs in open shadow DOM, which Playwright CSS pierces) has ids
first-name-input, last-name-input, email-input, confirm-email-input, phone, linkedin-input, website-input,
hiring-manager-message-input, location-autocomplete-search-input, a resume drop zone with input[type=file], consent
checkboxes, then "Submit" / "Bewerbung absenden" (knowledge/greenhouse_lever_selectors.md).
Live check (Oct 2026): the oneclick page serves a DataDome CAPTCHA to automated Chromium (geo.captcha-delivery.com),
so from this helper the job is parked with "CAPTCHA"; her own Chrome profile usually passes without a challenge."""
import re

from helper.sites.base import Site


class SmartRecruiters(Site):
    name = "smartrecruiters"
    FIXTURE = "https://jobs.smartrecruiters.com/BoschGroup/744000155476967-working-student-in-software-development-python-f-m-div-"
    HOST = r"(jobs\.smartrecruiters\.com|smartr\.me)/"
    MARKER = r"oc-oneclick-form|smartrecruiters\.com/oneclick"
    selectors = {
        "first_name": "#first-name-input, input[name=firstName]", "last_name": "#last-name-input, input[name=lastName]",
        "email": "#email-input, input[name=email]", "phone": "#phone-input, input[type=tel]",
        "linkedin": "#linkedin-input", "letter_text": "#hiring-manager-message-input",
        "cv": "input[type=file]",
    }
    submit_regex = re.compile(r"^\s*(submit( application)?|bewerbung (absenden|senden)|absenden|apply)\s*$", re.I)
    next_regex = re.compile(r"^\s*(next|weiter|continue|fortfahren)\s*$", re.I)
    confirm_regex = re.compile(r"thank you for (your )?(interest|appl)|application (has been )?(submitted|received|sent)|"
                               r"vielen dank für (ihre|deine) bewerbung|bewerbung (wurde )?(erfolgreich )?(übermittelt|versendet)", re.I)

    @staticmethod
    def form_url(url):
        m = re.match(r"(https?://jobs\.smartrecruiters\.com/[^/?#]+/\d+[^?#]*)", url or "")
        return m.group(1) + "?oga=true" if m and "oneclick-ui" not in url and "oga=true" not in url else None

    def fill(self, page, kit, cv, letter, text, lang, uploaded=None):
        filled, unknown = super().fill(page, kit, cv, letter, text, lang, uploaded)
        try:  # confirm-email field (no label the generic matcher trusts)
            el = page.query_selector("#confirm-email-input")
            if el and el.is_visible() and not el.input_value().strip():
                import os
                el.fill(os.environ["CANDIDATE_EMAIL"])
                filled.append("confirm e-mail")
        except Exception:
            pass
        return filled, unknown


SITE = SmartRecruiters()
