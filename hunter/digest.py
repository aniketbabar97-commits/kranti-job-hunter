"""Build and send the HTML digest email."""
import base64
import html
import logging
import os
import smtplib
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

log = logging.getLogger(__name__)

SECTIONS = [(80, "🎯 Strong match"), (60, "👍 Good fit / can learn"), (30, "👀 Worth a look"), (0, "🗂 Low match (titles only)")]


AGES = [(1, "🆕 ≤1 day"), (3, "2–3 days"), (7, "4–7 days"), (10**6, "7+ days")]


LONG_OPEN_DAYS = 30


def days_open(job):
    try:
        return (date.today() - date.fromisoformat(str(job.get("posted", ""))[:10])).days
    except ValueError:
        return None


def age_label(job):
    days = days_open(job)
    if days is None:
        return "date unknown"
    if days >= LONG_OPEN_DAYS:
        return f"⏳ open {days} days"
    return next(label for limit, label in AGES if days <= limit)


def _age_rank(job):
    days = days_open(job)
    return 10**6 if days is None else days


LANGS = [("en", "🇬🇧 English-speaking jobs"), ("de", "🇩🇪 German-speaking jobs")]


APPLIED_BADGES = {"applied": [("✅ Applied", "#dafbe1")], "company": [("↺ Applied at this company before", "#fff8c5")]}
CARD_MIN = 60  # jobs below this are only counted in the email and listed in the full record


def _base_url():
    repo = os.getenv("GITHUB_REPOSITORY")
    return f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{repo}" if repo else ""


def _card(j, e):
    strong = j["score"] >= 80
    color = "#1a7f37" if strong else "#0969da"
    age = age_label(j)
    lang = "English OK" if j.get("lang") == "en" else "German needed"
    meta = " · ".join(x for x in [j["location"], "🏠 Remote/hybrid" if j["remote"] else "", j["salary"]] if x)
    badges = "".join(
        f"<span style='display:inline-block;background:{bg};color:#24292f;border-radius:10px;padding:2px 8px;"
        f"margin:0 4px 4px 0;font-size:12px'>{e(t)}</span>"
        for t, bg in [(age, "#dafbe1" if age.startswith("🆕") else "#ffebe9" if age.startswith("⏳") else "#eaeef2"), (lang, "#eaeef2"), (j["source"], "#eaeef2")]
        + APPLIED_BADGES.get(j.get("applied", ""), []))
    return (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border:1px solid #d0d7de;"
        "border-radius:8px;margin:0 0 12px 0;border-collapse:separate'><tr>"
        f"<td width='56' valign='top' style='padding:14px 0 14px 14px'><div style='width:44px;height:44px;line-height:44px;"
        f"border-radius:22px;background:{color};color:#fff;text-align:center;font-weight:bold;font-size:16px'>{j['score']}</div></td>"
        "<td valign='top' style='padding:12px 14px 12px 10px;font-family:Arial,sans-serif'>"
        f"<a href='{e(j['url'])}' style='font-size:16px;font-weight:bold;color:#24292f;text-decoration:none'>{e(j['title'])}</a>"
        f"<div style='font-size:14px;color:#24292f;margin:3px 0'><b>{e(j['company'])}</b></div>"
        f"<div style='font-size:13px;color:#57606a;margin-bottom:6px'>{e(meta)}</div>"
        f"<div>{badges}</div>"
        f"<div style='font-size:13px;color:#24292f;margin:4px 0 6px 0'>✔ {e(j.get('why', ''))}</div>"
        + (f"<div style='font-size:13px;color:#24292f;margin:0 0 6px 0'>💡 {e(j['tip'])}</div>" if j.get("tip") else "")
        + (f"<div style='font-size:13px;margin:0 0 6px 0'>✉ <a href='mailto:{e(j['contact'].split(',')[0].strip())}'>{e(j['contact'])}</a></div>"
           if j.get("contact") else "")
        + "<div style='height:4px'></div>"
        f"<a href='{e(j['url'])}' style='display:inline-block;background:{color};color:#fff;text-decoration:none;"
        "padding:6px 14px;border-radius:6px;font-size:13px;font-weight:bold'>Open job →</a>"
        + (f" <a href='{_base_url()}/blob/main/{e(j['kit'])}' style='display:inline-block;border:1px solid {color};"
           f"color:{color};text-decoration:none;padding:5px 12px;border-radius:6px;font-size:13px;font-weight:bold;"
           "margin-left:6px'>📝 Application kit</a>" if j.get("kit") and _base_url() else "")
        + ("<div style='font-size:12px;color:#1a7f37;margin-top:6px'>📎 Tailored CV + cover letter attached to this email</div>"
           if j.get("attachments") else "")
        + "</td></tr></table>")


