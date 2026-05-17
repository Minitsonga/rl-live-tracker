"""Chemins Rocket League / DefaultStatsAPI.ini (Windows)."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path, PureWindowsPath
from typing import Optional

STATS_API_INI_NAME = "DefaultStatsAPI.ini"


def stats_api_ini_from_exe(rocket_league_exe: Path) -> PureWindowsPath:
    """`TAGame/Binaries/Win64/RocketLeague.exe` → `TAGame/Config/DefaultStatsAPI.ini`."""
    # PureWindowsPath: même arbre TAGame/... sur Linux (CI) et Windows.
    exe = PureWindowsPath(rocket_league_exe)
    tagame_dir = exe.parent.parent.parent
    return tagame_dir / "Config" / STATS_API_INI_NAME


def rocket_league_exe_path() -> Optional[Path]:
    """Chemin de RocketLeague.exe si le jeu tourne (Windows), sinon None."""
    if sys.platform != "win32":
        return None
    TH32CS_SNAPPROCESS = 0x2
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    try:
        kernel32 = ctypes.windll.kernel32
        snap = int(kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0))
        if snap == -1:
            return None
        try:
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if not kernel32.Process32First(snap, ctypes.byref(pe)):
                return None
            while True:
                name = pe.szExeFile.decode("utf-8", errors="ignore").lower()
                if name == "rocketleague.exe":
                    pid = int(pe.th32ProcessID)
                    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if not h:
                        return None
                    try:
                        buf = ctypes.create_unicode_buffer(4096)
                        size = wintypes.DWORD(len(buf))
                        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
                        if ok:
                            return Path(buf.value)
                    finally:
                        kernel32.CloseHandle(h)
                    return None
                if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                    break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        return None
    return None


def _common_install_roots() -> list[Path]:
    roots: list[Path] = []
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if not base:
            continue
        b = Path(base)
        roots.extend(
            [
                b / "Epic Games" / "rocketleague",
                b / "Steam" / "steamapps" / "common" / "rocketleague",
            ]
        )
    return roots


def resolve_default_stats_api_ini() -> Optional[PureWindowsPath]:
    """
    Chemin attendu de DefaultStatsAPI.ini.
    Priorité : jeu lancé → emplacements d'installation courants.
    """
    exe = rocket_league_exe_path()
    if exe and exe.is_file():
        return stats_api_ini_from_exe(exe)
    for root in _common_install_roots():
        ini = root / "TAGame" / "Config" / STATS_API_INI_NAME
        config_dir = ini.parent
        if ini.is_file() or config_dir.is_dir():
            return ini
        win64_exe = root / "TAGame" / "Binaries" / "Win64" / "RocketLeague.exe"
        if win64_exe.is_file():
            return stats_api_ini_from_exe(win64_exe)
    return None


def stats_api_config_dir(ini_path: Optional[Path]) -> Optional[Path]:
    if ini_path is None:
        return None
    return Path(ini_path).parent


def example_stats_api_ini(port: int = 49123, packet_send_rate: int = 2) -> str:
    return (
        "[StatsAPI]\n"
        f"PacketSendRate={packet_send_rate}\n"
        f"Port={int(port)}\n"
    )
