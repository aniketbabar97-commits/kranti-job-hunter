@echo off
rem Unattended best-fit run (started by Windows Task Scheduler, see setup_nightly.bat). No questions, no pause.
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
if not exist out mkdir out
rem diagnostics: a scheduled task has a thinner PATH than a normal window
(echo [%date% %time%] start, user %USERNAME%, dir %CD% & where claude & where python & where git & where npx & where chrome) >> out\nightly_diag.log 2>&1
call claude --version >> out\nightly_diag.log 2>&1
echo ===== nightly run %date% %time% ===== >> out\claude_runs.log
git stash -q >nul 2>nul
git -c gc.auto=0 pull -q >nul 2>nul
git stash pop -q >nul 2>nul
set MIN_SCORE=75
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-14).ToString('yyyy-MM-dd')"') do set APPLY_SINCE=%%d
rem own Chrome window that stays open in the morning (CAPTCHA tabs), Playwright attaches to it
start "" chrome --remote-debugging-port=9222 --user-data-dir="%CD%\out\chrome-apply" about:blank
timeout /t 5 >nul
call claude mcp remove playwright >nul 2>nul
call claude mcp add playwright -- npx @playwright/mcp@latest --cdp-endpoint http://localhost:9222 >nul
for /L %%i in (1,1,5) do (
  call claude -p --model sonnet --permission-mode acceptEdits "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs; stop early when 'next 1' returns an empty list." >> out\claude_runs.log 2>&1
  echo [%date% %time%] batch %%i exit %errorlevel% >> out\nightly_diag.log
  git add APPLIED.md helper/PLAYBOOK.md data >nul 2>nul
  git commit -qm "Claude applier: nightly batch %%i" >nul 2>nul
  git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
  git push -q >nul 2>nul
)
python -m helper.claude_jobs parked > out\parked_tonight.txt 2>&1