def _record_links():
    base = _base_url()
    if not base:
        return ""
    links = [f"<a href='{base}/blob/main/JOBS.md' style='color:#0969da'>📒 Full record of every job (sorted)</a>",
             f"<a href='{base}/blob/main/data/jobs_log.csv' style='color:#0969da'>spreadsheet</a>"]
    links.append(f"<a href='{base}/edit/main/APPLIED.md' style='color:#0969da'>✏️ mark applied</a>")
    if os.getenv("GITHUB_RUN_ID"):
        links.append(f"<a href='{base}/actions/runs/{os.environ['GITHUB_RUN_ID']}' style='color:#0969da'>run log</a>")
    return ("<p style='background:#f6f8fa;padding:10px;border-radius:6px;font-size:13px;font-family:Arial,sans-serif'>"
            + " · ".join(links) + "</p>")


def summary(jobs):
    strong = sum(1 for j in jobs if j["score"] >= 80)
    good = sum(1 for j in jobs if CARD_MIN <= j["score"] < 80)
    return strong, good, len(jobs) - strong - good


def build_html(jobs, health, run_label):
    e = html.escape
    strong, good, rest = summary(jobs)
    out = ["<div style='font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#24292f'>",
           f"<h2 style='margin:8px 0 4px 0'>Job digest</h2><div style='color:#57606a;font-size:13px'>{e(run_label)}</div>",
           f"<p style='font-size:15px'>🎯 <b>{strong}</b> strong · 👍 <b>{good}</b> good fit · "
           f"<span style='color:#57606a'>{rest} lower matches (in the full record)</span></p>",
           _record_links()]
    picks = sorted((j for j in jobs if j["score"] >= CARD_MIN), key=lambda j: (-j["score"], _age_rank(j)))[:3]
    if picks:
        out.append("<div style='border:2px solid #1a7f37;border-radius:8px;padding:10px 14px;margin:8px 0 4px 0'>"
                   "<div style='font-weight:bold;margin-bottom:6px'>⭐ Apply first</div>" + "".join(
                       f"<div style='font-size:14px;margin:4px 0'><b>{j['score']}</b> · "
                       f"<a href='{e(j['url'])}' style='color:#0969da'>{e(j['title'])}</a> — {e(j['company'])}</div>"
                       for j in picks) + "</div>")
    if not strong + good:
        out.append("<p>No strong or good matches in this run. Lower matches are listed in the full record above.</p>")
    for code, title in LANGS:
        cards = sorted((j for j in jobs if j.get("lang", "de") == code and j["score"] >= CARD_MIN),
                       key=lambda j: (j["score"] < 80, _age_rank(j), -j["score"]))
        if cards:
            out.append(f"<h3 style='margin:22px 0 10px 0'>{title} ({len(cards)})</h3>")
            out += [_card(j, e) for j in cards]
    issues = [f"{e(src)}: {n} results{(' — ' + e(err)) if err else ''}" for src, (n, err) in health.items() if err or n == 0]
    out.append("<p style='font-size:12px;color:#57606a;margin-top:24px'>Sources: "
               + " · ".join(f"{e(src)} {n}" for src, (n, _) in health.items()) + "</p>")
    if issues:
        out.append("<p style='font-size:12px;color:#9a6700'>⚠️ " + "<br>⚠️ ".join(issues) + "</p>")
    if any(j.get("attachments") for j in jobs):
        out.append(standard_answers())
    out.append(_record_links() + "</div>")
    return "".join(out)


