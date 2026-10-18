@echo off
cd /d "%~dp0.."
where git >nul 2>nul && git pull -q
python -m helper.apply
pause
