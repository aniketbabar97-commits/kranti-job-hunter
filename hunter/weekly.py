"""Monday summary email: best jobs of the past 7 days, companies hiring repeatedly, applications sent."""
import html
import logging
import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from . import applied, digest, report, rules

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "weekly_sent.txt"
log = logging.getLogger(__name__)
TOP_N = 10


def due(today):
    """Monday (or forced), and not already sent this ISO week."""
    week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    sent = STATE.read_text().strip() if STATE.exists() else ""
    return (today.weekday() == 0 or os.getenv("FORCE_WEEKLY")) and sent != week, week


def build(today, rows, applied_data):
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
    if repeat:
        out.append("<h3>🏢 Companies hiring repeatedly (last 30 days)</h3><ul>" + "".join(
            f"<li>{e(c)} — {n} openings{' · ↺ you applied here' if applied.status({'company': c}, applied_data) else ''}</li>"
            for c, n in repeat) + "</ul>")
    out.append("<p style='font-size:13px;color:#57606a'>Tip: add each application to APPLIED.md (link above) "
               "so applied jobs are marked and left out of this summary.</p></div>")
    return "".join(out)


def maybe_send(today):
    is_due, week = due(today)
    if not is_due:
        return
    body = build(today, report.read_log(), applied.load())
    (ROOT / "data" / "last_weekly.html").write_text(body)
    if digest.send(f"📊 Weekly job summary — week {week[-2:]}", body):
        STATE.write_text(week)
        log.info("weekly summary sent for %s", week)
    else:
        log.warning("weekly summary not sent")
