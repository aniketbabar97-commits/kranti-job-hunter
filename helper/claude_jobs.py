"""Bridge between Claude Code on her PC and the job data.

  python -m helper.claude_jobs next [n]        -> next n jobs to apply to (JSON: job, link, files, why_us, salary, lang)
  python -m helper.claude_jobs facts           -> candidate facts for forms (incl. email/phone/address from me.env)
  python -m helper.claude_jobs password        -> the account password from me.env (ACCOUNT_PASSWORD)
  python -m helper.claude_jobs code <sender>   -> waits for a verification code/link mail from <sender> (Gmail)
  python -m helper.claude_jobs done <id> confirmed|pending|parked|closed "<note>"   -> logs the result

Builds the job's PDFs on first use (out/helper/...). Logging goes through the same proof/APPLIED.md path as the helper.
"""
import json
import re
import sys
import time
from pathlib import Path

import yaml

from helper.apply import ROOT, SKIPPED, build_pdfs, load_env, queue

LINK_RX = r"verif|activat|confirm|reset|password|passwort|bestätig|aktivier|login|anmeld|sign|token|auth|magic"
STATE = ROOT / "data" / "claude_runs.json"


def _state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def _save(s):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")


def _id(kit):
    return kit["job"]["url"]


def next_jobs(n=1):
    from hunter.kit import salary_answer
    done = _state()
    out = []
    for kit in queue():
        j = kit["job"]
        # finished ones never again; parked ones only in a later run (not again within 6 h)
        d = done.get(_id(kit), {})
        recent = d.get("ts", "") >= time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 6 * 3600))
        if d.get("status") in ("confirmed", "pending", "closed") or (d.get("status") == "parked" and recent) \
                or j.get("channel") == "email":
            continue
        cv, letter, _, lang = build_pdfs(kit)
        sal = salary_answer({"salary": j.get("salary", "")})
        out.append({
            "id": _id(kit), "company": j["company"], "title": j["title"], "location": j.get("location", ""),
            "link": j.get("form_url") or j.get("direct_url") or j.get("apply_url") or j["url"],
            "original_posting": j["url"], "language": "German" if lang == "de" else "English",
            "files": {"cv": str(Path(cv).resolve()), "cover_letter": str(Path(letter).resolve())},
            "why_us": kit["tailoring"].get("why_company", ""),
            "salary": sal.split(" · DE: ")[-1] if lang == "de" else sal.split(" · DE: ")[0],
        })
        if len(out) >= n:
            break
    return out


def facts():
    import os
    f = yaml.safe_load((ROOT / "profile" / "facts.yaml").read_text(encoding="utf-8"))
    f["contact"] = {"email": os.environ.get("CANDIDATE_EMAIL", ""), "phone": os.environ.get("CANDIDATE_PHONE", ""),
                    "street": os.environ.get("CANDIDATE_STREET", ""), "birthdate": os.environ.get("CANDIDATE_BIRTHDATE", ""),
                    "postcode": os.environ.get("CANDIDATE_POSTCODE", "") or f["location"]["postal_code"]}
    return f


EMAIL_IN_NOTE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def to_email_route(job_id, address):
    """A job whose page offers an application email moves to the email route (sent by the daily run)."""
    for f in (ROOT / "applications").glob("*.json"):
        k = json.loads(f.read_text(encoding="utf-8"))
        if k["job"]["url"] == job_id:
            k["job"]["channel"], k["job"]["contact"] = "email", address
            f.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
            return True
    return False


def done(job_id, status, note=""):
    from helper import proof
    m = EMAIL_IN_NOTE.search(note or "")
    if status == "parked" and m and to_email_route(job_id, m.group(0).rstrip(".")):
        note = f"{note} → email route"
    s = _state()
    s[job_id] = {"status": status, "note": note, "ts": time.strftime("%Y-%m-%d %H:%M")}
    for site in ("linkedin", "xing"):
        if status == "confirmed" and f"{site} easy apply" in (note or "").lower():
            s[job_id]["via"] = site
    _save(s)
    kit = next((k for k in queue(days=365) if _id(k) == job_id), None)
    job = kit["job"] if kit else {"url": job_id, "company": "?", "title": "?"}
    if status == "confirmed":
        proof.log_submission(job, job.get("ats", "own"), None, True, "claude")
    elif status == "pending":
        proof.log_submission(job, job.get("ats", "own"), None, False, "claude")
    elif status == "closed":
        with open(SKIPPED, "a", encoding="utf-8") as fh:
            fh.write(job_id + "\n")
    return {"logged": status}


def main():
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "next":
        res = next_jobs(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    elif cmd == "facts":
        res = facts()
    elif cmd == "password":  # password [linkedin|xing] -> that platform's login, else the default account password
        import os
        site = (sys.argv[2] if len(sys.argv) > 2 else "").upper()
        if site in ("LINKEDIN", "XING"):
            used = sum(1 for v in _state().values() if v.get("via") == site.lower() and v["ts"][:10] == time.strftime("%Y-%m-%d"))
            res = {"email": os.environ.get(f"{site}_EMAIL", ""), "password": os.environ.get(f"{site}_PASSWORD", ""),
                   "left_today": max(0, 10 - used)}
        else:
            res = {"password": os.environ.get("ACCOUNT_PASSWORD", "")}
    elif cmd == "code":  # code <company> [site-domain]: link first (they expire fast), then a numeric code
        from helper import mailcodes
        since, hints, res = time.time() - 600, [h for h in sys.argv[2:4] if h], {}
        hints += [h for h in ("myworkday", "workday", "successfactors", "noreply", "no-reply") if h not in hints]
        for _ in range(12):
            for h in hints:
                link = mailcodes.wait_for_link(h, LINK_RX, since_ts=since, timeout=5)
                code = None if link else mailcodes.wait_for_code(h, since, timeout=5)
                if link or code:
                    res = {"link": link, "code": code, "from": h}
                    break
            if res:
                break
        res = res or {"link": None, "code": None, "note": "nothing yet: request a new mail and call again"}
    elif cmd == "parked":  # list everything she can still finish by hand (CAPTCHA, unclear submit, …)
        st = _state()
        res = [{"link": k, "note": v["note"]} for k, v in st.items() if v["status"] == "parked"]
    elif cmd == "learn":  # learn <system> <lesson>: appended to helper/PLAYBOOK.md (public: no personal data)
        pb = ROOT / "helper" / "PLAYBOOK.md"
        text = pb.read_text(encoding="utf-8")
        head, line = f"## {sys.argv[2]}", f"- {sys.argv[3].strip()}"
        if line not in text:
            text = text.replace(head, head + "\n" + line, 1) if head in text else text.rstrip() + f"\n\n{head}\n{line}\n"
            pb.write_text(text, encoding="utf-8")
        res = {"learned": True}
    elif cmd == "done":
        res = done(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    else:
        res = {"error": f"unknown command {cmd}"}
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
