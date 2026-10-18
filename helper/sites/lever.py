"""Lever: jobs.lever.co/<company>/<uuid>  ->  /apply. Selectors from knowledge/greenhouse_lever_selectors.md:
fields by name - name, email, phone, org, urls[LinkedIn], urls[GitHub], resume (#resume-upload-input), comments
(additional information = cover letter text), custom questions cards[<uuid>][field0], EEO eeo[*] (never guessed).
Location typeahead .dropdown-location writes JSON into hidden selectedLocation. Submit #btn-submit /
button[data-qa=btn-submit]; hCaptcha often appears on submit (-> park). Confirmation: URL /thanks,
"Application submitted!" / "Thanks for applying"."""
import re

from helper.sites.base import Site


class Lever(Site):
    name = "lever"
    FIXTURE = "https://jobs.lever.co/palantir/a8eb96f4-e39b-4c0f-b42e-610165b88f34"
    HOST = r"jobs(\.eu)?\.lever\.co/"
    MARKER = r"lever\.co/|input\.location-input"
    selectors = {
        "name": "input[name=name]", "email": "input[name=email]", "phone": "input[name=phone]",
        "linkedin": "input[name='urls[LinkedIn]']", "cv": "#resume-upload-input, input[name=resume]",
        "letter_text": "textarea[name=comments]", "city": "input.location-input[name=location]",
    }
    submit_regex = re.compile(r"^\s*(submit( application)?|bewerbung (absenden|senden)|absenden)\s*$", re.I)
    confirm_regex = re.compile(r"application submitted|thanks for applying|thank you for applying|vielen dank für (ihre|deine) bewerbung", re.I)

    @staticmethod
    def form_url(url):
        m = re.match(r"(https?://jobs(?:\.eu)?\.lever\.co/[^/?#]+/[0-9a-f-]{36})", url or "")
        return m.group(1) + "/apply" if m and not url.rstrip("/").endswith("/apply") else None

    def find_button(self, page, rx):
        for css in ("#btn-submit", "button[data-qa=btn-submit]"):
            el = page.query_selector(css)
            if el and el.is_visible() and el.is_enabled():
                return el
        return super().find_button(page, rx)

    def confirmed(self, page):
        return page.url.rstrip("/").endswith("/thanks")

    def after_fill(self, page, lang):
        try:  # location typeahead -> first result
            loc = page.query_selector("input.location-input[name=location]")
            if loc and loc.is_visible() and loc.input_value().strip() and not page.query_selector("input[name=selectedLocation][value]:not([value=''])"):
                page.wait_for_timeout(1200)
                item = page.query_selector(".dropdown-location .dropdown-results div")
                if item:
                    item.click()
        except Exception:
            pass


SITE = Lever()
