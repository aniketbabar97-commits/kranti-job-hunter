@echo off
rem One apply worker on Chrome port %1 (3 batches of 10). Called by nightly_fast.bat.
cd /d "%~dp0.."
for /L %%i in (1,1,3) do (
  call claude -p --model sonnet --permission-mode acceptEdits --mcp-config out\mcp-%1.json --strict-mcp-config "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to 10 jobs; stop early when 'next 1' returns an empty list." >> out\claude_runs_%1.log 2>&1
)
