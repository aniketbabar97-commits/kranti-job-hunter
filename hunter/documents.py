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

BASE_CSS = """
@page { size: A4 portrait; margin: 12mm 14mm; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; color: #1e293b; line-height: 1.4; font-size: 9.6pt; margin: 0; }
h1 { font-size: 20pt; font-weight: 800; color: #0f172a; margin: 0 0 2px 0; text-transform: uppercase; letter-spacing: -0.3px; }
h2 { font-size: 10.8pt; font-weight: 700; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px;
     border-bottom: 1px solid #cbd5e1; padding-bottom: 2px; margin: 12px 0 6px 0; break-after: avoid; }
.headline { font-size: 10.5pt; font-weight: 700; color: #0284c7; margin: 0 0 6px 0; }
.header { border-bottom: 2px solid #0284c7; padding-bottom: 8px; margin-bottom: 10px; overflow: hidden; }
.photo { float: right; width: 2.8cm; height: 3.5cm; object-fit: cover; border-radius: 6px; border: 1px solid #cbd5e1; margin-left: 12px; }
.contact { font-size: 9.2pt; color: #334155; line-height: 1.5; }
.contact a, a { color: #0284c7; text-decoration: none; }
p { margin: 0 0 6px 0; }
.job { margin-bottom: 9px; }
.job-title { font-weight: 700; color: #0f172a; font-size: 10pt; }
.job-dates { font-weight: 600; color: #475569; font-size: 9pt; float: right; }
.job-company { font-weight: 600; color: #0284c7; font-size: 9.4pt; margin-bottom: 2px; }
.tag { font-style: italic; color: #b45309; font-weight: 600; font-size: 8.8pt; margin-bottom: 2px; }
ul { margin: 2px 0 0 0; padding-left: 16px; }
li { margin-bottom: 2.5px; font-size: 9.2pt; break-inside: avoid; }
.skill-row { margin-bottom: 3px; font-size: 9.2pt; }
"""

