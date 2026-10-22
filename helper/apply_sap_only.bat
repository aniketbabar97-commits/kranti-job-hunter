@echo off
rem Focus run: only SAP Commerce / Hybris / SAP CX jobs, best fit first.
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
git stash -q >nul 2>nul
git -c gc.auto=0 pull -q
git stash pop -q >nul 2>nul
set APPLY_ONLY=sap commerce^|hybris^|sap commerce cloud^|sap cx^|spartacus
call claude mcp remove playwright >nul 2>nul
rem own Chrome window that stays open after Claude finishes (CAPTCHA tabs stay for her)
start "" chrome --remote-debugging-port=9222 --user-data-dir="%CD%\out\chrome-apply" about:blank
timeout /t 3 >nul
call claude mcp add playwright -- npx @playwright/mcp@latest --cdp-endpoint http://localhost:9222 >nul
if not exist out mkdir out
echo Applying to the open SAP Commerce / SAP CX jobs ...
call claude -p --model sonnet --permission-mode acceptEdits "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs; stop early when 'next 1' returns an empty list." >> out\claude_runs.log
git add APPLIED.md helper/PLAYBOOK.md data >nul 2>nul
git commit -qm "Claude applier: SAP focus run" >nul 2>nul
git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
git push -q >nul 2>nul
python -m helper.claude_jobs parked
pause
