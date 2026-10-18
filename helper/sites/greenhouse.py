"""Greenhouse: job-boards.greenhouse.io/<board>/jobs/<id> (boards.greenhouse.io, or embedded via #grnhse_iframe on the
company site -> we navigate to the board URL instead). Selectors from knowledge/greenhouse_lever_selectors.md:
classic ids #first_name #last_name #email #phone #resume, #job_application_location (Google Places), react-select
`.select__container` on new boards, submit input[type=submit][data-trackingid=job-application-submit] /
button[type=submit].submit-step / #submit_app, confirmation `.confirmation__content` or URL /confirmation.
Fixture = Celonis board (Munich)."""
import os
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

    def after_fill(self, page, lang, kit=None):
        """Location typeahead (first suggestion), School typeahead (her university -> University of Pune -> Other),
        required "I confirm ..." selects (-> Yes / I confirm), campus-event selects (-> Not applicable / None)."""
        try:
            loc = page.query_selector("#job_application_location, input[name*=location]")
            if loc and loc.is_visible() and loc.input_value().strip():
                page.wait_for_timeout(1200)
                item = page.query_selector(".pac-item, .select__option")
                if item:
                    item.click()
        except Exception:
            pass
        from helper import answers
        uni = answers.facts()["education"]["university"]
        done = []
        for el in page.query_selector_all("input.select__input, input[id^=school--]"):
            try:
                if not el.is_visible() or self._rs_value(el):
                    continue
                label = (el.evaluate("e => { const l = document.getElementById(e.id + '-label') || "
                                     "e.closest('.select__container')?.querySelector('label'); return l ? l.innerText : ''; }") or "").strip()
                if re.match(r"school|university|universität|hochschule", label, re.I):
                    for typed, rx in ((uni, r"savitribai|phule"), ("University of Pune", r"^\s*(university of pune|pune university)\b"),
                                      ("Other", r"^\s*other\b")):
                        if self._rs_pick(page, el, typed, rx):
                            done.append(f"{label[:30]} = {self._rs_text(el)[:40]}")
                            break
                elif re.search(r"\bi (hereby )?confirm|i (have read|acknowledge|agree|understand)|true and correct|ich bestätige", label, re.I):
                    if self._rs_pick(page, el, "", r"^\s*(yes|ja|i confirm|confirm|i agree|agree|acknowledge|i acknowledge|"
                                                   r"i have read|accept|true)\b", only_one_ok=True):
                        done.append(f"{label[:30]} = {self._rs_text(el)[:20]}")
                elif re.search(r"campus event|career fair|karrieremesse|which event", label, re.I):
                    if self._rs_pick(page, el, "", r"not applicable|^\s*none\b|^\s*n/?a\b|keine|did not attend|haven'?t attended"):
                        done.append(f"{label[:30]} = {self._rs_text(el)[:20]}")
            except Exception:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
        return done

    @staticmethod
    def _rs_text(el):
        return el.evaluate("e => { const c = e.closest('.select__container, .select-shell'); "
                           "const v = c && c.querySelector('[class*=single-value], [class*=singleValue]'); return v ? v.innerText : ''; }") or ""

    @staticmethod
    def _rs_value(el):
        return el.evaluate("e => { const c = e.closest('.select__container, .select-shell'); "
                           "return !!(c && c.querySelector('[class*=single-value], [class*=singleValue], [class*=multi-value]')); }")

    def _rs_pick(self, page, el, typed, rx, only_one_ok=False):
        """Open a react-select, optionally type (async typeahead), click the first option matching rx."""
        rx = re.compile(rx, re.I)
        el.click()
        el.fill("")
        if typed:
            el.type(typed, delay=30)
        for _ in range(8):  # async options (school list) arrive late
            page.wait_for_timeout(500)
            opts = [o for o in page.query_selector_all(".select__option, [role=option]") if o.is_visible()]
            texts = [(o.inner_text() or "").strip() for o in opts]
            if any(re.search(r"loading|wird geladen", t, re.I) for t in texts):
                continue
            hit = [o for o, t in zip(opts, texts) if rx.search(t)]
            if typed and os.environ.get("HELPER_DEBUG"):
                print("      options for", typed, texts[:8])
            if not hit and only_one_ok and len(opts) == 1 and not re.search(r"no options|no results", texts[0], re.I):
                hit = opts
            if hit:
                hit[0].click()
                page.wait_for_timeout(300)
                return True
            if opts:
                break
        el.fill("")
        page.keyboard.press("Escape")
        return False


SITE = Greenhouse()
