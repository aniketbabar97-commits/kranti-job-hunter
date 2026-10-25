@echo off
rem One-time setup. Windows checks every 30 minutes (and at log-on) while the PC is on: if jobs are waiting and no run
rem is going, it applies (helper\autorun.bat). No fixed time - whenever the PC is on, it continues where it stopped.
rem To remove:  schtasks /Delete /TN "Kranti job applications" /F
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$a = New-ScheduledTaskAction -Execute '%CD%\helper\autorun.bat' -WorkingDirectory '%CD%';" ^
 "$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30);" ^
 "$t2 = New-ScheduledTaskTrigger -AtLogOn;" ^
 "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 8);" ^
 "Register-ScheduledTask -TaskName 'Kranti job applications' -Action $a -Trigger @($t1,$t2) -Settings $s -Force | Out-Null"
if errorlevel 1 (echo Setup failed. & pause & exit /b 1)
echo Done: checks every 30 minutes while the PC is on and applies whenever jobs are waiting.
echo First check in 1 minute. Log: out\nightly_diag.log
pause
