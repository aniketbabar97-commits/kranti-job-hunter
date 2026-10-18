"""detect(url, page=None) -> Site adapter for the applicant-tracking system behind a job URL (own.py = fallback).
`python -m helper.sites` runs every adapter's fixture test and prints a table."""
import importlib

MODULES = ("personio", "join_com", "softgarden", "smartrecruiters", "recruitee", "greenhouse", "lever", "workday", "own")
_SITES = None


def all_sites():
    global _SITES
    if _SITES is None:
        _SITES = []
        for m in MODULES:
            try:
                mod = importlib.import_module(f"helper.sites.{m}")
                _SITES.append(getattr(mod, "SITE"))
            except Exception as ex:  # an adapter that fails to import must not stop the others
                print(f"   (site adapter {m} not loaded: {ex})")
    return _SITES


def detect(url, page=None):
    sites = all_sites()
    for s in sites:  # URL first (cheap, certain)
        if s.name != "own" and s.match(url):
            return s
    if page is not None:
        for s in sites:
            if s.name != "own" and getattr(s, "MARKER", None) and s.match("", page):
                return s
    return sites[-1]
