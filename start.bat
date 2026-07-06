@echo off
REM Double-click this file to launch career-copilot in dev mode.
REM It starts Vite, Electron, and the Python backend together.
cd /d "%~dp0"
echo Starting career-copilot...
echo (A desktop window will open once Vite and the backend are ready.)
echo Close this console window to stop the app.
echo.
call npm run dev
pause
