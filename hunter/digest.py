"""Build and send the HTML digest email."""
import html
import logging
import os
import smtplib
from email.mime.text import MIMEText

import requests

log = logging.getLogger(__name__)

SECTIONS = [(80, "🎯 Strong match"), (60, "👍 Good fit / can learn"), (30, "👀 Worth a look"), (0, "🗂 Low match (titles only)")]


LANGS = [("en", "🇬🇧 English-speaking jobs"), ("de", "🇩🇪 German-speaking jobs")]


def _render_group(out, jobs, e):
    for floor, label in SECTIONS:
        group = [j for j in jobs if j.get("_section") == label]
        if not group:
            continue
        if label.startswith("🗂"):
            out.append(f"<h4>{label} ({len(group)})</h4><p style='font-size:13px;color:#555'>" + "<br>".join(
                f"{j['score']} · <a href='{e(j['url'])}'>{e(j['title'])}</a> — {e(j['company'])}" for j in group) + "</p>")
            continue
        out.append(f"<h4>{label} ({len(group)})</h4><table cellpadding='6' style='border-collapse:collapse;width:100%'>")
        for j in group:
            tags = " · ".join(x for x in [j["location"], "🏠 remote/hybrid" if j["remote"] else "", j["salary"], j["source"], j["posted"]] if x)
            out.append(
                f"<tr style='border-bottom:1px solid #ddd'><td style='width:42px;font-weight:bold;font-size:18px'>{j['score']}</td>"
                f"<td><a href='{e(j['url'])}' style='font-weight:bold'>{e(j['title'])}</a><br>"
                f"<b>{e(j['company'])}</b> — <span style='color:#555'>{e(tags)}</span><br>"
                f"<i style='color:#333'>{e(j.get('why', ''))}</i></td></tr>")
        out.append("</table>")


def build_html(jobs, health, run_label):
    e = html.escape
    counts = {code: sum(1 for j in jobs if j.get("lang", "de") == code) for code, _ in LANGS}
    out = [f"<div style='font-family:Arial,sans-serif;max-width:760px'>"
           f"<h2>Job digest — {e(run_label)}</h2>"
           f"<p>{len(jobs)} new openings, ranked by fit: "
           f"<a href='#en'>{counts['en']} English-speaking</a> · <a href='#de'>{counts['de']} German-speaking</a>.</p>"]
    for code, title in LANGS:
        group = [j for j in jobs if j.get("lang", "de") == code]
        out.append(f"<h2 id='{code}' style='border-bottom:3px solid #333;padding-top:12px'>{title} ({len(group)})</h2>")
        if group:
            _render_group(out, group, e)
        else:
            out.append("<p style='color:#555'>None this run.</p>")
    out.append("<h4>Source health</h4><ul>")
    for src, (n, err) in health.items():
        flag = "⚠️ " if err or n == 0 else ""
        out.append(f"<li>{flag}{e(src)}: {n} results{(' — ' + e(err)) if err else ''}</li>")
    out.append("</ul></div>")
    return "".join(out)


def assign_sections(jobs):
    for j in jobs:
        j["_section"] = next(label for floor, label in SECTIONS if j["score"] >= floor)


def recipients():
    return [x.strip() for k in ("TO_EMAIL", "TO_EMAIL_2") for x in os.getenv(k, "").split(",") if x.strip()]


def _resend(to, subject, body):
    r = requests.post("https://api.resend.com/emails", timeout=30,
                      headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
                      json={"from": os.getenv("FROM_EMAIL") or "Job Hunter <onboarding@resend.dev>",
                            "to": [to], "subject": subject, "html": body})
    if not r.ok:
        raise RuntimeError(f"Resend {r.status_code}: {r.text[:200]}")


def _gmail(to, subject, body):
    user = os.environ["GMAIL_USER"]
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


def send(subject, body):
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
                fn(to, subject, body)
                log.info("emailed %s via %s", to, name)
                sent += 1
                break
            except Exception as e:
                log.warning("%s -> %s failed: %s", name, to, e)
    return sent > 0
