# Build PyInstaller one-dir + Inno Setup installer (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$pyproject = Join-Path $Root "pyproject.toml"
$versionLine = Select-String -Path $pyproject -Pattern '^version\s*=\s*"(.+)"' | Select-Object -First 1
$version = if ($versionLine) { $versionLine.Matches.Groups[1].Value } else { "0.0.0" }
# Inno AppVersion: digits and dots only (1.0.0-beta.2 -> 1.0.0.2)
$innoVersion = ($version -replace "^v", "" -replace "-beta\.", ".")
if ($innoVersion -notmatch "^\d+(\.\d+)*$") {
    $innoVersion = "1.0.0.2"
}

Write-Host "Building RL Live Tracker $version (Inno $innoVersion)..."

python -m pip install -q -e .
python -m pip install -q pyinstaller

if (Test-Path "dist\RLLiveTracker") {
    Remove-Item -Recurse -Force "dist\RLLiveTracker"
}

python -m PyInstaller packaging\rl_live_tracker.spec --noconfirm --clean

$exe = "dist\RLLiveTracker\RLLiveTracker.exe"
if (-not (Test-Path $exe)) {
    throw "PyInstaller failed: $exe not found"
}

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $iscc)) {
    Write-Warning "Inno Setup not found — PyInstaller output is in dist\RLLiveTracker"
    exit 0
}

& $iscc "packaging\installer.iss" "/DMyAppVersion=$innoVersion"
Write-Host "Done: dist\RLLiveTracker-Setup-$innoVersion.exe"
