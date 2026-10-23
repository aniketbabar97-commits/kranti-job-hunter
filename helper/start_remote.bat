@echo off
rem Phone control: run this once on the PC, leave it open, then use the Claude app on the phone (see helper/PHONE.md).
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
git stash -q >nul 2>nul
git -c gc.auto=0 pull -q
git stash pop -q >nul 2>nul
rem best-fit jobs first (score 75+, last 10 days); say "all jobs" on the phone to lift it
set MIN_SCORE=75
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-10).ToString('yyyy-MM-dd')"') do set APPLY_SINCE=%%d
rem own Chrome window that stays open (CAPTCHA tabs stay), Playwright attaches to it
start "" chrome --remote-debugging-port=9222 --user-data-dir="%CD%\out\chrome-apply" about:blank
timeout /t 3 >nul
call claude mcp remove playwright >nul 2>nul
call claude mcp add playwright -- npx @playwright/mcp@latest --cdp-endpoint http://localhost:9222 >nul
echo.
echo Ready. Open the Claude app on your phone - Code - this session ("kranti-job-hunter").
echo Keep this window and Chrome open. Close this window to stop.
echo.
call claude remote-control
