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
    selectors = {
        "first_name": "input[name='applicationData.firstname']", "last_name": "input[name='applicationData.lastname']",
        "email": "input[name='applicationData.email']", "phone": "input[name='applicationData.phone']",
        "cv": "input[name=cv-file]", "letter": "input[name=attachments]",
    }
    next_regex = re.compile(r"^\s*(zum (nächsten|letzten) schritt|weiter|next( step)?|continue|to the (next|last) step)\s*$", re.I)
    submit_regex = re.compile(r"^\s*(bestätigen|bewerbung (absenden|abschicken)|absenden|confirm|submit( application)?)\s*$", re.I)
    confirm_regex = re.compile(r"vielen dank für (ihre|deine) bewerbung|bewerbung (ist|wurde) (erfolgreich )?(eingegangen|übermittelt|"
                               r"versendet)|thank you for (your )?appl|application (has been )?(submitted|received)", re.I)

    def has_form(self, page):
        return "/application/" in page.url or super().has_form(page)

    def after_fill(self, page, lang):
        """Step 3: free-text questions ("Eintrittstermin") get answers from facts; choice buttons we know are clicked."""
        from helper import answers, apply
        for el in page.query_selector_all("input[name^='applicationData.answers']"):
            try:
                if not el.is_visible() or el.input_value().strip():
                    continue
                q = el.evaluate("e => { const p = e.closest('div'); const q = p && p.parentElement; "
                                "return (q ? q.innerText : '').split('\\n')[0]; }") or el.evaluate(apply.LABEL_JS)
                a = answers.answer(q, lang)
                if a:
                    el.fill(a)
            except Exception:
                continue


SITE = Softgarden()
