"""Application funnel: found → relevant → kit ready → applied → confirmed → replies → interviews.

Sources: data/jobs_log.csv (found, relevant = score ≥ 60), applications/*.json (kits), data/submissions.json
(website applications by the helper: auto/assisted), data/applications.json (emailed applications), APPLIED.md
(manual entries), data/responses.json (replies, interviews)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEVANT = 60


def _url(u):
    return re.sub(r"[?#].*$", "", (u or "").strip().lower()).rstrip("/")


def _json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def counts(since=None):
    """Funnel numbers as a dict. since: ISO date; rows/kits/submissions/mails/replies before it are ignored."""
    from . import applied, report
    rows = report.read_log()
    if since:
        rows = [r for r in rows if r.get("found", "") >= since]
    found = len(rows)
    relevant = sum(1 for r in rows if int(r.get("score") or 0) >= RELEVANT)

    kits = set()
    for f in (ROOT / "applications").glob("*.json"):
        k = _json(f, {})
        if k.get("lang") and not k.get("skip") and (not since or k.get("created", "") >= since):
            kits.add(_url(k.get("job", {}).get("url")))

    subs = [s for s in _json(ROOT / "data" / "submissions.json", []) if not since or s.get("ts", "")[:10] >= since]
    web_auto = {_url(s["url"]) for s in subs if s.get("mode") == "auto"}
    web_assisted = {_url(s["url"]) for s in subs if s.get("mode") != "auto"}
    confirmed = {_url(s["url"]) for s in subs if s.get("status") == "confirmed"}
    pending = {_url(s["url"]) for s in subs if s.get("status") == "pending"}

    ledger = _json(ROOT / "data" / "applications.json", {})
    emailed = {_url(v["url"]) for v in ledger.values() if v.get("status") == "sent" and (not since or v.get("sent", "") >= since)}

    data = applied.load()
    manual = set()
    for when, line in data["entries"]:
        if since and when and when < since:
            continue
        m = re.search(r"https?://\S+", line)
        u = _url(m.group(0)) if m else ""
        if u and u not in web_auto and u not in web_assisted and u not in emailed and not applied.NOT_DONE.search(line):
            manual.add(u)
    applied_all = web_auto | web_assisted | emailed | manual
    # emailed applications and manual APPLIED.md entries count as confirmed (the mail left, she did it herself)
    confirmed_all = confirmed | emailed | manual

    recs = [r for r in _json(ROOT / "data" / "responses.json", {}).values() if not since or r.get("date", "") >= since]
    replies = {r["company"] for r in recs if r.get("category") in ("interview", "rejection", "other")}
    interviews = {r["company"] for r in recs if r.get("category") == "interview"}
    rejections = {r["company"] for r in recs if r.get("category") == "rejection"}
    return {"found": found, "relevant": relevant, "kits": len(kits),
            "applied": len(applied_all), "auto": len(web_auto), "assisted": len(web_assisted),
            "emailed": len(emailed), "manual": len(manual), "pending": len(pending),
            "confirmed": len(confirmed_all), "replies": len(replies), "interviews": len(interviews),
            "rejections": len(rejections)}


STEPS = [("found", "found"), ("relevant", "relevant (≥60)"), ("kits", "kit ready"), ("applied", "applied"),
         ("confirmed", "confirmed"), ("replies", "replies"), ("interviews", "interviews")]


def text(c=None, since=None):
    c = c or counts(since)
    detail = f"auto {c['auto']} · assisted {c['assisted']} · email {c['emailed']} · manual {c['manual']}"
    line = " → ".join(f"{label} {c[key]}" for key, label in STEPS)
    return f"{line}\n  applied: {detail}" + (f" · pending {c['pending']}" if c["pending"] else "")


def html_block(since=None, title="📈 Funnel"):
    import html
    c = counts(since)
    cells = "".join(
        f"<td style='text-align:center;background:#f6f8fa;border-radius:8px;padding:8px 4px'>"
        f"<div style='font-size:20px;font-weight:bold'>{c[key]}</div><div style='font-size:11px;color:#57606a'>{html.escape(label)}</div></td>"
        + ("<td style='color:#8c959f;font-size:14px;padding:0 2px'>→</td>" if i < len(STEPS) - 1 else "")
        for i, (key, label) in enumerate(STEPS))
    sub = (f"applied = 🤖 auto {c['auto']} · 🤝 assisted {c['assisted']} · ✉ email {c['emailed']} · ✍ manual {c['manual']}"
           + (f" · ⏳ pending {c['pending']}" if c["pending"] else "")
           + (f" · ✖ rejections {c['rejections']}" if c["rejections"] else ""))
    return (f"<div style='margin:14px 0'><div style='font-weight:bold;margin-bottom:6px'>{title}"
            + (f" <span style='color:#57606a;font-weight:normal;font-size:12px'>since {html.escape(since)}</span>" if since else "")
            + "</div><table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>" + cells + "</tr></table>"
            f"<div style='font-size:12px;color:#57606a;margin-top:4px'>{sub}</div></div>")


def markdown(since=None):
    c = counts(since)
    return ("| " + " | ".join(label for _, label in STEPS) + " |\n|" + "---:|" * len(STEPS) + "\n| "
            + " | ".join(str(c[k]) for k, _ in STEPS) + " |\n\n"
            f"applied: auto {c['auto']} · assisted {c['assisted']} · email {c['emailed']} · manual {c['manual']} · pending {c['pending']}")
