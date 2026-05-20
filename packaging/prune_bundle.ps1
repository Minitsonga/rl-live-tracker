# Prune PyInstaller bundle under dist/RLLiveTracker/_internal (idempotent).
param(
    [string]$BundleRoot = "dist\RLLiveTracker"
)

$ErrorActionPreference = "Stop"
$deps = Join-Path $BundleRoot "_internal"
if (-not (Test-Path $deps)) {
    Write-Warning "Deps folder not found: $deps"
    exit 0
}

function Get-DirSizeMb([string]$Path) {
    if (-not (Test-Path $Path)) { return 0.0 }
    $bytes = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if (-not $bytes) { return 0.0 }
    return [math]::Round($bytes / 1MB, 2)
}

function Remove-IfExists([string]$Path) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$before = Get-DirSizeMb $BundleRoot
Write-Host "Bundle size before prune: $before MB"

$pyside = Join-Path $deps "PySide6"
$qtPlugins = Join-Path $pyside "plugins"

$qtDropDlls = @(
    "opengl32sw.dll",
    "Qt6Quick.dll", "Qt6Qml.dll", "Qt6QmlMeta.dll", "Qt6QmlModels.dll", "Qt6QmlWorkerScript.dll",
    "Qt6Pdf.dll", "Qt6OpenGL.dll", "Qt6Svg.dll", "Qt6VirtualKeyboard.dll",
    "Qt6Network.dll", "QtNetwork.pyd"
)
foreach ($name in $qtDropDlls) {
    Remove-IfExists (Join-Path $pyside $name)
}

$removePatterns = @("_tk_data", "tcl", "gevent", "zope")
foreach ($pat in $removePatterns) {
    Get-ChildItem -Path $deps -Filter $pat -Recurse -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-IfExists $_.FullName }
}

$relativeDirs = @(
    "PySide6\qml", "Qt6\qml",
    "PySide6\translations", "Qt6\translations",
    "PySide6\resources",
    "PySide6\plugins\multimedia", "PySide6\plugins\audio", "PySide6\plugins\mediaservice",
    "PySide6\plugins\generic", "PySide6\plugins\networkinformation",
    "PySide6\plugins\platforminputcontexts", "PySide6\plugins\tls",
    "PySide6\plugins\iconengines"
)
foreach ($rel in $relativeDirs) {
    Remove-IfExists (Join-Path $deps $rel)
}

$platforms = Join-Path $qtPlugins "platforms"
if (Test-Path $platforms) {
    Get-ChildItem -Path $platforms -Filter "*.dll" -File |
        Where-Object { $_.Name -ne "qwindows.dll" } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}

$img = Join-Path $qtPlugins "imageformats"
if (Test-Path $img) {
    Get-ChildItem -Path $img -Filter "*.dll" -File |
        Where-Object { $_.Name -notin @("qico.dll", "qgif.dll") } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}

$styles = Join-Path $qtPlugins "styles"
if (Test-Path $styles) {
    Get-ChildItem -Path $styles -Filter "*.dll" -File |
        Where-Object { $_.Name -ne "qmodernwindowsstyle.dll" } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}

Get-ChildItem -Path $deps -Recurse -Filter "QtWebEngine*" -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-IfExists $_.FullName }

Get-ChildItem -Path $deps -Recurse -Filter "*.pdb" -File -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }

$libDup = Join-Path $deps "libcrypto-3.dll"
if ((Test-Path $libDup) -and (Test-Path (Join-Path $deps "libcrypto-3-x64.dll"))) {
    Remove-Item -LiteralPath $libDup -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $deps "libssl-3.dll") -Force -ErrorAction SilentlyContinue
}

# Stdlib extensions not required at runtime (verified post-build)
foreach ($pyd in @("_bz2.pyd", "_lzma.pyd")) {
    $p = Join-Path $deps $pyd
    if (Test-Path $p) {
        Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
    }
}

$after = Get-DirSizeMb $BundleRoot
Write-Host "Bundle size after prune: $after MB"

$reportDir = "build"
if (-not (Test-Path $reportDir)) { New-Item -ItemType Directory -Path $reportDir | Out-Null }
$reportPath = Join-Path $reportDir "size-report.txt"
$lines = @(
    "Bundle: $BundleRoot",
    "Before prune: $before MB",
    "After prune: $after MB",
    "",
    "Size by top-level folder under _internal/:"
)
$folderSizes = Get-ChildItem -Path $deps -Directory -ErrorAction SilentlyContinue |
    ForEach-Object {
        $mb = Get-DirSizeMb $_.FullName
        [PSCustomObject]@{ Name = $_.Name; Mb = $mb }
    } | Sort-Object Mb -Descending
foreach ($f in $folderSizes) {
    $lines += ("{0,8} MB  {1}/" -f $f.Mb, $f.Name)
}
$rootMb = Get-ChildItem -Path $deps -File -ErrorAction SilentlyContinue |
    Measure-Object -Property Length -Sum
if ($rootMb.Sum) {
    $rmb = [math]::Round($rootMb.Sum / 1MB, 2)
    $lines += ("{0,8} MB  (root .pyd/.dll)" -f $rmb)
}
$lines += ""
$lines += "Top 20 largest files under _internal/:"
$top = Get-ChildItem -Path $deps -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending |
    Select-Object -First 20
foreach ($f in $top) {
    $rel = $f.FullName.Substring($deps.Length).TrimStart('\', '/')
    $mb = [math]::Round($f.Length / 1MB, 2)
    $lines += ("{0,8} MB  {1}" -f $mb, $rel)
}
$lines | Set-Content -Path $reportPath -Encoding UTF8
Write-Host "Size report: $reportPath"

if ($after -gt 50) {
    Write-Warning "Installed size $after MB exceeds target 50 MB - see $reportPath"
}
