@echo off
rem Focus run: strong / best-fit jobs (score 75+) found in the last 10 days, best fit first.
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
git stash -q >nul 2>nul
git -c gc.auto=0 pull -q
git stash pop -q >nul 2>nul
set MIN_SCORE=75
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-10).ToString('yyyy-MM-dd')"') do set APPLY_SINCE=%%d
call claude mcp remove playwright >nul 2>nul
rem own Chrome window that stays open after Claude finishes (CAPTCHA tabs stay for her)
start "" chrome --remote-debugging-port=9222 --user-data-dir="%CD%\out\chrome-apply" about:blank
timeout /t 3 >nul
call claude mcp add playwright -- npx @playwright/mcp@latest --cdp-endpoint http://localhost:9222 >nul
if not exist out mkdir out
echo Applying to the strong / best-fit jobs (score 75+, last 10 days) ...
for /L %%i in (1,1,4) do call claude -p --model sonnet --permission-mode acceptEdits "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs; stop early when 'next 1' returns an empty list." >> out\claude_runs.log
git add APPLIED.md helper/PLAYBOOK.md data >nul 2>nul
git commit -qm "Claude applier: best-fit run" >nul 2>nul
git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
git push -q >nul 2>nul
python -m helper.claude_jobs parked
pause
