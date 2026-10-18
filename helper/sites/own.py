"""Fallback for company-owned career sites and ATSs without an adapter: the generic filler alone.
Fixture: a local HTML form (apply/next/submit/confirmation) so the pipeline itself is tested offline."""
from pathlib import Path

from helper.sites.base import Site

FIXTURE_HTML = Path(__file__).resolve().parent / "fixture_own.html"


class Own(Site):
    name = "own"
    FIXTURE = FIXTURE_HTML.as_uri()

    def match(self, url, page=None):
        return True


SITE = Own()
