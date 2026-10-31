# career-copilot one-line installer for Windows.
#
#   irm https://github.com/SyedmaazSaif/career-copilot/releases/latest/download/install-windows.ps1 | iex
#
# Fetches the Windows installer from the latest release and runs it.
# Nothing here needs administrator rights. Works on Windows 10 and 11.

$ErrorActionPreference = "Stop"

# Older PowerShell defaults to TLS 1.0; GitHub needs 1.2.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = "SyedmaazSaif/career-copilot"
$url = "https://github.com/$repo/releases/latest/download/Install-Career-Copilot-Windows.zip"
$work = Join-Path $env:TEMP "career-copilot-install"
$zip = Join-Path $work "installer.zip"

Write-Host ""
Write-Host "====================================================="
Write-Host "   Career Copilot - installer (Windows)"
Write-Host "====================================================="

if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force -Path $work | Out-Null

Write-Host "Downloading the installer..."
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

Write-Host "Unpacking..."
Expand-Archive -Path $zip -DestinationPath $work -Force

$bat = Get-ChildItem -Path $work -Recurse -Filter "*.bat" | Select-Object -First 1
if ($null -eq $bat) {
    Write-Host ""
    Write-Host "Install stopped: the download did not contain the installer."
    exit 1
}

Write-Host "Starting setup..."
Write-Host ""
& $bat.FullName
