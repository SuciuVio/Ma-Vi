param(
    [string]$ProjectRoot = "C:\mavi_project"
)

$ErrorActionPreference = "Stop"

Write-Host "Ma:Vi Android build preflight"
Write-Host "Project: $ProjectRoot"

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    throw "Project directory not found: $ProjectRoot"
}

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-Host "WSL executable was not found."
    Write-Host "Run PowerShell as Administrator and execute: wsl.exe --install -d Ubuntu"
    exit 2
}

$ErrorActionPreference = "Continue"
$status = & wsl.exe --status 2>&1
$statusCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($statusCode -ne 0) {
    Write-Host "WSL is not ready:"
    Write-Host $status
    Write-Host "Run PowerShell as Administrator and execute: wsl.exe --install -d Ubuntu"
    Write-Host "Restart Windows if requested, then run this preflight again."
    exit 2
}

Write-Host "WSL status:"
Write-Host $status

$linuxCheck = & wsl.exe bash -lc "python3 --version && command -v buildozer || true" 2>&1
Write-Host $linuxCheck

if ($linuxCheck -notmatch "buildozer") {
    Write-Host "Buildozer is not installed inside WSL."
    Write-Host "Inside WSL, run:"
    Write-Host "cd /mnt/c/mavi_project"
    Write-Host "python3 -m venv .buildozer-venv"
    Write-Host "source .buildozer-venv/bin/activate"
    Write-Host "pip install --upgrade pip"
    Write-Host "pip install buildozer cython"
    exit 3
}

Write-Host "Preflight passed. You can run:"
Write-Host "wsl.exe bash -lc 'cd /mnt/c/mavi_project && source .buildozer-venv/bin/activate && buildozer android debug'"
