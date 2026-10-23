@echo off
rem One-time setup: Windows runs helper\nightly.bat every night at 23:00 (wakes the PC from sleep).
rem Run again to change nothing; to remove:  schtasks /Delete /TN "Kranti job applications" /F
cd /d "%~dp0.."
set TIME_AT=23:00
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$a = New-ScheduledTaskAction -Execute '%CD%\helper\nightly.bat' -WorkingDirectory '%CD%';" ^
 "$t = New-ScheduledTaskTrigger -Daily -At '%TIME_AT%';" ^
 "$s = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 6);" ^
 "Register-ScheduledTask -TaskName 'Kranti job applications' -Action $a -Trigger $t -Settings $s -Force | Out-Null"
if errorlevel 1 (echo Setup failed. & pause & exit /b 1)
echo Done: runs every night at %TIME_AT% (also when the PC was asleep or missed it).
set /p NOW=Start a run right now as well? (y/n) 
if /i "%NOW%"=="y" powershell -NoProfile -Command "Start-ScheduledTask -TaskName 'Kranti job applications'" & echo Started - Chrome opens in a few seconds. Results: out\claude_runs.log
pause
