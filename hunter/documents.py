"""Render tailored CV and cover letter (HTML -> PDF), in the style of Kranti's own documents.

ATS rules: one column, real selectable text, standard section headings, reading order = document order,
no text inside images, no tables for layout, plain bullet points, dates as MM/YYYY text.
Personal contact data and the photo come from environment / GitHub secrets, never from the repository.
"""
import base64
import html
import os
from datetime import date
from pathlib import Path

e = html.escape

FONTS = Path(__file__).resolve().parent.parent / "profile" / "fonts"
# Carlito (open-source, metric-compatible with Calibri) as TrueType: crisp, selectable text in every PDF viewer and
# ATS parser. OTF/CFF fonts end up as blurry Type 3 glyphs in Chromium PDFs.
FONT_CSS = "".join(
    f"@font-face {{ font-family: 'CV Sans'; src: url('{(FONTS / f).as_uri()}') format('truetype'); "
    f"font-weight: {w}; font-style: {st}; }}\n"
    for f, w, st in [("Carlito-Regular.ttf", 400, "normal"), ("Carlito-Bold.ttf", 700, "normal"),
                     ("Carlito-Italic.ttf", 400, "italic"), ("Carlito-BoldItalic.ttf", 700, "italic")])

BASE_CSS = FONT_CSS + """
@page { size: A4 portrait; margin: 13mm 15mm 12mm 15mm; }
* { box-sizing: border-box; }
body { font-family: 'CV Sans', Calibri, Carlito, Arial, sans-serif; color: #1f2937; line-height: 1.32; font-size: 10.5pt;
       margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 23pt; font-weight: 700; color: #0f172a; margin: 0 0 1px 0; letter-spacing: 0.2px; }
h2 { font-size: 11.5pt; font-weight: 700; color: #0b4f8a; text-transform: uppercase; letter-spacing: 0.8px;
     border-bottom: 1.2px solid #0b4f8a; padding-bottom: 1px; margin: 11px 0 5px 0; break-after: avoid; }
.headline { font-size: 12pt; font-weight: 700; color: #0b4f8a; margin: 0 0 5px 0; }
.header { border-bottom: 2.5px solid #0b4f8a; padding-bottom: 7px; margin-bottom: 4px; overflow: hidden; }
.photo { float: right; width: 2.75cm; height: 3.4cm; object-fit: cover; border-radius: 4px; margin-left: 14px; }
.contact { font-size: 10pt; color: #374151; line-height: 1.42; }
a { color: #0b4f8a; text-decoration: none; }
p { margin: 0 0 5px 0; }
.job { margin-bottom: 8px; }
.job-title { font-weight: 700; color: #0f172a; font-size: 11pt; }
.job-dates { font-weight: 700; color: #4b5563; font-size: 10pt; float: right; }
.job-company { font-weight: 700; color: #0b4f8a; font-size: 10.3pt; margin-bottom: 1px; }
.tag { font-style: italic; color: #92400e; font-size: 9.6pt; margin-bottom: 1px; }
ul { margin: 2px 0 0 0; padding-left: 15px; }
li { margin-bottom: 2px; break-inside: avoid; }
.skill-row { margin-bottom: 2.5px; }
.skill-row b { color: #0f172a; }
"""

COVER_CSS = FONT_CSS + """
@page { size: A4 portrait; margin: 16mm 20mm 14mm 22mm; }
* { box-sizing: border-box; }
body { font-family: 'CV Sans', Calibri, Carlito, Arial, sans-serif; color: #1f2937; line-height: 1.42; font-size: 11pt;
       margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.header { border-bottom: 2.5px solid #0b4f8a; padding-bottom: 8px; margin-bottom: 18px; overflow: hidden; }
.photo { float: right; width: 2.3cm; height: 2.85cm; object-fit: cover; border-radius: 4px; margin-left: 14px; }
.sender-name { font-size: 21pt; font-weight: 700; color: #0f172a; letter-spacing: 0.2px; }
.sender-title { font-size: 11pt; font-weight: 700; color: #0b4f8a; margin: 1px 0 4px 0; }
.sender-contact { font-size: 9.8pt; color: #374151; line-height: 1.4; }
.recipient { font-size: 10.5pt; line-height: 1.35; margin-bottom: 6px; }
.date-line { text-align: right; font-size: 10.5pt; color: #374151; margin-bottom: 16px; }
.subject { font-size: 12pt; font-weight: 700; color: #0f172a; margin-bottom: 2px; }
.subject-sub { font-size: 10pt; color: #4b5563; margin-bottom: 16px; }
p { margin: 0 0 10px 0; text-align: left; }
ul.points { margin: 2px 0 12px 0; padding-left: 17px; }
ul.points li { margin-bottom: 6px; }
ul.points b { color: #0b4f8a; }
.signature { font-weight: 700; font-size: 11.5pt; color: #0f172a; margin-top: 26px; }
.attachments { margin-top: 18px; font-size: 9.6pt; color: #4b5563; }
"""