COVER_CSS = """
@page { size: A4 portrait; margin: 18mm 20mm 15mm 20mm; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #111827; line-height: 1.55; font-size: 9.8pt; margin: 0; }
.header { margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #e5e7eb; border-top: 4px solid #0284c7; padding-top: 10px; overflow: hidden; }
.photo { float: right; width: 2.4cm; height: 3cm; object-fit: cover; border-radius: 6px; border: 1px solid #cbd5e1; margin-left: 12px; }
.sender-name { font-size: 16pt; font-weight: 800; color: #0f172a; text-transform: uppercase; margin-bottom: 3px; }
.sender-title { font-size: 9pt; font-weight: 600; color: #0284c7; margin-bottom: 6px; }
.sender-contact { font-size: 8.5pt; color: #4b5563; line-height: 1.45; }
.recipient { margin-bottom: 8px; font-size: 9pt; color: #1f2937; line-height: 1.4; }
.date-line { font-size: 9pt; color: #6b7280; margin-bottom: 16px; }
.subject { background: #f8fafc; border-left: 4px solid #0284c7; padding: 8px 12px; margin-bottom: 18px; }
.subject-title { font-size: 11pt; font-weight: 700; color: #0f172a; }
.subject-subtitle { font-size: 8.5pt; color: #475569; font-style: italic; }
p { margin: 0 0 10px 0; text-align: justify; color: #334155; }
.skills { margin: 12px 0; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; }
.skills ul { margin: 0; padding-left: 16px; }
.skills li { font-size: 8.8pt; color: #1e293b; margin-bottom: 5px; line-height: 1.4; }
.signature { font-weight: 700; font-size: 10pt; color: #0f172a; margin-top: 22px; }
.attachments { margin-top: 15px; font-size: 8.5pt; color: #64748b; border-top: 1px dashed #e2e8f0; padding-top: 8px; }
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


def render_cv(p, t):
    """p = master profile, t = tailoring {headline, summary, skills:{label:[...]}, bullet_order:{key:[idx]}}."""
    c = contact_info()
    skills = t.get("skills") or p["skills"]
    out = [f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><title>{e(p['name'])} - CV</title>"
           f"<style>{BASE_CSS}</style></head><body>",
           f"<div class='header'>{photo_tag()}<h1>{e(p['name'])}</h1>",
           f"<div class='headline'>{e(t.get('headline') or p['headlines'][0])}</div>",
           "<div class='contact'>"
           f"Location: {e(p['location'])} | Phone: {e(c['phone'])} | Email: {e(c['email'])}<br>"
           f"LinkedIn: {e(p['linkedin'])}<br>Work Authorization: {e(p['work_authorization'])}<br>"
           f"Work Mode: {e(p['work_mode'])} | Notice Period: {e(p['notice'])}</div></div>",
           "<h2>Professional Summary</h2>", f"<p>{e(t.get('summary') or p['summary'])}</p>",
           "<h2>Key Skills</h2>"]
    out += [f"<div class='skill-row'><b>{e(label)}:</b> {e(', '.join(items))}</div>" for label, items in skills.items() if items]
    out.append("<h2>Work Experience</h2>")
    for job in p["jobs"]:
        order = t.get("bullet_order", {}).get(job["key"]) or list(range(len(job["bullets"])))
        out.append(f"<div class='job'><span class='job-dates'>{e(job['dates'])}</span>"
                   f"<div class='job-title'>{e(job['title'])}</div>"
                   f"<div class='job-company'>{e(job['company'])} — {e(job['place'])}</div>"
                   + (f"<div class='tag'>{e(job['note'])}</div>" if job.get("note") else "")
                   + "<ul>" + "".join(f"<li>{e(job['bullets'][i])}</li>" for i in order) + "</ul></div>")
    out += ["<h2>Certifications</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in p["certifications"]) + "</ul>",
            f"<h2>Education</h2><p>{e(p['education'])}</p>",
            f"<h2>Languages</h2><p>{e(p['languages'])}</p></body></html>"]
    return "".join(out)


def render_cover(p, cl, job, lang, headline):
    """cl = {subject, salutation, hook, bullets:[{label,text}], gap, logistics, closing}."""
    c = contact_info()
    today = date.today()
    if lang == "de":
        when = f"Karlsruhe, {today.day}. {GERMAN_MONTHS[today.month - 1]} {today.year}"
        sign, encl, enc_txt = "Mit freundlichen Grüßen", "Anlagen", "Lebenslauf, Zertifikate"
        sub2 = "Karlsruhe | Kündigungsfrist, letzter Arbeitstag 15.12.2026"
    else:
        when = f"Karlsruhe, {today.day} {today.strftime('%B %Y')}"
        sign, encl, enc_txt = "Kind regards,", "Enclosures", "CV, certificates"
        sub2 = "Karlsruhe | Serving notice period, last working day 15 December 2026"
    recipient = f"<b>{e(job['company'])}</b>" + (f"<br>{e(job['location'])}" if job.get("location") else "")
    return "".join([
        f"<!DOCTYPE html><html lang='{lang}'><head><meta charset='UTF-8'><title>{e(cl['subject'])} - {e(p['name'])}</title>"
        f"<style>{COVER_CSS}</style></head><body>",
        f"<div class='header'>{photo_tag()}<div class='sender-name'>{e(p['name'])}</div>"
        f"<div class='sender-title'>{e(headline)}</div><div class='sender-contact'>"
        f"Karlsruhe &bull; <b>{'Tel' if lang == 'de' else 'Phone'}:</b> {e(c['phone'])}<br>"
        f"<b>{'E-Mail' if lang == 'de' else 'Email'}:</b> {e(c['email'])}<br><b>LinkedIn:</b> {e(p['linkedin'])}</div></div>",
        f"<div class='recipient'>{recipient}</div><div class='date-line'>{e(when)}</div>",
        f"<div class='subject'><div class='subject-title'>{e(cl['subject'])}</div><div class='subject-subtitle'>{e(sub2)}</div></div>",
        f"<p>{e(cl['salutation'])}</p><p>{e(cl['hook'])}</p>",
        "<div class='skills'><ul>" + "".join(f"<li><b>{e(b['label'])}:</b> {e(b['text'])}</li>" for b in cl["bullets"][:4]) + "</ul></div>",
        f"<p>{e(cl['gap'])}</p>" if cl.get("gap") else "",
        f"<p>{e(cl['logistics'])}</p>", f"<p>{e(cl.get('closing', ''))}</p>" if cl.get("closing") else "",
        f"<p>{e(sign)}</p><div class='signature'>{e(p['name'])}</div>",
        f"<div class='attachments'><b>{encl}:</b> {enc_txt}</div></body></html>"])


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
