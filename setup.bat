@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title career-copilot setup

echo =====================================================
echo    career-copilot  -  setup ^(Windows^)
echo =====================================================
echo This installs what the app needs, then starts it.
echo Leave this window open while you use the app.
echo.

REM ---------- Step 1: Node.js ----------
echo [1/6] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
  echo    Node.js is missing. Installing it for you...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo    This needs Windows Package Manager ^(winget^), which Windows 11 has
    echo    built in. Install Node.js ^(LTS^) from https://nodejs.org, then run
    echo    setup again.
    pause & exit /b 1
  )
  winget install -e --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
  REM winget puts the new PATH in place for future processes, not this one, so
  REM add the standard install location here and carry on rather than making
  REM the user close the window and start over.
  set "PATH=%ProgramFiles%\nodejs;%PATH%"
  where node >nul 2>nul
  if errorlevel 1 (
    echo    Node.js was installed but is not visible yet. Please CLOSE this
    echo    window and run setup.bat again.
    pause & exit /b 0
  )
)
for /f "delims=" %%v in ('node --version') do echo    Node %%v found.

REM ---------- Step 2: Python ----------
echo [2/6] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
  echo    Python is missing. Installing it for you...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo    This needs Windows Package Manager ^(winget^), which Windows 11 has
    echo    built in. Install Python from https://python.org/downloads, ticking
    echo    "Add Python to PATH", then run setup again.
    pause & exit /b 1
  )
  winget install -e --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
  REM As above: make the just-installed Python visible to this window.
  set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
  where python >nul 2>nul
  if errorlevel 1 (
    echo    Python was installed but is not visible yet. Please CLOSE this
    echo    window and run setup.bat again.
    pause & exit /b 0
  )
)
for /f "delims=" %%v in ('python --version') do echo    %%v found.

REM ---------- Step 3: app dependencies ----------
echo [3/6] Installing app dependencies...
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
echo [4/6] Setting up the local backend...
if not exist "backend\.venv" (
  python -m venv backend\.venv
)
call backend\.venv\Scripts\python -m pip install --upgrade pip -q
call backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt
if errorlevel 1 ( echo    Backend setup failed. & pause & exit /b 1 )
REM Settings live in .env, which is not in the repo ^(it is per-machine^).
if not exist ".env" copy ".env.example" ".env" >nul
echo    Backend ready.

REM ---------- Step 5: the optional local AI ----------
echo [5/6] Optional local AI...
call backend\.venv\Scripts\python -m backend.setup_ai

REM ---------- Step 6: launch ----------
echo [6/6] Starting career-copilot...
echo.
echo Setup complete. The app window opens in a moment.
echo Next time, just double-click career-copilot.vbs to start it.
echo.
call npm run dev

endlocal
