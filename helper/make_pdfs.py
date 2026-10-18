"""Build CV + cover letter PDFs for every final kit into one folder (default C:\\Kranti\\pdfs) for Claude in Chrome.

Start with make_pdfs.bat (or: python -m helper.make_pdfs [folder]).
"""
import shutil
import sys
from pathlib import Path

from helper.apply import ROOT, build_pdfs, load_env  # noqa: F401
import json


def main():
    load_env()
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Kranti\pdfs")
    dest.mkdir(parents=True, exist_ok=True)
    kits = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((ROOT / "applications").glob("*.json"))]
    kits = [k for k in kits if k.get("lang")]
    for n, k in enumerate(kits, 1):
        try:
            cv, cl, _, _ = build_pdfs(k)
            for f in (cv, cl):
                shutil.copy(f, dest / Path(f).name)
            print(f"{n}/{len(kits)} {k['job']['company']}")
        except Exception as ex:
            print(f"{n}/{len(kits)} FAILED {k['job']['company']}: {ex}")
    print(f"Done: {len(list(dest.glob('*.pdf')))} PDFs in {dest}")


if __name__ == "__main__":
    main()
