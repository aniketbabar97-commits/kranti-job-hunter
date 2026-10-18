"""softgarden: <company>.softgarden.io/job/<id>/<slug>  ->  <company>.career.softgarden.de/application/?jobId=<id>.
Verified live (softgarden.softgarden.io, Oct 2026), three steps on one URL:
  1 Lebenslauf: hidden input[name=cv-file] (CV), hidden input[name=attachments] (more files), cookie banner
    "ALLES AKZEPTIEREN", button "zum nächsten Schritt"
  2 Persönliche Angaben: applicationData.firstname / lastname / email / phone, react-select "Wie hast du diesen Job
    gefunden?", button "zum letzten Schritt"
  3 Zusätzliche Fragen: applicationData.answers.N.answer (text) and button groups for choices, then an
    "Anti-Roboter-Verifizierung - Hier klicken" CAPTCHA and submit "Bestätigen".
The CAPTCHA on step 3 means the job is parked for a human, with everything before it filled in."""
import re

from helper.sites.base import Site


class Softgarden(Site):
    name = "softgarden"
    FIXTURE = "https://softgarden.softgarden.io/job/62349294/Senior-Account-Executive-m-w-d-SaaS-Enterprise?l=de"
    HOST = r"\.softgarden\.(io|de)/"
    MARKER = r"softgarden"
    confirm_by_text = False  # the thank-you modal is always in the DOM (off-screen): see confirmed()
    selectors = {
        "first_name": "input[name='applicationData.firstname']", "last_name": "input[name='applicationData.lastname']",
        "email": "input[name='applicationData.email']", "phone": "input[name='applicationData.phone']",
        "cv": "input[name=cv-file]", "letter": "input[name=attachments]",
    }
    next_regex = re.compile(r"^\s*(zum (nächsten|letzten) schritt|weiter|next( step)?|continue|to the (next|last) step)\s*$", re.I)
    submit_regex = re.compile(r"^\s*(bestätigen|bewerbung (absenden|abschicken)|absenden|confirm|submit( application)?)\s*$", re.I)
    confirm_regex = re.compile(r"vielen dank für (ihre|deine) bewerbung|bewerbung (ist|wurde) (erfolgreich )?(eingegangen|übermittelt|"
                               r"versendet)|thank you for (your )?appl|application (has been )?(submitted|received)", re.I)

    def find_button(self, page, rx):
        """Steps stack on one page and earlier steps keep their buttons ("zum nächsten Schritt" stays visible on
        step 2): the current step's button is the LAST visible match."""
        last = None
        try:
            loc = page.get_by_role("button")
            for i in range(min(loc.count(), 80)):
                el = loc.nth(i)
                try:
                    if el.is_visible() and el.is_enabled() and rx.search(el.inner_text(timeout=500) or ""):
                        last = el
                except Exception:
                    continue
        except Exception:
            pass
        return last if last is not None else super().find_button(page, rx)

    def click_next(self, page):
        el = self.find_button(page, self.rx("next"))
        if el is None:
            return False
        try:
            el.click(timeout=5000)
            return True
        except Exception:
            return False

    def has_form(self, page):
        return "/application/" in page.url  # the job page has a search box; the form lives on career.softgarden.de

    def after_fill(self, page, lang, kit=None):
        """Step 3 "Zusätzliche Fragen": each item = question text div + a text input or a PickList (button group).
        Text: facts first, then AI (free text). PickList: only an option matching the fixed answer is clicked."""
        from helper import answers, apply
        for item in page.query_selector_all("[class*=ApplicationFormItem]"):
            try:
                qel = item.query_selector("[class*=ApplicationQuestion__Text]")
                if qel is None or not item.is_visible():
                    continue
                q = (qel.inner_text() or "").strip()
                required = q.endswith("*")
                inp = item.query_selector("input[name^='applicationData.answers'][name$='.answer']:not([readonly]), "
                                          "textarea[name^='applicationData.answers']")
                if inp is not None:
                    if inp.input_value().strip():
                        continue
                    a = answers.answer(q, lang)
                    if not a:
                        kind = "textarea" if inp.evaluate("e => e.tagName") == "TEXTAREA" else "text"
                        a = apply.ai_for(q, kit or {}, lang, required, kind)
                    if a:
                        inp.fill(a)
                    continue
                hidden = item.query_selector("input[class*=PickList__HiddenInput]")
                opts = item.query_selector_all("button[class*=PickList__Option]")
                if not opts or (hidden is not None and hidden.input_value().strip()):
                    continue
                a = answers.answer(q, lang)
                if not a:
                    continue
                if answers.is_yes(a):
                    rx = re.compile(r"^\s*(yes|ja)\b", re.I)
                elif answers.is_no(a):
                    rx = re.compile(r"^\s*(no|nein|keine?)\b", re.I)
                else:
                    rx = re.compile(re.escape(a.split(",")[0].strip()[:20]), re.I)
                hits = [o for o in opts if rx.search(o.inner_text() or "")]
                if len(hits) == 1:
                    hits[0].click()
            except Exception:
                continue

    def problems(self, page, uploads_needed, uploaded):
        why = super().problems(page, uploads_needed, uploaded)
        for item in page.query_selector_all("[class*=ApplicationFormItem]"):  # required PickList left empty
            try:
                qel = item.query_selector("[class*=ApplicationQuestion__Text]")
                hidden = item.query_selector("input[class*=PickList__HiddenInput]")
                if qel and hidden and item.is_visible() and (qel.inner_text() or "").strip().endswith("*") \
                        and not hidden.input_value().strip():
                    why.append("unanswered choice: " + qel.inner_text().strip()[:40])
            except Exception:
                continue
        return why

    def confirmed(self, page):
        """The thank-you modal is always in the DOM, parked off-screen to the right (x > viewport width) until the
        application is sent: only a copy inside the viewport counts."""
        try:
            vw = page.evaluate("() => window.innerWidth")
            loc = page.get_by_text(re.compile(r"bewerbung ist bei uns erfolgreich eingegangen|vielen dank für (ihre|deine) bewerbung", re.I))
            for i in range(min(loc.count(), 5)):
                box = loc.nth(i).bounding_box()
                if box and loc.nth(i).is_visible() and 0 <= box["x"] < vw and box["x"] + box["width"] > 0:
                    return True
        except Exception:
            pass
        return False


SITE = Softgarden()
