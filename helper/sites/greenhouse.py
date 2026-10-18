"""Greenhouse: job-boards.greenhouse.io/<board>/jobs/<id> (boards.greenhouse.io, or embedded via #grnhse_iframe on the
company site -> we navigate to the board URL instead). Selectors from knowledge/greenhouse_lever_selectors.md:
classic ids #first_name #last_name #email #phone #resume, #job_application_location (Google Places), react-select
`.select__container` on new boards, submit input[type=submit][data-trackingid=job-application-submit] /
button[type=submit].submit-step / #submit_app, confirmation `.confirmation__content` or URL /confirmation.
Fixture = Celonis board (Munich)."""
import re

from helper.sites.base import Site

EMBED = re.compile(r"boards\.greenhouse\.io/embed/job_app\?for=([\w-]+)&(?:amp;)?token=(\d+)", re.I)


class Greenhouse(Site):
    name = "greenhouse"
    FIXTURE = "https://job-boards.greenhouse.io/celonis/jobs/7819725003"
    HOST = r"(job-boards|boards)\.greenhouse\.io/"
    MARKER = r"grnhse_app|grnhse_iframe|gh_application_submission|boards\.greenhouse\.io"
    selectors = {
        "first_name": "#first_name, input[name='job_application[first_name]']",
        "last_name": "#last_name, input[name='job_application[last_name]']",
        "email": "#email, input[name='job_application[email]']", "phone": "#phone, input[name='job_application[phone]']",
        "cv": "#resume, #resume_fieldset input[type=file], input[type=file][name*=resume]",
        "letter": "#cover_letter, #cover_letter_fieldset input[type=file], input[type=file][name*=cover]",
        "letter_text": "#cover_letter_text, textarea[name*=cover_letter]",
    }
    submit_regex = re.compile(r"^\s*(submit( application)?|bewerbung (absenden|senden)|absenden)\s*$", re.I)
    confirm_regex = re.compile(r"thank you for applying|thank you for (your )?application|application (has been )?(submitted|received)|"
                               r"vielen dank für (ihre|deine) bewerbung", re.I)

    def open_form(self, page, ctx=None):
        from helper import apply
        apply.accept_cookies(page)
        try:  # embedded board on a company site: go to the board page itself
            m = EMBED.search(page.content()[:400000])
            if m and "greenhouse.io" not in page.url:
                page.goto(f"https://job-boards.greenhouse.io/{m.group(1)}/jobs/{m.group(2)}", timeout=60000)
                page.wait_for_timeout(2500)
        except Exception:
            pass
        if not page.query_selector("#first_name, input[name='job_application[first_name]']"):
            for sel in ("a[href$='#app'], a[href*='/jobs/'][href$='#application']", "#apply_button, a.apply-button"):
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click(timeout=3000)
                    page.wait_for_timeout(2000)
                    break
            else:
                apply.click_apply(page) and page.wait_for_timeout(2500)
        return self.has_form(page)

    def find_button(self, page, rx):
        for css in ("input[type=submit][data-trackingid=job-application-submit]", "button[type=submit].submit-step", "#submit_app"):
            el = page.query_selector(css)
            if el and el.is_visible() and el.is_enabled():
                return el
        return super().find_button(page, rx)

    def confirmed(self, page):
        return "/confirmation" in page.url or page.query_selector(".confirmation__content") is not None

    def after_fill(self, page, lang):
        """Greenhouse location typeahead: pick the first suggestion so the hidden fields get set."""
        try:
            loc = page.query_selector("#job_application_location, input[name*=location]")
            if loc and loc.is_visible() and loc.input_value().strip():
                page.wait_for_timeout(1200)
                item = page.query_selector(".pac-item, .select__option")
                if item:
                    item.click()
        except Exception:
            pass


SITE = Greenhouse()