GERMAN_MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                 "November", "Dezember"]


def contact_info():
    return {"phone": os.getenv("CANDIDATE_PHONE", "[phone]"),
            "email": os.getenv("CANDIDATE_EMAIL", "[email]")}


def photo_tag(css_class="photo"):
    """Photo from CANDIDATE_PHOTO_B64 secret or a local (git-ignored) profile/photo.jpg."""
    data = os.getenv("CANDIDATE_PHOTO_B64", "").strip()
    local = Path(__file__).resolve().parent.parent / "profile" / "photo.jpg"
    if not data and local.exists():
        data = base64.b64encode(local.read_bytes()).decode()
    return f"<img class='{css_class}' src='data:image/jpeg;base64,{data}' alt=''>" if data else ""


CV_TEXT = {
    "en": {"summary": "Professional Summary", "skills": "Key Skills", "exp": "Work Experience", "cert": "Certifications",
           "edu": "Education", "lang": "Languages", "permit": "Valid German work permit",
           "start": "Earliest start: {d} (notice period)"},
    "de": {"summary": "Profil", "skills": "Kenntnisse", "exp": "Berufserfahrung", "cert": "Zertifizierungen",
           "edu": "Ausbildung", "lang": "Sprachen", "permit": "Gültige Arbeitserlaubnis für Deutschland",
           "start": "Frühester Eintritt: {d} (Kündigungsfrist)"},
}


def german(p, t):
    """Same CV in German: master_de.yaml has the same order of skills and bullets, so map by position."""
    import yaml
    de = yaml.safe_load((Path(__file__).resolve().parent.parent / "profile" / "master_de.yaml").read_text(encoding="utf-8"))
    labels_en, labels_de = list(p["skills"]), list(de["skills"])
    skills = {}
    for label, items in (t.get("skills") or p["skills"]).items():
        if label not in labels_en:
            continue
        en_items, de_items = p["skills"][label], de["skills"][labels_de[labels_en.index(label)]]
        skills[labels_de[labels_en.index(label)]] = [de_items[en_items.index(i)] for i in items if i in en_items]
    jobs = [{**job_en, **{k: job_de[k] for k in ("place", "dates", "bullets")}}
            for job_en, job_de in zip(p["jobs"], de["jobs"])]
    p2 = {**p, **{k: de[k] for k in ("location", "work_mode", "certifications", "education", "languages")}, "jobs": jobs}
    return p2, {**t, "skills": skills}


def render_cv(p, t, lang="en"):
    """p = master profile, t = tailoring {headline, summary, skills:{label:[...]}, bullet_order:{key:[idx]}}.
    lang "de": German headings and German master texts (headline/summary must already be German in t)."""
    c = contact_info()
    if lang == "de":
        p, t = german(p, t)
    L = CV_TEXT[lang]
    skills = t.get("skills") or p["skills"]
    out = [f"<!DOCTYPE html><html lang='{lang}'><head><meta charset='UTF-8'><title>{e(p['name'])} - CV</title>"
           f"<style>{BASE_CSS}</style></head><body>",
           f"<div class='header'>{photo_tag()}<h1>{e(p['name'])}</h1>",
           f"<div class='headline'>{e(t.get('headline') or p['headlines'][0])}</div>",
           "<div class='contact'>"
           f"{e(p['location'])} &nbsp;·&nbsp; {e(c['phone'])} &nbsp;·&nbsp; {e(c['email'])}<br>"
           f"{e(p['linkedin'])} &nbsp;·&nbsp; {L['permit']}<br>"
           f"{L['start'].format(d=e(str(p['earliest_start']).replace('/', '.')))} &nbsp;·&nbsp; {e(p['work_mode'])}"
           "</div></div>",
           f"<h2>{L['summary']}</h2>", f"<p>{e(t.get('summary') or p['summary'])}</p>",
           f"<h2>{L['skills']}</h2>"]
    out += [f"<div class='skill-row'><b>{e(label)}:</b> {e(', '.join(items))}</div>" for label, items in skills.items() if items]
    out.append(f"<h2>{L['exp']}</h2>")
    for job in p["jobs"]:
        order = t.get("bullet_order", {}).get(job["key"]) or list(range(len(job["bullets"])))
        out.append(f"<div class='job'><span class='job-dates'>{e(job['dates'])}</span>"
                   f"<div class='job-title'>{e(job['title'])}</div>"
                   f"<div class='job-company'>{e(job['company'])} — {e(job['place'])}</div>"
                   + "<ul>" + "".join(f"<li>{e(job['bullets'][i])}</li>" for i in order) + "</ul></div>")
    out += [f"<h2>{L['cert']}</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in p["certifications"]) + "</ul>",
            f"<h2>{L['edu']}</h2><p>{e(p['education'])}</p>",
            f"<h2>{L['lang']}</h2><p>{e(p['languages'])}</p></body></html>"]
    return "".join(out)


