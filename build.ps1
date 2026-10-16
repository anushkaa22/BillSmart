<#
.SYNOPSIS
  Build the BillSmart Windows desktop app: PyInstaller one-dir + optional Inno Setup installer.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\build.ps1            # app bundle only
  powershell -ExecutionPolicy Bypass -File .\build.ps1 -Installer # + Setup exe (needs Inno Setup 6)
#>
param(
  [switch]$Installer,
  [string]$Python = "python.exe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> [1/4] Installing dependencies ($Python)" -ForegroundColor Cyan
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt

Write-Host "==> [2/4] Running PyInstaller" -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm billsmart.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$Exe = Join-Path $Root "dist\BillSmart\BillSmart.exe"
if (-not (Test-Path $Exe)) { throw "Expected output missing: $Exe" }
Write-Host "OK: $Exe" -ForegroundColor Green

Write-Host "==> [3/4] Sanity check (frozen-mode import paths)" -ForegroundColor Cyan
$env:BILLSMART_DATA_DIR = Join-Path ([IO.Path]::GetTempPath()) "billsmart-build-check"
& $Python -c "import app; print('dev import ok:', app.APP_NAME, app.APP_VERSION, '| db:', app.DB_PATH)"

if ($Installer) {
  Write-Host "==> [4/4] Building installer (Inno Setup)" -ForegroundColor Cyan
  $Iscc = $null
  foreach ($cand in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")) {
    if (Test-Path $cand) { $Iscc = $cand; break }
  }
  if (-not $Iscc) { throw "ISCC.exe not found. Install Inno Setup 6 first: https://jrsoftware.org/isinfo.php" }
  & $Iscc "installer.iss"
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
  Get-ChildItem (Join-Path $Root "installer-output") | Format-Table Name, Length
} else {
  Write-Host "Skipped installer (pass -Installer to build Setup exe)" -ForegroundColor Yellow
}

Write-Host "Build complete." -ForegroundColor Green
