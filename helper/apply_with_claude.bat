@echo off
rem One click: update, then Claude Code applies to jobs in a real Chrome window.
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
git -c gc.auto=0 pull -q
call claude mcp get playwright >nul 2>nul || call claude mcp add playwright -- npx @playwright/mcp@latest --browser chrome
set /p N=How many jobs?
call claude "Read helper/CLAUDE_CODE_APPLY.md and follow it exactly. Apply to %N% jobs."
pause
