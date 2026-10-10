"""Build and send the HTML digest email."""
import html
import logging
import os
import smtplib
from email.mime.text import MIMEText

import requests

log = logging.getLogger(__name__)

SECTIONS = [(80, "🎯 Strong match"), (60, "👍 Good fit / can learn"), (0, "👀 Worth a look")]


def build_html(jobs, health, run_label):
    e = html.escape
    out = [f"<div style='font-family:Arial,sans-serif;max-width:760px'>"
           f"<h2>Job digest — {e(run_label)}</h2><p>{len(jobs)} new openings, ranked by fit.</p>"]
    for floor, label in SECTIONS:
        group = [j for j in jobs if j.get("_section") == label]
        if not group:
            continue
        out.append(f"<h3>{label} ({len(group)})</h3><table cellpadding='6' style='border-collapse:collapse;width:100%'>")
        for j in group:
            tags = " · ".join(x for x in [j["location"], "🏠 remote/hybrid" if j["remote"] else "", j["salary"], j["source"], j["posted"]] if x)
            out.append(
                f"<tr style='border-bottom:1px solid #ddd'><td style='width:42px;font-weight:bold;font-size:18px'>{j['score']}</td>"
                f"<td><a href='{e(j['url'])}' style='font-weight:bold'>{e(j['title'])}</a><br>"
                f"<b>{e(j['company'])}</b> — <span style='color:#555'>{e(tags)}</span><br>"
                f"<i style='color:#333'>{e(j.get('why', ''))}</i></td></tr>")
        out.append("</table>")
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


def send(subject, body):
    to = recipients()
    if not to:
        log.warning("No TO_EMAIL set; skipping email")
        return False
    if os.getenv("RESEND_API_KEY"):
        r = requests.post("https://api.resend.com/emails", timeout=30,
                          headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
                          json={"from": os.getenv("FROM_EMAIL", "Job Hunter <onboarding@resend.dev>"),
                                "to": to, "subject": subject, "html": body})
        if r.ok:
            return True
        log.warning("Resend failed (%s): %s", r.status_code, r.text[:300])
    if os.getenv("GMAIL_APP_PASSWORD"):
        user = os.environ["GMAIL_USER"]
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = subject, user, ", ".join(to)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, os.environ["GMAIL_APP_PASSWORD"])
            s.send_message(msg)
        return True
    return False
