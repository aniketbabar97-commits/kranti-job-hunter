"""Job list for Claude in Chrome (no personal data): python -m helper.make_chrome_list -> helper/CLAUDE_CHROME_LIST.md"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from hunter import applied, documents, kit  # noqa: E402


def main():
    text = (ROOT / "APPLIED.md").read_text(encoding="utf-8")
    done = {m.group(1) for m in re.finditer(r"(\S+) \([^)]*(applied via form|via Claude)", text)}
    kits, seen = [], set()
    for f in sorted((ROOT / "applications").glob("*.json"), reverse=True):
        k = json.loads(f.read_text(encoding="utf-8"))
        j = k["job"]
        if not k.get("lang") or j["url"] in seen or j["url"] in done:
            continue
        seen.add(j["url"])
        if j["title"].startswith("[Post]") or j["company"].lower() == "see posting":
            continue
        kits.append(k)
    kits.sort(key=lambda k: -int(k["job"]["score"]))
    out = ["# Job list for Claude in Chrome", "",
           "Each job: open **Link** → reach the employer's own application form → fill with the candidate details from the "
           "chat instruction + **Salary/Start** below → **Why us** for any motivation/message field → upload **Files** → "
           "submit → report. Rules are in the chat instruction.", ""]
    for n, k in enumerate(kits, 1):
        j, t, lang = k["job"], k["tailoring"], k["lang"]
        sal = kit.salary_answer(j).split(" · DE: ")
        out += [f"## {n}. {j['company']} — {j['title']}",
                f"- **Score:** {j['score']} · **Language:** {'German' if lang == 'de' else 'English'} · **Job ID:** {j['url']}",
                f"- **Link:** {j.get('direct_url') or j.get('apply_url') or j['url']}",
                f"- **Original posting:** {j['url']}",
                f"- **Files:** `{documents.file_name('cv', j, lang)}` + `{documents.file_name('cl', j, lang)}`",
                f"- **Salary:** {sal[-1] if lang == 'de' else sal[0]} · **Start:** 16.12.2026 · **Location:** Karlsruhe",
                f"- **Why us:** {t.get('why_company', '').strip()}", ""]
    (ROOT / "helper" / "CLAUDE_CHROME_LIST.md").write_text("\n".join(out), encoding="utf-8")
    print(len(kits), "jobs")


if __name__ == "__main__":
    main()
