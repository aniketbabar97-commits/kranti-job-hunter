"""One polite follow-up for email applications that got no reply (python -m hunter.followup).

Rules: only status "sent" (no reply seen by outreach.sync), sent at least DAYS days ago, never twice,
replied in the same thread. The note repeats what she offers and, where the kit has one, its company insight.
"""
import json
import logging
import smtplib
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from . import outreach, send_kits

ROOT = Path(__file__).resolve().parent.parent

log = logging.getLogger(__name__)
DAYS = 5
MAX_PER_RUN = 15
OFFER = {
    "en": "Briefly, what I would bring: 5+ years of SAP Commerce Cloud (Hybris 2105/2211) at Rockwell Automation and "
          "Shell, CCv2 upgrades and deployments, OCC APIs, PIM/ERP integrations and production support, as an SAP "
          "Certified Commerce Cloud Developer who can contribute from week one.",
    "de": "Kurz, was ich mitbringe: über fünf Jahre SAP Commerce Cloud (Hybris 2105/2211) bei Rockwell Automation und "
          "Shell, CCv2-Upgrades und -Deployments, OCC-APIs, PIM-/ERP-Integrationen und Produktionssupport – als SAP "
          "Certified Commerce Cloud Developer kann ich ab der ersten Woche produktiv beitragen.",
}


def body(entry, kit, lang):
    c = outreach.contact_info()
    insight = ((kit or {}).get("tailoring", {}).get("insight") or "").strip() if lang == "en" else ""
    if lang == "de":
        lines = ["Guten Tag,", "",
                 f"ich wollte kurz nachfragen, ob meine Bewerbung vom {'.'.join(reversed(entry['sent'].split('-')))} ({entry['subject']}) bei Ihnen "
                 "angekommen ist.", "", OFFER["de"], "",
                 "Ich stehe ab dem 16.12.2026 zur Verfügung und freue mich über ein kurzes Gespräch – "
                 "gern auch telefonisch, 15 Minuten genügen.", ""]
    else:
        lines = ["Hello,", "",
                 f"I wanted to briefly follow up on my application from {entry['sent']} ({entry['subject']}).", "",
                 OFFER["en"] + (" " + insight if insight else ""), "",
                 "I am available from 16 December 2026 and would welcome a short 15-minute call.", ""]
    return "\n".join(lines + [outreach.SIGNATURE[lang].format(**c)]) + "\n"


def run():
    if not outreach.ready():
        raise SystemExit("Gmail login or CANDIDATE_* secrets missing")
    user, pw = outreach.credentials()
    kits = {k["job"]["url"]: k for k in send_kits.kits(days=90)}
    ledger = outreach.load()
    resp = json.loads((ROOT / "data" / "responses.json").read_text(encoding="utf-8"))
    rejected = {outreach._company_key({"company": r.get("company", "")}) for r in (resp if isinstance(resp, list) else resp.values())
                if r.get("category") == "rejection"}
    due = (date.today() - timedelta(days=DAYS)).isoformat()
    done, seen_to = 0, {v['to'] for v in ledger.values() if v.get('followup')}
    for msg_id, v in sorted(ledger.items(), key=lambda kv: kv[1].get("sent", "")):
        if done >= MAX_PER_RUN:
            break
        if v.get("status") != "sent" or v.get("followup") or not v.get("sent") or v["sent"] > due or v.get("resent") \
                or outreach._company_key(v) in rejected or "bounce" in (v.get("note") or ""):
            continue
        if v["to"] in seen_to:
            continue
        seen_to.add(v["to"])
        lang = v.get("lang") or "en"
        msg = EmailMessage()
        msg["From"] = formataddr(("Kranti Chavan", user))
        msg["To"] = v["to"]
        msg["Subject"] = "Re: " + v["subject"]
        msg["In-Reply-To"] = msg["References"] = msg_id
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=user.split("@")[1])
        msg.set_content(body(v, kits.get(v.get("url")), lang))
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(user, pw)
                smtp.send_message(msg)
        except Exception as ex:
            log.warning("follow-up to %s failed: %s", v["to"], ex)
            continue
        v["followup"] = date.today().isoformat()
        done += 1
        log.info("follow-up: %s -> %s", v["company"], v["to"])
    outreach.save(ledger)
    log.info("follow-ups sent: %d", done)
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    run()
