@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title career-copilot setup

echo =====================================================
echo    career-copilot  -  one-time setup
echo =====================================================
echo This installs what the app needs, then starts it.
echo Leave this window open while using the app.
echo.

REM ---------- Step 1: Node.js ----------
echo [1/5] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
  echo    Node.js is not installed. Trying to install it for you...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo    Please install Node.js ^(LTS^) from https://nodejs.org then run setup again.
    pause & exit /b 1
  )
  winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
  echo.
  echo    Node.js was installed. Please CLOSE this window and run setup.bat again
  echo    so the change takes effect.
  pause & exit /b 0
)
for /f "delims=" %%v in ('node --version') do echo    Node %%v found.

REM ---------- Step 2: Python ----------
echo [2/5] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
  echo    Python is not installed. Trying to install it for you...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo    Please install Python from https://python.org/downloads
    echo    Tick "Add Python to PATH" during install, then run setup again.
    pause & exit /b 1
  )
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo    Python was installed. Please CLOSE this window and run setup.bat again.
  pause & exit /b 0
)
for /f "delims=" %%v in ('python --version') do echo    %%v found.

REM ---------- Step 3: app dependencies ----------
echo [3/5] Installing app dependencies...
if not exist "node_modules" (
  call npm install
  if errorlevel 1 ( echo    npm install failed. & pause & exit /b 1 )
) else (
  echo    Already installed.
)

REM Repair the Electron binary if it did not unpack ^(a known Windows hiccup^).
if not exist "node_modules\electron\dist\electron.exe" (
  echo    Repairing Electron...
  node node_modules\electron\install.js >nul 2>nul
  if not exist "node_modules\electron\dist\electron.exe" (
    powershell -NoProfile -Command "$z = Get-ChildItem \"$env:LOCALAPPDATA\electron\Cache\*\electron-*.zip\" -ErrorAction SilentlyContinue | Select-Object -First 1; if ($z) { Expand-Archive -Path $z.FullName -DestinationPath 'node_modules\electron\dist' -Force; Set-Content -Path 'node_modules\electron\path.txt' -Value 'electron.exe' -NoNewline }"
  )
)

REM ---------- Step 4: Python backend ----------
echo [4/5] Setting up the local backend...
if not exist "backend\.venv" (
  python -m venv backend\.venv
)
call backend\.venv\Scripts\python -m pip install --upgrade pip -q
call backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt
if errorlevel 1 ( echo    Backend setup failed. & pause & exit /b 1 )
echo    Backend ready.

REM ---------- Step 5: launch ----------
echo [5/5] Starting career-copilot...
echo.
echo Setup complete. The app window opens in a moment.
echo Next time, just double-click career-copilot.vbs to start it.
echo.
call npm run dev

endlocal
