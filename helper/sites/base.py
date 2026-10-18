"""Site adapters for the application helper: one module per ATS that needs more than apply.fill().

An adapter is a module in helper/sites/ exposing a `Site` subclass (or instance) with:
    match(url) -> bool                      this adapter handles the page
    needs_account                           True: the portal needs a candidate login (vault + mail codes)
    open_form(page, ctx) -> bool            Apply -> ... until the first form page is visible
    fill(page, kit, cv, letter, text, lang, uploaded) -> (filled, unknown)   fill the current page (never Submit)
    submit_regex / next_regex / confirm_regex    button / confirmation text patterns for the generic loop
Everything a specific adapter does not override falls back to helper/apply.py's generic behaviour.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Site:
    name = "generic"
    needs_account = False
    submit_regex = re.compile(r"^\s*(submit|send)( (my |your )?application)?\s*$|^\s*(bewerbung )?(jetzt )?"
                              r"(absenden|abschicken|senden|einreichen|übermitteln)\s*$", re.I)
    next_regex = re.compile(r"^\s*(weiter|next|continue|fortfahren|save and continue|nächster schritt)\s*$", re.I)
    confirm_regex = re.compile(r"thank you for (your )?appl|application (has been )?(submitted|received|sent)|"
                               r"(vielen )?dank für ihre bewerbung|bewerbung (wurde |ist )?(erfolgreich )?"
                               r"(eingegangen|übermittelt|versendet)|successfully (submitted|applied)|"
                               r"you have successfully|congratulations", re.I)

    def match(self, url):
        return False

    def open_form(self, page, ctx=None):
        """Go from the job posting to the first form page. Returns True when a form is on screen."""
        from helper import apply
        return apply.click_apply(page)

    def fill(self, page, kit, cv, letter, text, lang, uploaded=None):
        from helper import apply
        return apply.fill(page, kit, cv, letter, text, lang, uploaded)


def all_sites():
    """Instances of every Site subclass found in helper/sites/*.py (except this file)."""
    import importlib
    out = []
    for f in sorted(HERE.glob("*.py")):
        if f.stem in ("base", "__init__"):
            continue
        mod = importlib.import_module(f"helper.sites.{f.stem}")
        site = getattr(mod, "SITE", None) or getattr(mod, "Site", None)
        if isinstance(site, type):
            site = site()
        if site is not None:
            out.append(site)
    return out


def for_url(url):
    for s in all_sites():
        try:
            if s.match(url):
                return s
        except Exception:
            continue
    return None
