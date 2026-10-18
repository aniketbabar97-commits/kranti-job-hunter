"""Bridge between Claude Code on her PC and the job data.

  python -m helper.claude_jobs next [n]        -> next n jobs to apply to (JSON: job, link, files, why_us, salary, lang)
  python -m helper.claude_jobs facts           -> candidate facts for forms (incl. email/phone/address from me.env)
  python -m helper.claude_jobs password        -> the account password from me.env (ACCOUNT_PASSWORD)
  python -m helper.claude_jobs code <sender>   -> waits for a verification code/link mail from <sender> (Gmail)
  python -m helper.claude_jobs done <id> confirmed|pending|parked|closed "<note>"   -> logs the result

Builds the job's PDFs on first use (out/helper/...). Logging goes through the same proof/APPLIED.md path as the helper.
"""
import json
import sys
import time
from pathlib import Path

import yaml

from helper.apply import ROOT, SKIPPED, build_pdfs, load_env, queue

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
        if _id(kit) in done or j.get("channel") == "email":
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
                    "street": os.environ.get("CANDIDATE_STREET", ""),
                    "postcode": os.environ.get("CANDIDATE_POSTCODE", "") or f["location"]["postal_code"]}
    return f


def done(job_id, status, note=""):
    from helper import proof
    s = _state()
    s[job_id] = {"status": status, "note": note, "ts": time.strftime("%Y-%m-%d %H:%M")}
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
    elif cmd == "password":
        import os
        res = {"password": os.environ.get("ACCOUNT_PASSWORD", "")}
    elif cmd == "code":
        from helper import mailcodes
        since = time.time() - 600
        res = {"code": mailcodes.wait_for_code(sys.argv[2], since, timeout=180),
               "link": mailcodes.wait_for_link(sys.argv[2], r"https?://\S+", since, timeout=30)}
    elif cmd == "done":
        res = done(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    else:
        res = {"error": f"unknown command {cmd}"}
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
