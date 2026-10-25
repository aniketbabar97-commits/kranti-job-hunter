"""One-off re-sends from the ledger (workflow input "resend").

FIX: initiative emails of 25 Oct whose cover letter still named the template company -> corrected documents.
READDRESS: applications whose address bounced -> the same application to a working address.
Each entry is sent once (ledger field "resent").
"""
import json
import logging
import smtplib
from pathlib import Path

import yaml

from . import outreach, send_kits

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger(__name__)
FIX = ["Brita", "Cocomore", "Convista", "diva-e", "FIS / Medienwerft", "Gebr. Heinemann", "Kernpunkt", "novomind",
       "Scheer", "Shopmacher", "Spryker"]
READDRESS = {"karriere@af-mediagroup.com": "info@af-mediagroup.com"}
FIX_BODY = """Sehr geehrte Damen und Herren,

in meiner heutigen Initiativbewerbung als SAP Commerce Cloud (Hybris) Developer / Consultant enthielt das Anschreiben versehentlich einen falschen Firmennamen. Dafür bitte ich um Entschuldigung. Anbei sende ich Ihnen die korrigierten Unterlagen (Lebenslauf und Anschreiben) – bitte verwenden Sie diese Fassung.

Ich bringe über fünf Jahre Erfahrung mit SAP Commerce Cloud (Hybris 2105/2211), Java und Spring bei Rockwell Automation und Shell mit und bin SAP Certified Commerce Cloud Developer. Ich lebe in Karlsruhe, habe eine gültige Arbeitserlaubnis und kann ab dem 16.12.2026 starten.

Über eine Einladung zu einem Gespräch freue ich mich sehr.

Mit freundlichen Grüßen
Kranti Chavan"""


def run():
    user, pw = outreach.credentials()
    if not outreach.ready():
        raise SystemExit("Gmail login or CANDIDATE_* secrets missing")
    master = yaml.safe_load((ROOT / "profile" / "master.yaml").read_text(encoding="utf-8"))
    kits = {k["job"]["url"]: k for k in send_kits.kits(days=60)}
    ledger = outreach.load()
    for key, v in ledger.items():
        fix = v["company"] in FIX and v["status"] == "sent" and v.get("created") == "2026-10-25"
        new_to = READDRESS.get(v["to"])
        if v.get("resent") or not (fix or new_to):
            continue
        kit = kits.get(v["url"])
        if not kit:
            log.warning("no kit for %s", v["company"])
            continue
        j = dict(kit["job"])
        kit["slug"] = f"resend-{outreach._company_key(j)}-{abs(hash(j['url'])) % 10000}"
        j["attachments"] = send_kits.build(kit, master)
        lang = v.get("lang") or "de"
        files = outreach._files(j, lang)
        if fix:
            j["email_subject"] = "Korrigierte Unterlagen: " + v["subject"].replace("Bewerbung als ", "", 1)
            j["email_body"] = FIX_BODY
        msg = outreach.build_message(j, new_to or v["to"], lang, kit["letters"][lang], files, user)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(user, pw)
            smtp.send_message(msg)
        v["resent"] = f"{'corrected' if fix else 'readdressed'} -> {new_to or v['to']}"
        log.info("resent %s -> %s", v["company"], new_to or v["to"])
    outreach.save(ledger)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    run()
