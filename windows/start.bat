@echo off
REM Starts career-copilot and closes straight away.
REM
REM This file only exists for people who reach for a .bat out of habit. A .bat
REM always flashes a console window for a moment, which is why the real
REM launcher is career-copilot.vbs -- it shows nothing at all. Use that one,
REM or the desktop shortcut setup creates.
REM
REM All output goes to %USERPROFILE%\.career-copilot\logs\app.log

cd /d "%~dp0"
start "" wscript.exe "%~dp0career-copilot.vbs"
exit /b 0
