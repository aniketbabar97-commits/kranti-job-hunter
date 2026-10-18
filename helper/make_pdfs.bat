@echo off
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
where git >nul 2>nul && git -c gc.auto=0 pull -q
python -m helper.make_pdfs
pause
