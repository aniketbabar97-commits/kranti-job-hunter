"""Build and send the HTML digest email."""
import html
import logging
import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

import requests

log = logging.getLogger(__name__)

SECTIONS = [(80, "🎯 Strong match"), (60, "👍 Good fit / can learn"), (30, "👀 Worth a look"), (0, "🗂 Low match (titles only)")]


AGES = [(1, "🆕 ≤1 day"), (3, "2–3 days"), (7, "4–7 days"), (10**6, "7+ days")]


def age_label(job):
    try:
        days = (date.today() - date.fromisoformat(job["posted"][:10])).days
    except ValueError:
        return "date unknown"
    return next(label for limit, label in AGES if days <= limit)


def _age_rank(job):
    labels = [label for _, label in AGES] + ["date unknown"]
    return labels.index(age_label(job))


LANGS = [("en", "🇬🇧 English-speaking jobs"), ("de", "🇩🇪 German-speaking jobs")]


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
        for t, bg in [(age, "#dafbe1" if age.startswith("🆕") else "#eaeef2"), (lang, "#eaeef2"), (j["source"], "#eaeef2")])
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
        f"<div style='font-size:13px;color:#24292f;margin:4px 0 10px 0'>✔ {e(j.get('why', ''))}</div>"
        f"<a href='{e(j['url'])}' style='display:inline-block;background:{color};color:#fff;text-decoration:none;"
        "padding:6px 14px;border-radius:6px;font-size:13px;font-weight:bold'>Open job →</a>"
        "</td></tr></table>")


def _record_links():
    base = _base_url()
    if not base:
        return ""
    links = [f"<a href='{base}/blob/main/JOBS.md' style='color:#0969da'>📒 Full record of every job (sorted)</a>",
             f"<a href='{base}/blob/main/data/jobs_log.csv' style='color:#0969da'>spreadsheet</a>"]
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
    out.append(_record_links() + "</div>")
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
