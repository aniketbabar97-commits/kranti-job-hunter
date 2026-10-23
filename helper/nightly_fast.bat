@echo off
rem Faster unattended run: 2 workers in parallel, each with its own Chrome window. Jobs are claimed, never done twice.
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
if not exist out mkdir out
echo ===== nightly fast run %date% %time% ===== >> out\claude_runs.log
git stash -q >nul 2>nul
git -c gc.auto=0 pull -q >nul 2>nul
git stash pop -q >nul 2>nul
set MIN_SCORE=75
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-14).ToString('yyyy-MM-dd')"') do set APPLY_SINCE=%%d
for %%p in (9222 9223) do (
  start "" chrome --remote-debugging-port=%%p --user-data-dir="%CD%\out\chrome-apply-%%p" about:blank
  > out\mcp-%%p.json echo {"mcpServers":{"playwright":{"command":"cmd","args":["/c","npx","@playwright/mcp@latest","--cdp-endpoint","http://localhost:%%p"]}}}
)
timeout /t 5 >nul
start "worker 1" /min cmd /c helper\worker.bat 9222
call helper\worker.bat 9223
rem wait for worker 1 to finish too
:wait
tasklist /v | find "worker 1" >nul && (timeout /t 30 >nul & goto wait)
git add APPLIED.md helper/PLAYBOOK.md data >nul 2>nul
git commit -qm "Claude applier: nightly fast run" >nul 2>nul
git -c gc.auto=0 pull -q --rebase --autostash >nul 2>nul
git push -q >nul 2>nul
python -m helper.claude_jobs parked > out\parked_tonight.txt 2>&1
