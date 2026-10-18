"""Fallback for company-owned career sites and ATSs without an adapter: the generic filler alone.
Fixture: a local HTML form (apply/next/submit/confirmation) so the pipeline itself is tested offline.

find_job(page, title, company): many kits only know the company's generic careers page. When that page has no form,
search the job there: type 2-3 key words of the title into the site's job search, score job links by token overlap
with the title, open the best one (>= 50 %); else follow one "Stellenangebote / Jobs / Offene Stellen / Karriere"
link and retry. Read-only: it only navigates, never fills or submits."""
import re
from pathlib import Path

from helper.sites.base import Site

FIXTURE_HTML = Path(__file__).resolve().parent / "fixture_own.html"
STOP = re.compile(r"\(?\b(m|w|d|f|x|div|h|all genders?|human|gn\*?|m/w/d|w/m/d|m/f/d|f/m/d|m/w/x|senior|junior|sr|jr|lead|"
                  r"principal|expert|experte|erfahrene[rn]?|mit|und|and|or|oder|der|die|das|for|für|in|im|at|bei|the|a|"
                  r"remote|hybrid|vollzeit|teilzeit|full.?time|part.?time|germany|deutschland|mwd|wmd)\b\)?", re.I)
PRIORITY = re.compile(r"sap commerce|hybris|sap cx|shopware|salesforce|spryker|commercetools", re.I)
JOBS_LINK = re.compile(r"^\s*(alle )?(stellenangebote|stellenbörse|offene stellen|jobs?( finden| suchen| & karriere)?|"
                       r"karriere|careers?|vacancies|open positions|job ?search|jobsuche|jobbörse|zu den jobs|alle jobs)\s*$", re.I)
SEARCH_INPUT = ("input[type=search], input[name*=search i], input[name*=query i], input[name=q], input[name*=keyword i], "
                "input[placeholder*=such i], input[placeholder*=search i], input[aria-label*=such i], input[aria-label*=search i], "
                "input[id*=search i], input[name*=suche i]")


def tokens(text):
    t = STOP.sub(" ", re.sub(r"[()\[\]/|,.:;–\-+&*]", " ", (text or "").lower()))
    return [w for w in t.split() if len(w) > 2 or w in ("cx", "ux", "ui", "qa")]


def keywords(title):
    """2-3 search words: the ATS-relevant phrase first (SAP Commerce, Hybris, SAP CX...), then the role noun."""
    m = PRIORITY.search(title or "")
    toks = tokens(title)
    if m:
        kw = m.group(0)
        rest = [t for t in toks if t not in kw.lower().split()]
        return " ".join([kw] + rest[:1])
    return " ".join(toks[:3])


def overlap(title, text):
    a, b = set(tokens(title)), set(tokens(text))
    return len(a & b) / len(a) if a else 0.0


def best_link(page, title):
    best, score = None, 0.0
    for frame in page.frames:
        try:
            links = frame.query_selector_all("a[href]")
        except Exception:
            continue
        for a in links[:1500]:
            try:
                txt = (a.inner_text() or "").strip()
                if not txt or len(txt) > 200 or not a.is_visible():
                    continue
                s = overlap(title, txt.split("\n")[0]) * 0.7 + overlap(title, txt) * 0.3
                if s > score:
                    best, score = a, s
            except Exception:
                continue
    return best, score


def search_box(page):
    for frame in page.frames:
        try:
            for el in frame.query_selector_all(SEARCH_INPUT):
                if el.is_visible() and el.is_enabled():
                    return el
        except Exception:
            continue
    return None


def _open(page, link):
    href = link.get_attribute("href") or ""
    ctx = page.context
    n = len(ctx.pages)
    link.click(timeout=5000)
    page.wait_for_timeout(3500)
    if len(ctx.pages) > n:  # opened in a new tab
        return ctx.pages[-1]
    return page if href else page


JOB_BOARD = re.compile(r"arbeitsagentur\.de|remotely\.de|stepstone\.|indeed\.|deutschland-stellenmarkt|fashionunited|"
                       r"jobware|stellenanzeigen\.de|kimeta|jooble", re.I)
EXTERNAL_LINK = re.compile(r"^\s*(externe seite öffnen|zur (externen )?(stellenanzeige|stellenbeschreibung|bewerbung|"
                           r"original-?anzeige)|zum (original|stellenangebot|arbeitgeber)|original-?anzeige|"
                           r"(jetzt )?(extern )?bewerben|apply( now)?( on company (website|site))?|"
                           r"(auf|zur) (der )?(unternehmens|firmen|arbeitgeber)-?(webseite|website|seite)( bewerben)?|"
                           r"weiter zur bewerbung|vollständige stellenbeschreibung)\s*$", re.I)


def follow_board(page):
    """A job-board posting (Arbeitsagentur, remotely, ...): open its link to the employer's own posting / form.
    Returns the new page or None."""
    if not JOB_BOARD.search(page.url or ""):
        return None
    host = page.url.split("://", 1)[-1].split("/", 1)[0]
    for frame in page.frames:
        try:
            for a in frame.query_selector_all("a[href]"):
                t = (a.inner_text() or "").strip()
                href = a.get_attribute("href") or ""
                if EXTERNAL_LINK.match(t) and a.is_visible() and href.startswith("http") and host not in href:
                    return _open(page, a)
        except Exception:
            continue
    return None


def find_job(page, title, company="", min_score=0.5, _depth=0):
    """Returns (page, found: bool, note). page may be a new tab."""
    from helper import apply
    apply.accept_cookies(page)
    if _depth < 2:  # job-board posting: hop to the employer's page first (at most twice: board -> board -> employer)
        nxt = follow_board(page)
        if nxt is not None:
            nxt.wait_for_timeout(1500)
            apply.accept_cookies(nxt)
            if JOB_BOARD.search(nxt.url):
                return find_job(nxt, title, company, min_score, _depth + 1)
            return nxt, True, f"followed job board -> {nxt.url[:60]}"
    # 0) the job may already be listed on this page
    link, score = best_link(page, title)
    if link is not None and score >= 0.75:
        return _open(page, link), True, f"listed on page ({score:.0%})"
    # 1) the site's job search
    box = search_box(page)
    if box is not None:
        try:
            kw = keywords(title)
            box.click(timeout=2000)
            box.fill(kw)
            box.press("Enter")
            page.wait_for_timeout(4000)
            apply.accept_cookies(page)
            link, score = best_link(page, title)
            if link is not None and score >= min_score:
                return _open(page, link), True, f"search '{kw}' -> {score:.0%}"
        except Exception:
            pass
    link, score2 = best_link(page, title)
    if link is not None and score2 >= min_score:
        return _open(page, link), True, f"listed ({score2:.0%})"
    # 2) one hop to the job list ("Stellenangebote", "Jobs", ...)
    if _depth == 0:
        for frame in page.frames:
            try:
                for a in frame.query_selector_all("a[href], button"):
                    t = (a.inner_text() or "").strip()
                    if JOBS_LINK.match(t) and a.is_visible():
                        nxt = _open(page, a)
                        return find_job(nxt, title, company, min_score, 1)
            except Exception:
                continue
    return page, False, f"not found (best {max(score, score2):.0%})"


class Own(Site):
    name = "own"
    FIXTURE = FIXTURE_HTML.as_uri()

    def match(self, url, page=None):
        return True


SITE = Own()
