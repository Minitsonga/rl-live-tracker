# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-dir build for RL Live Tracker (Windows)."""
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent
src = root / "src"

a = Analysis(
    [str(src / "rl_live_tracker" / "__main__.py")],
    pathex=[str(src)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._win32",
        "curl_cffi",
        "curl_cffi.requests",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RLLiveTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RLLiveTracker",
)