def assign_sections(jobs):
    for j in jobs:
        j["_section"] = next(label for floor, label in SECTIONS if j["score"] >= floor)


def recipients():
    return [x.strip() for k in ("TO_EMAIL", "TO_EMAIL_2") for x in os.getenv(k, "").split(",") if x.strip()]


def _attachment_name(path):
    """Unique, readable file names: <company-job folder>__<file>."""
    p = Path(path)
    return f"{p.parent.name[11:]}__{p.name}" if p.parent.name[:4].isdigit() else p.name


def _resend(to, subject, body, attachments=()):
    payload = {"from": os.getenv("FROM_EMAIL") or "Job Hunter <onboarding@resend.dev>",
               "to": [to], "subject": subject, "html": body}
    if attachments:
        payload["attachments"] = [{"filename": _attachment_name(a), "content": base64.b64encode(Path(a).read_bytes()).decode()}
                                  for a in attachments]
    r = requests.post("https://api.resend.com/emails", timeout=60,
                      headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"}, json=payload)
    if not r.ok:
        raise RuntimeError(f"Resend {r.status_code}: {r.text[:200]}")


def _gmail(to, subject, body, attachments=()):
    user = os.environ["GMAIL_USER"]
    msg = MIMEMultipart()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(body, "html", "utf-8"))
    for a in attachments:
        part = MIMEApplication(Path(a).read_bytes(), Name=_attachment_name(a))
        part["Content-Disposition"] = f'attachment; filename="{_attachment_name(a)}"'
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


def standard_answers():
    """Copy-paste block for application forms. Personal data only ever appears in the private email."""
    from .documents import contact_info
    c = contact_info()
    rows = [("Name", "Kranti Chavan"), ("Email", c["email"]), ("Phone", c["phone"]), ("City", "Karlsruhe, Germany"),
            ("LinkedIn", "https://linkedin.com/in/kranti-chavan-84a155191"),
            ("Work permit", "Valid German residence & work permit, no sponsorship required"),
            ("Earliest start", "16.12.2026 (serving notice, last working day 15.12.2026)"),
            ("Experience", "5+ years SAP Commerce Cloud (Hybris), Java, Spring"),
            ("Languages", "English C2, German B1, Hindi & Marathi native"),
            ("Work mode", "Remote, hybrid or on-site anywhere in Germany"),
            ("Salary expectation", "€60.000 gross/year, negotiable (each kit adapts it to the posted range)")]
    return ("<h3 style='margin-top:24px'>📋 Standard answers for application forms</h3>"
            "<table style='font-size:13px;border-collapse:collapse'>" + "".join(
                f"<tr><td style='padding:3px 10px 3px 0;color:#57606a'>{html.escape(k)}</td><td style='padding:3px 0'>{html.escape(v)}</td></tr>"
                for k, v in rows) + "</table><p style='font-size:12px;color:#57606a'>Job-specific answers (why this company, "
            "motivation, LinkedIn note) are in each job's 📝 Application kit.</p>")


def send(subject, body, attachments=()):
    """One email per recipient, so one bad address can't block the other. True if any arrived."""
    senders = [(n, f) for n, f, k in [("gmail", _gmail, "GMAIL_APP_PASSWORD"), ("resend", _resend, "RESEND_API_KEY")]
               if os.getenv(k)]
    to_list = recipients()
    if not to_list or not senders:
        log.error("Missing TO_EMAIL or email credentials (RESEND_API_KEY / GMAIL_APP_PASSWORD)")
        return False
    sent = 0
    for to in to_list:
        for name, fn in senders:
            try:
                fn(to, subject, body, attachments)
                log.info("emailed %s via %s (%d attachments)", to, name, len(attachments))
                sent += 1
                break
            except Exception as ex:
                log.warning("%s -> %s failed: %s", name, to, ex)
    return sent > 0
