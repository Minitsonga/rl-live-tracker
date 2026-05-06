"""Détection fenêtre au premier plan : Rocket League (Windows)."""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def rocket_league_process_running() -> bool:
    """True si au moins un processus RocketLeague.exe tourne (Windows)."""
    if sys.platform != "win32":
        return True
    TH32CS_SNAPPROCESS = 0x2

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
            return True
        try:
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if not kernel32.Process32First(snap, ctypes.byref(pe)):
                return True
            while True:
                name = pe.szExeFile.decode("utf-8", errors="ignore").lower()
                if name == "rocketleague.exe":
                    return True
                if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                    break
        finally:
            kernel32.CloseHandle(snap)
        return False
    except Exception:
        return True


def is_hwnd_foreground(hwnd: int) -> bool:
    """True si hwnd est la fenêtre Windows active (GetForegroundWindow)."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        return int(ctypes.windll.user32.GetForegroundWindow()) == int(hwnd)
    except Exception:
        return False


def is_rocket_league_foreground() -> bool:
    """
    True si la fenêtre active appartient à RocketLeague.exe.
    Hors Windows ou en cas d'erreur API : True (ne pas masquer les overlays par erreur).
    """
    if sys.platform != "win32":
        return True
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return True
        try:
            buf = ctypes.create_unicode_buffer(4096)
            size = wintypes.DWORD(len(buf))
            ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            if not ok:
                return True
            path = buf.value.lower()
            return path.endswith("\\rocketleague.exe")
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return True