def render_cover(p, cl, job, lang, headline):
    """cl = {subject, salutation, hook, bullets:[{label,text}], gap, logistics, closing, contact?}."""
    c = contact_info()
    today = date.today()
    if lang == "de":
        when = f"Karlsruhe, {today.day}. {GERMAN_MONTHS[today.month - 1]} {today.year}"
        sign, encl, enc_txt = "Mit freundlichen Grüßen", "Anlage", "Lebenslauf"
        sub2 = "Frühester Eintritt: 16.12.2026 · Karlsruhe · gültige Arbeitserlaubnis"
        tel, mail = "Tel.", "E-Mail"
    else:
        when = f"Karlsruhe, {today.day} {today.strftime('%B %Y')}"
        sign, encl, enc_txt = "Kind regards,", "Enclosure", "CV"
        sub2 = "Earliest start: 16 December 2026 · Karlsruhe · valid German work permit"
        tel, mail = "Phone", "Email"
    recipient = [f"<b>{e(job['company'])}</b>"]
    if cl.get("contact"):
        recipient.append(e(cl["contact"]))
    if job.get("location"):
        recipient.append(e(job["location"].split(",")[0]))
    return "".join([
        f"<!DOCTYPE html><html lang='{lang}'><head><meta charset='UTF-8'><title>{e(cl['subject'])} - {e(p['name'])}</title>"
        f"<style>{COVER_CSS}</style></head><body>",
        f"<div class='header'>{photo_tag()}<div class='sender-name'>{e(p['name'])}</div>"
        f"<div class='sender-title'>{e(headline)}</div><div class='sender-contact'>"
        f"{tel} {e(c['phone'])} &nbsp;·&nbsp; {mail} {e(c['email'])}<br>"
        f"{e(p['linkedin'])} &nbsp;·&nbsp; Karlsruhe, {'Deutschland' if lang == 'de' else 'Germany'}</div></div>",
        f"<div class='recipient'>{'<br>'.join(recipient)}</div><div class='date-line'>{e(when)}</div>",
        f"<div class='subject'>{e(cl['subject'])}</div><div class='subject-sub'>{e(sub2)}</div>",
        f"<p>{e(cl['salutation'])}</p><p>{e(cl['hook'])}</p>",
        "<ul class='points'>" + "".join(f"<li><b>{e(b['label'])}:</b> {e(b['text'])}</li>" for b in cl["bullets"][:4]) + "</ul>",
        f"<p>{e(cl['gap'])}</p>" if cl.get("gap") else "",
        f"<p>{e(cl['logistics'])}</p>", f"<p>{e(cl.get('closing', ''))}</p>" if cl.get("closing") else "",
        f"<p style='margin-top:14px'>{e(sign)}</p><div class='signature'>{e(p['name'])}</div>",
        f"<div class='attachments'>{encl}: {enc_txt}</div></body></html>"])


def file_name(kind, job, lang):
    """Kranti_Chavan_CV_Maify_Senior-SAP-Commerce-Developer.pdf — easy to find among many downloads."""
    import re
    def clean(s, n):
        s = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß]+", "-", re.sub(r"\(.*?\)|\b(gmbh|ag|se|kg|co|mbh)\b", "", s, flags=re.I)).strip("-")
        return s if len(s) <= n else s[:n].rsplit("-", 1)[0]  # cut at a word boundary
    word = {("cv", "de"): "Lebenslauf", ("cv", "en"): "CV", ("cl", "de"): "Anschreiben", ("cl", "en"): "Cover_Letter"}[(kind, lang)]
    return f"Kranti_Chavan_{word}_{clean(job['company'], 25)}_{clean(job['title'], 48)}.pdf"


def to_pdf(html_files):
    """Print HTML files to PDF with headless Chromium (Playwright). Returns list of PDF paths."""
    from playwright.sync_api import sync_playwright
    exe = os.getenv("CHROMIUM_PATH") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
    pdfs = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        page = browser.new_page()
        for f in html_files:
            page.goto(Path(f).resolve().as_uri())
            out = str(Path(f).with_suffix(".pdf"))
            page.pdf(path=out, format="A4", print_background=True, prefer_css_page_size=True)
            pdfs.append(out)
        browser.close()
    return pdfs
