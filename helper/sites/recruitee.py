"""Recruitee: <company>.recruitee.com/o/<slug> (often behind a custom domain such as karriere.<company>.de);
the form is at /o/<slug>/c/new on the same page as the ad ("Bewerben" tab).
Verified live (bitcare, Oct 2026): candidate.name (full name), candidate.email, candidate.phone (+ country-code button),
file inputs candidate.photo (optional), candidate.cv, candidate.coverLetterFile, "Stattdessen hier schreiben" switches
the letter to a textarea, submit "Senden" / "Submit"; passive hCaptcha frames (captcha-assets.recruiteecdn.com) that
only challenge on submit - a challenge that becomes visible is a CAPTCHA -> park."""
import re

from helper.sites.base import Site


class Recruitee(Site):
    name = "recruitee"
    FIXTURE = "https://bitcare.recruitee.com/o/developer-softwareentwickler-java-mwd-fur-munchen-25"
    HOST = r"\.recruitee\.com/"
    MARKER = r"recruitee(cdn)?\.com|recruitee-inbox"
    selectors = {
        "name": "input[name='candidate.name']", "email": "input[name='candidate.email']",
        "phone": "input[name='candidate.phone']", "cv": "input[name='candidate.cv']",
        "letter": "input[name='candidate.coverLetterFile']",
    }
    submit_regex = re.compile(r"^\s*(senden|absenden|submit( application)?|send( application)?|bewerbung (absenden|senden))\s*$", re.I)
    confirm_regex = re.compile(r"vielen dank für (ihre|deine) bewerbung|thank you for (your )?appl|bewerbung (wurde )?(erfolgreich )?"
                               r"(versendet|übermittelt|eingegangen|gesendet)|application (has been )?(submitted|sent|received)|"
                               r"sie haben sich bereits auf diese stelle beworben", re.I)

    @staticmethod
    def form_url(url):
        m = re.match(r"(https?://[^/]+/o/[^/?#]+)", url or "")
        return m.group(1) + "/c/new" if m and "/c/new" not in url else None


SITE = Recruitee()
