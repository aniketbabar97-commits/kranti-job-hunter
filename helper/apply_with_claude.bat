@echo off
rem One click: Claude Code applies to up to 50 jobs (5 fresh sessions x 10 jobs), learns into helper/PLAYBOOK.md.
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
git -c gc.auto=0 pull -q
call claude mcp remove playwright >nul 2>nul
rem own Chrome window that stays open after Claude finishes (CAPTCHA tabs stay for her)
start "" chrome --remote-debugging-port=9222 --user-data-dir="%CD%\out\chrome-apply" about:blank
timeout /t 3 >nul
call claude mcp add playwright -- npx @playwright/mcp@latest --cdp-endpoint http://localhost:9222 >nul
set /p B=How many batches of 10 jobs (5 = 50 jobs)? 
if "%B%"=="" set B=5
if not exist out mkdir out
for /L %%i in (1,1,%B%) do (
  echo ===== batch %%i of %B% =====
  call claude -p --model sonnet --permission-mode acceptEdits "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs." >> out\claude_runs.log
  git add APPLIED.md helper/PLAYBOOK.md data >nul 2>nul
  git commit -qm "Claude applier: batch %%i results + playbook" >nul 2>nul
  git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
  git push -q >nul 2>nul
)
echo.
echo Done. Results: out\claude_runs.log   (CAPTCHA jobs are listed there with their open tabs)
type out\claude_runs.log | findstr /i "confirmed parked closed pending"
pause
