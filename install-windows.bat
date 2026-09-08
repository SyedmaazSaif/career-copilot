@echo off
REM career-copilot one-click installer for Windows.
REM
REM Download this one file, double-click it, and it does the rest: fetches the
REM app, installs Node and Python if they are missing, sets everything up,
REM offers the optional local AI, and starts it.
REM
REM If Windows shows "Windows protected your PC", that is SmartScreen reacting
REM to a file downloaded from the internet, not a problem with this file:
REM click "More info", then "Run anyway".

setlocal enabledelayedexpansion
title career-copilot installer

if "%CAREER_COPILOT_DIR%"=="" set "CAREER_COPILOT_DIR=%USERPROFILE%\career-copilot"
if "%CAREER_COPILOT_REPO%"=="" set "CAREER_COPILOT_REPO=SyedmaazSaif/career-copilot"
if "%CAREER_COPILOT_BRANCH%"=="" set "CAREER_COPILOT_BRANCH=main"
set "ZIP_URL=https://github.com/%CAREER_COPILOT_REPO%/archive/refs/heads/%CAREER_COPILOT_BRANCH%.zip"
set "WORK=%TEMP%\career-copilot-install"

echo =====================================================
echo    career-copilot  -  installer ^(Windows^)
echo =====================================================
echo Installing to: %CAREER_COPILOT_DIR%
echo.

REM ---------- Download ----------
echo [1/3] Downloading career-copilot...
if exist "%WORK%" rmdir /s /q "%WORK%"
mkdir "%WORK%" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%WORK%\app.zip' -UseBasicParsing"
if errorlevel 1 (
  echo    Download failed. Check your internet connection and try again.
  pause & exit /b 1
)

REM ---------- Unpack ----------
echo [2/3] Unpacking...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; Expand-Archive -Path '%WORK%\app.zip' -DestinationPath '%WORK%\unpacked' -Force"
if errorlevel 1 ( echo    Could not unpack the download. & pause & exit /b 1 )

REM The zip contains one folder, named for the repo and branch.
set "SRC="
for /d %%d in ("%WORK%\unpacked\*") do set "SRC=%%~fd"
if "%SRC%"=="" ( echo    The download did not contain the app. & pause & exit /b 1 )

REM Keep what belongs to the user, not to the app: their profile database,
REM their settings, and the CVs already generated. Reinstalling must never be
REM the reason someone loses their job search.
if exist "%CAREER_COPILOT_DIR%" (
  echo    An existing install is here already - updating it, keeping your data.
  set "KEEP=%WORK%\keep"
  mkdir "!KEEP!" 2>nul
  if exist "%CAREER_COPILOT_DIR%\backend\data"     xcopy /e /i /q /y "%CAREER_COPILOT_DIR%\backend\data" "!KEEP!\data" >nul
  if exist "%CAREER_COPILOT_DIR%\applications"     xcopy /e /i /q /y "%CAREER_COPILOT_DIR%\applications" "!KEEP!\applications" >nul
  if exist "%CAREER_COPILOT_DIR%\.env"             copy /y "%CAREER_COPILOT_DIR%\.env" "!KEEP!\.env" >nul
  if exist "%CAREER_COPILOT_DIR%\master_profile.yaml" copy /y "%CAREER_COPILOT_DIR%\master_profile.yaml" "!KEEP!\master_profile.yaml" >nul
  REM node_modules and the venv are large and rebuilt anyway; move them across
  REM rather than making the user download them a second time.
  if exist "%CAREER_COPILOT_DIR%\node_modules"   move "%CAREER_COPILOT_DIR%\node_modules" "%SRC%\node_modules" >nul
  if exist "%CAREER_COPILOT_DIR%\backend\.venv"  move "%CAREER_COPILOT_DIR%\backend\.venv" "%SRC%\backend\.venv" >nul
  rmdir /s /q "%CAREER_COPILOT_DIR%"
)

move "%SRC%" "%CAREER_COPILOT_DIR%" >nul
if errorlevel 1 ( echo    Could not write to %CAREER_COPILOT_DIR%. & pause & exit /b 1 )

if exist "%WORK%\keep" (
  if exist "%WORK%\keep\data"         xcopy /e /i /q /y "%WORK%\keep\data" "%CAREER_COPILOT_DIR%\backend\data" >nul
  if exist "%WORK%\keep\applications" xcopy /e /i /q /y "%WORK%\keep\applications" "%CAREER_COPILOT_DIR%\applications" >nul
  if exist "%WORK%\keep\.env"         copy /y "%WORK%\keep\.env" "%CAREER_COPILOT_DIR%\.env" >nul
  if exist "%WORK%\keep\master_profile.yaml" copy /y "%WORK%\keep\master_profile.yaml" "%CAREER_COPILOT_DIR%\master_profile.yaml" >nul
)

REM ---------- Desktop shortcut ----------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'career-copilot.lnk')); $s.TargetPath='%CAREER_COPILOT_DIR%\career-copilot.vbs'; $s.WorkingDirectory='%CAREER_COPILOT_DIR%'; $s.Description='career-copilot'; $s.Save()" >nul 2>nul

REM ---------- Hand over to setup ----------
echo [3/3] Running setup...
echo.
cd /d "%CAREER_COPILOT_DIR%"
call setup.bat

endlocal
