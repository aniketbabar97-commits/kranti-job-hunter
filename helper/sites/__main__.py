"""python -m helper.sites [name ...] [--headful]: run the fixture tests and print a table."""
import json
import sys

from helper.sites import all_sites


def main(argv):
    headless = "--headful" not in argv
    names = [a for a in argv if not a.startswith("--")]
    rows = []
    for s in all_sites():
        if names and s.name not in names or not s.FIXTURE:
            continue
        print(f"... {s.name}", flush=True)
        rep = s.test_fixture(headless=headless)
        rows.append(rep)
        print("    " + json.dumps({k: v for k, v in rep.items() if k != "detail"}, ensure_ascii=False)[:600], flush=True)
    print("\n| ATS | fixture | filled | uploads | problems | submit found |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['ats']} | {r['fixture'][:70]} | {r['filled']} | {r['uploads']} | "
              f"{', '.join(r['problems'])[:60] or '-'}{(' ERR ' + r['error']) if r.get('error') else ''} | {'yes' if r['submit'] else 'no'} |")


if __name__ == "__main__":
    main(sys.argv[1:])
