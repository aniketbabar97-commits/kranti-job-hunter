@echo off
cd /d "%~dp0.."
set PYTHONUTF8=1
chcp 65001 >nul
echo Installing the application helper (one time, about 3 minutes)...
where python >nul 2>nul || (echo Python is missing. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH". Then run setup.bat again. & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r helper\requirements.txt || (pause & exit /b 1)
python -m playwright install chromium || (pause & exit /b 1)
if not exist helper\me.env copy helper\me.env.example helper\me.env
echo.
echo Done. Next: open helper\me.env in Notepad and put in your phone and email,
echo save your photo as profile\photo.jpg, then double-click helper\start.bat.
pause
