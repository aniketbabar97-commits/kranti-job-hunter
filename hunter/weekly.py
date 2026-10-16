"""Monday summary email: best jobs of the past 7 days, companies hiring repeatedly, applications sent."""
import html
import logging
import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import re

from . import applied, digest, report, rules, sources

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "weekly_sent.txt"
log = logging.getLogger(__name__)
TOP_N = 10


def due(today):
    """Monday (or forced), and not already sent this ISO week."""
    week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    sent = STATE.read_text().strip() if STATE.exists() else ""
    return (today.weekday() == 0 or os.getenv("FORCE_WEEKLY")) and sent != week, week


LONG_OPEN_QUERIES = ["SAP Commerce", "Hybris", "SAP Commerce Cloud", "SAP CX Commerce"]
ROLE = re.compile(r"(?i)developer|entwickler|engineer|consultant|berater|architect|lead|owner|analyst|expert")
NOT_FOR_HER = re.compile(r"(?i)\b(sales|vertrieb|account executive|praktik|intern|werkstudent|working student|ausbildung)\b")


def long_open(cfg, applied_data, limit=15):
    """SAP Commerce roles still open after 30+ days: companies struggling to hire — the best targets for a direct approach."""
    found = []
    for q in LONG_OPEN_QUERIES:
        try:
            found += sources.arbeitsagentur(q, days=None)
        except Exception as e:
            log.warning("long-open arbeitsagentur %r failed: %s", q, e)
    for entry in cfg.get("companies", []):
        try:
            found += sources.company_feed(entry)
        except Exception as e:
            log.warning("long-open %s failed: %s", entry["name"], e)
    seen, out = set(), []
    for j in found:
        title, text = j["title"] or "", f"{j['title']} {j['description']}"
        core = rules.COMMERCE_CORE.search(title) or (rules.COMMERCE_CORE.search(text) and ROLE.search(title))
        days = digest.days_open(j)
        where_ok = j["source"] == "Arbeitsagentur" or rules.GERMANY.search(j["location"] or "") or j["remote"]
        k = re.sub(r"[^a-z0-9]", "", f"{title}|{j['company']}".lower())
        if core and not NOT_FOR_HER.search(title) and days is not None and days >= digest.LONG_OPEN_DAYS \
                and where_ok and k not in seen and applied.status(j, applied_data) != "applied":
            seen.add(k)
            out.append(dict(j, days=days))
    return sorted(out, key=lambda j: -j["days"])[:limit]


def build(today, rows, applied_data, hard_to_fill=()):
    e = html.escape
    week_ago, month_ago = (today - timedelta(days=7)).isoformat(), (today - timedelta(days=30)).isoformat()
    week = [dict(r, description="") for r in rows if r["found"] >= week_ago]
    for r in week:
        r["score"], _ = rules.adjust(r)
        r["applied"] = applied.status(r, applied_data)
    open_top = sorted((r for r in week if r["score"] >= digest.CARD_MIN and r["applied"] != "applied"),
                      key=lambda r: -r["score"])[:TOP_N]
    strong = sum(1 for r in week if r["score"] >= 80)
    good = sum(1 for r in week if digest.CARD_MIN <= r["score"] < 80)
    hiring = Counter(r["company"] for r in rows if r["found"] >= month_ago and r["company"]
                     and r["source"] != "LinkedIn post" and int(r["score"]) >= 40)
    repeat = [(c, n) for c, n in hiring.most_common(8) if n >= 2]
    sent_week = applied.count_since(applied_data, today - timedelta(days=7))

    out = ["<div style='font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#24292f'>",
           f"<h2 style='margin:8px 0 4px 0'>📊 Weekly summary</h2>"
           f"<div style='color:#57606a;font-size:13px'>{week_ago} → {today.isoformat()}</div>",
           "<table role='presentation' width='100%' style='margin:14px 0'><tr>" + "".join(
               f"<td style='text-align:center;background:#f6f8fa;border-radius:8px;padding:10px'>"
               f"<div style='font-size:22px;font-weight:bold'>{n}</div><div style='font-size:12px;color:#57606a'>{label}</div></td>"
               for n, label in [(len(week), "new jobs"), (strong, "strong"), (good, "good fit"), (sent_week, "applied (dated)")])
           + "</tr></table>",
           digest._record_links()]
    out.append(f"<h3>⭐ Best jobs this week you haven't applied to ({len(open_top)})</h3>")
    if open_top:
        out += [digest._card(dict(r, remote=r["remote"] == "True", salary=""), e) for r in open_top]
    else:
        out.append("<p>No strong or good matches this week.</p>")
    if hard_to_fill:
        out.append("<h3>⏳ Hard-to-fill SAP Commerce roles (still open after 30+ days)</h3>"
                   "<p style='font-size:13px;color:#57606a'>These companies have been searching for a long time. "
                   "Apply directly and also message the recruiter or team lead on LinkedIn — your chances are best here.</p>")
        out.append("<table role='presentation' width='100%' style='font-size:14px;border-collapse:collapse'>" + "".join(
            f"<tr style='border-bottom:1px solid #eaeef2'><td style='padding:6px 8px 6px 0;white-space:nowrap;color:#cf222e'>"
            f"<b>{j['days']}</b> days</td><td style='padding:6px 0'><a href='{e(j['url'])}' style='color:#0969da'>{e(j['title'])}</a>"
            f" — {e(j['company'])}{(', ' + e(j['location'])) if j['location'] else ''}"
            f"{' · ↺ applied at company' if applied.status(j, applied_data) == 'company' else ''}</td></tr>"
            for j in hard_to_fill) + "</table>")
    if repeat:
        out.append("<h3>🏢 Companies hiring repeatedly (last 30 days)</h3><ul>" + "".join(
            f"<li>{e(c)} — {n} openings{' · ↺ you applied here' if applied.status({'company': c}, applied_data) else ''}</li>"
            for c, n in repeat) + "</ul>")
    out.append("<p style='font-size:13px;color:#57606a'>Tip: add each application to APPLIED.md (link above) "
               "so applied jobs are marked and left out of this summary.</p></div>")
    return "".join(out)


def maybe_send(today, cfg):
    is_due, week = due(today)
    if not is_due:
        return
    applied_data = applied.load()
    body = build(today, report.read_log(), applied_data, long_open(cfg, applied_data))
    (ROOT / "data" / "last_weekly.html").write_text(body)
    if digest.send(f"📊 Weekly job summary — week {week[-2:]}", body):
        STATE.write_text(week)
        log.info("weekly summary sent for %s", week)
    else:
        log.warning("weekly summary not sent")
