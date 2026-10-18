"""Lever: jobs.lever.co/<company>/<uuid>  ->  /apply. Selectors from knowledge/greenhouse_lever_selectors.md:
fields by name - name, email, phone, org, urls[LinkedIn], urls[GitHub], resume (#resume-upload-input), comments
(additional information = cover letter text), custom questions cards[<uuid>][field0], EEO eeo[*] (never guessed).
Location typeahead .dropdown-location writes JSON into hidden selectedLocation. Submit #btn-submit /
button[data-qa=btn-submit]; hCaptcha often appears on submit (-> park). Confirmation: URL /thanks,
"Application submitted!" / "Thanks for applying"."""
import re

from helper.sites.base import Site


class Lever(Site):
    name = "lever"
    FIXTURE = "https://jobs.lever.co/palantir/a8eb96f4-e39b-4c0f-b42e-610165b88f34"
    HOST = r"jobs(\.eu)?\.lever\.co/"
    MARKER = r"lever\.co/|input\.location-input"
    selectors = {
        "name": "input[name=name]", "email": "input[name=email]", "phone": "input[name=phone]",
        "linkedin": "input[name='urls[LinkedIn]']", "cv": "#resume-upload-input, input[name=resume]",
        "letter_text": "textarea[name=comments]", "city": "input.location-input[name=location]",
    }
    submit_regex = re.compile(r"^\s*(submit( application)?|bewerbung (absenden|senden)|absenden)\s*$", re.I)
    confirm_regex = re.compile(r"application submitted|thanks for applying|thank you for applying|vielen dank für (ihre|deine) bewerbung", re.I)

    @staticmethod
    def form_url(url):
        m = re.match(r"(https?://jobs(?:\.eu)?\.lever\.co/[^/?#]+/[0-9a-f-]{36})", url or "")
        return m.group(1) + "/apply" if m and not url.rstrip("/").endswith("/apply") else None

    def find_button(self, page, rx):
        for css in ("#btn-submit", "button[data-qa=btn-submit]"):
            el = page.query_selector(css)
            if el and el.is_visible() and el.is_enabled():
                return el
        return super().find_button(page, rx)

    def confirmed(self, page):
        return page.url.rstrip("/").endswith("/thanks")

    def after_fill(self, page, lang, kit=None):
        """Location typeahead (typed + suggestion clicked, else Lever clears it), then the custom-question cards."""
        from helper import answers
        done = []
        try:
            loc = page.query_selector("input.location-input[name=location]")
            chosen = page.evaluate("() => { const h = document.querySelector('input[name=selectedLocation]'); return !!(h && h.value); }")
            if loc and loc.is_visible() and not chosen:
                city = answers.facts()["location"]["city"]
                loc.click()
                loc.fill("")
                loc.type(city, delay=60)
                page.wait_for_timeout(1500)
                item = page.query_selector("div.dropdown-location, .dropdown-results div")
                if item and item.is_visible():
                    item.click()
                    page.wait_for_timeout(500)
        except Exception:
            pass
        done += self._cards(page, lang, kit)
        return done

    QUESTION_JS = """e => { const li = e.closest('li.application-question') || e.closest('.application-question');
      const t = li && li.querySelector('.application-label .text, .application-label');
      return t ? t.innerText.trim() : ''; }"""

    def _cards(self, page, lang, kit):
        """Custom questions cards[<uuid>][fieldN]: answers.answer() first; free text -> AI; uncovered yes/no -> park."""
        from helper import answers, apply
        done, radios = [], {}
        for el in page.query_selector_all("[name^='cards[']"):
            try:
                if not el.is_visible():
                    continue
                kind = (el.get_attribute("type") or el.evaluate("e => e.tagName")).lower()
                name = el.get_attribute("name")
                q = re.sub(r"\s*✱\s*$", "", el.evaluate(self.QUESTION_JS) or "").strip()
                required = el.get_attribute("required") is not None or "✱" in (el.evaluate(self.QUESTION_JS) or "")
                if not q:
                    continue
                if kind == "radio":
                    radios.setdefault(name, (q, []))[1].append(el)
                    continue
                if kind == "checkbox":
                    continue  # multi-choice (languages): apply.tick_consent ticks hers only
                if kind in ("select", "select-one"):
                    if el.evaluate("e => e.selectedIndex > 0 && e.value !== ''"):
                        continue
                    if re.search(r"universit|school|college|hochschule", q, re.I):
                        uni = answers.facts()["education"]["university"]
                        for want in (uni, "University of Pune", "Pune University", "Other"):
                            if apply.pick_option(el, want, q):
                                done.append(f"{q[:30]} = {want}")
                                break
                        continue
                    want = answers.answer(q, lang)
                    if want and apply.pick_option(el, want, q):
                        done.append(f"{q[:30]} = {want[:20]}")
                    continue
                if el.input_value().strip():
                    continue
                a = answers.answer(q, lang)
                if not a:
                    a = apply.ai_for(q, kit or {}, lang, required, "textarea" if kind == "textarea" else "text")
                if a:
                    el.fill(a)
                    done.append(f"{q[:30]} = {a[:30]}")
            except Exception:
                continue
        for name, (q, els) in radios.items():
            try:
                if any(e.is_checked() for e in els):
                    continue
                want = answers.answer(q, lang)
                if not want:
                    continue  # a yes/no question facts.yaml does not cover: parked (problems() reports it)
                rx = re.compile(r"^\s*(yes|ja)\b" if answers.is_yes(want) else r"^\s*(no|nein)\b" if answers.is_no(want)
                                else re.escape(want[:20]), re.I)
                hits = [e for e in els if rx.search(e.get_attribute("value") or e.evaluate("e => e.parentElement.innerText") or "")]
                if len(hits) == 1:
                    hits[0].check(timeout=2000)
                    done.append(f"{q[:30]} = {hits[0].get_attribute('value')[:15]}")
            except Exception:
                continue
        return done

    def problems(self, page, uploads_needed, uploaded):
        """Generic problems use bad labels on cards; report required unanswered cards by their question text."""
        why = [w for w in super().problems(page, uploads_needed, uploaded) if not w.startswith("empty: | |")]
        seen = set()
        for el in page.query_selector_all("[name^='cards['][required]"):
            try:
                name = el.get_attribute("name")
                if name in seen or not el.is_visible():
                    continue
                seen.add(name)
                kind = (el.get_attribute("type") or el.evaluate("e => e.tagName")).lower()
                group = page.query_selector_all(f"[name=\"{name}\"]")
                if kind in ("radio", "checkbox"):
                    ok = any(g.is_checked() for g in group)
                elif kind in ("select", "select-one"):
                    ok = el.evaluate("e => e.selectedIndex > 0 && e.value !== ''")
                else:
                    ok = bool(el.input_value().strip())
                if not ok:
                    why.append("unanswered: " + (el.evaluate(self.QUESTION_JS) or name)[:50])
            except Exception:
                continue
        return why


SITE = Lever()
