@echo off
setlocal EnableDelayedExpansion
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
set MIN_SCORE=60
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-14).ToString('yyyy-MM-dd')"') do set APPLY_SINCE=%%d
rem same browser setup as the runs that worked (registered MCP server, Playwright starts its own Chrome)
call claude mcp remove playwright >nul 2>nul
call claude mcp add playwright -- npx @playwright/mcp@latest --browser chrome --user-data-dir "%CD%\out\pw-profile" >> out\nightly_diag.log 2>&1
for /L %%i in (1,1,5) do (
  call claude -p --model sonnet --permission-mode acceptEdits "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs; stop early when 'next 1' returns an empty list." > out\batch.txt 2>&1 < nul
  set RC=!errorlevel!
  type out\batch.txt >> out\claude_runs.log
  echo [!date! !time!] batch %%i exit !RC! >> out\nightly_diag.log
  powershell -NoProfile -Command "Get-Content out\batch.txt -Tail 8" >> out\nightly_diag.log
  rem share the run report with GitHub (so the cloud side can follow every run)
  type out\batch.txt >> data\run_reports.log
  copy /y out\nightly_diag.log data\nightly_diag.log >nul 2>nul
  git add APPLIED.md helper/PLAYBOOK.md data >nul 2>nul
  git commit -qm "Claude applier: nightly batch %%i" >nul 2>nul
  git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
  git push -q >nul 2>nul
)
python -m helper.claude_jobs parked > out\parked_tonight.txt 2>&1
copy /y out\parked_tonight.txt data\parked.txt >nul 2>nul
git add data >nul 2>nul
git commit -qm "Claude applier: parked list" >nul 2>nul
git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
git push -q >nul 2>nul
