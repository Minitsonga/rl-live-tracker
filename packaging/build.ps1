# Build PyInstaller one-dir + Inno Setup installer (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$pyproject = Join-Path $Root "pyproject.toml"
$versionLine = Select-String -Path $pyproject -Pattern '^version\s*=\s*"(.+)"' | Select-Object -First 1
$version = if ($versionLine) { $versionLine.Matches.Groups[1].Value } else { "0.0.0" }
# Inno AppVersion: X.Y.Z only (strip pre-release suffixes like -beta.2)
$innoVersion = ($version -replace "^v", "" -replace "-.*$", "")
if ($innoVersion -notmatch "^\d+(\.\d+)*$") {
    $innoVersion = "1.0.0"
}

Write-Host "Building RL Live Tracker $version (Inno $innoVersion)..."

$running = Get-Process -Name "RLLiveTracker" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Stopping running RLLiveTracker.exe (required to replace dist/)..."
    $running | Stop-Process -Force
    Start-Sleep -Seconds 2
}

python -m pip install -q -e .
python -m pip install -q pyinstaller

if (Test-Path "build\pyinstaller") {
    Remove-Item -Recurse -Force "build\pyinstaller"
}
if (Test-Path "build\rl_live_tracker") {
    Remove-Item -Recurse -Force "build\rl_live_tracker"
}
if (Test-Path "dist\RLLiveTracker") {
    Remove-Item -Recurse -Force "dist\RLLiveTracker"
}
Get-ChildItem -Path "dist" -Filter "RL-LiveTracker-Setup*.exe" -ErrorAction SilentlyContinue |
    Remove-Item -Force

python -m PyInstaller packaging\rl_live_tracker.spec --noconfirm --clean

$exe = "dist\RLLiveTracker\RLLiveTracker.exe"
if (-not (Test-Path $exe)) {
    throw "PyInstaller failed: $exe not found"
}

# Do not rename _internal: PyInstaller bootloader expects that folder name.
$deps = "dist\RLLiveTracker\_internal"
if (-not (Test-Path $deps)) {
    throw "Expected PyInstaller deps folder missing: $deps"
}

& "$PSScriptRoot\prune_bundle.ps1" -BundleRoot "dist\RLLiveTracker"

$sizeMb = [math]::Round(
    ((Get-ChildItem -Path "dist\RLLiveTracker" -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB),
    1
)
Write-Host "Installed size: $sizeMb MB"

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $iscc)) {
    Write-Warning "Inno Setup not found - PyInstaller output is in dist\RLLiveTracker"
    exit 0
}

& $iscc "packaging\installer.iss" "/DMyAppVersion=$innoVersion"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compile failed (exit $LASTEXITCODE)"
}
$setup = "dist\RL-LiveTracker-Setup.exe"
if (-not (Test-Path $setup)) {
    throw "Installer not found: $setup"
}
Write-Host "Done: $setup ($sizeMb MB installed folder before compression)"
