@echo off
setlocal EnableDelayedExpansion
rem One apply worker on Chrome port %1 (3 batches of 10). Called by nightly_fast.bat.
cd /d "%~dp0.."
for /L %%i in (1,1,3) do (
  call claude -p --model sonnet --permission-mode acceptEdits --mcp-config out\mcp-%1.json --strict-mcp-config "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs; stop early when 'next 1' returns an empty list." > out\batch_%1.txt 2>&1
  set RC=!errorlevel!
  type out\batch_%1.txt >> out\claude_runs_%1.log
  echo [!date! !time!] worker %1 batch %%i exit !RC! >> out\nightly_diag.log
  powershell -NoProfile -Command "Get-Content out\batch_%1.txt -Tail 8" >> out\nightly_diag.log
)
