"""Personio career pages: <company>.jobs.personio.de|com/job/<id>  ->  form at /job/<id>/apply (one page).
Verified live (tado.jobs.personio.de, Oct 2026): inputs first_name, last_name, email, phone, location, available_from,
salary_expectations, custom_attribute_*; hidden file inputs documents.cv / documents.other (set_input_files works on
them); required is marked in the label text ("*", "(required)"), not by an attribute; submit "Submit Application" /
"Bewerbung absenden". Checkboxes (privacy) appear on some companies' forms -> tick all."""
import re

from helper.sites.base import Site


class Personio(Site):
    name = "personio"
    FIXTURE = "https://tado.jobs.personio.de/job/2502124"
    HOST = r"\.jobs\.personio\.(de|com)/"
    MARKER = r"Powered by Personio|personio\.(de|com)/.*apply"
    selectors = {
        "first_name": "input[name=first_name]", "last_name": "input[name=last_name]",
        "email": "input[name=email]", "phone": "input[name=phone]", "city": "input[name=location]",
        "start": "input[name=available_from]", "salary": "input[name=salary_expectations]",
        "cv": "input[name='documents.cv']", "letter": "input[name='documents.other'], input[name='documents.cover-letter']",
    }
    submit_regex = re.compile(r"^\s*(submit( application)?|bewerbung (absenden|abschicken)|absenden|jetzt bewerben)\s*$", re.I)
    confirm_regex = re.compile(r"thank you for (your )?appl|vielen dank für (ihre|deine) bewerbung|application (was|has been) "
                               r"(sent|submitted|received)|bewerbung (wurde )?(erfolgreich )?(versendet|übermittelt|eingegangen)", re.I)

    @staticmethod
    def form_url(url):
        m = re.match(r"(https?://[^/]+/job/\d+)", url or "")
        return m.group(1) + "/apply" if m and not url.rstrip("/").endswith("/apply") else None


SITE = Personio()
