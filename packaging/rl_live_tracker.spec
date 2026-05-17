# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-dir build for RL Live Tracker (Windows)."""
import os
from pathlib import Path

_spec_dir = os.path.abspath(SPECPATH)
_repo = os.path.dirname(_spec_dir)
distpath = os.path.join(_repo, "dist")
workpath = os.path.join(_repo, "build", "pyinstaller")
specpath = _spec_dir

root = Path(_repo)
src = root / "src"

_EXCLUDES = [
    "tkinter",
    "_tkinter",
    "matplotlib",
    "numpy",
    "pandas",
    "PIL",
    "IPython",
    "notebook",
    "pytest",
    "setuptools",
    "gevent",
    "greenlet",
    "zope",
    "test",
    "unittest",
    "pydoc",
    "doctest",
    "xmlrpc",
    "lib2to3",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtPdf",
    "PySide6.QtDesigner",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtHelp",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtSerialPort",
    "PySide6.QtSensors",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtStateMachine",
    "PySide6.QtUiTools",
    "PySide6.QtXml",
    "PySide6.QtNetworkAuth",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtNetwork",
]

block_cipher = None

a = Analysis(
    [str(root / "packaging" / "entry.py")],
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
    excludes=_EXCLUDES,
    cipher=block_cipher,
    noarchive=False,
)

_SKIP_BIN_SUBSTR = (
    "Qt6Qml",
    "Qt6Quick",
    "Qt6Pdf",
    "Qt6OpenGL",
    "Qt6Svg",
    "Qt6VirtualKeyboard",
    "Qt6Network",
    "opengl32sw",
    "QtNetwork.pyd",
)

a.binaries = [
    row
    for row in a.binaries
    if not any(part in row[0] for part in _SKIP_BIN_SUBSTR)
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RLLiveTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
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
    strip=True,
    upx=False,
    upx_exclude=[],
    name="RLLiveTracker",
)
