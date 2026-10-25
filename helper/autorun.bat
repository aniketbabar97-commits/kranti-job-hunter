@echo off
rem Started by Windows every 30 minutes while the PC is on (see setup_nightly.bat).
rem Applies only when jobs are waiting and no run is going; picks up where the last run stopped.
cd /d "%~dp0.."
set PYTHONUTF8=1
if not exist out mkdir out
rem a run is going (lock younger than 6 h AND Claude still running) -> nothing to do
rem a lock left behind by sleep / shutdown / a frozen window is ignored
if exist out\run.lock (
  powershell -NoProfile -Command "if((((Get-Date)-(Get-Item out\run.lock).LastWriteTime).TotalHours -lt 6) -and (Get-Process claude -ErrorAction SilentlyContinue)){exit 1}else{exit 0}" || exit /b 0
)
git -c gc.auto=0 pull -q --autostash >nul 2>nul
set MIN_SCORE=60
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-14).ToString('yyyy-MM-dd')"') do set APPLY_SINCE=%%d
set N=0
for /f %%n in ('python -m helper.claude_jobs count 2^>nul') do set N=%%n
echo [%date% %time%] autorun: %N% jobs waiting >> out\nightly_diag.log
if "%N%"=="0" exit /b 0
echo %date% %time% > out\run.lock
call helper\nightly.bat
del out\run.lock >nul 2>nul
