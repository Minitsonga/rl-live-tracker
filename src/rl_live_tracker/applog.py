"""Logs fichier + console — style lisible, sans toucher au spam TCP [stats]."""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from .paths import API_DUMP_PATH, EVENT_LOG_PATH, MMR_LOG_PATH, now_iso

MMR_LOG_CAP = 256 * 1024
API_DUMP_CAP_BYTES = 2 * 1024 * 1024
EVENT_LOG_CAP = 384 * 1024

_mmr_log_lock = threading.Lock()
_api_dump_lock = threading.Lock()
_event_log_lock = threading.Lock()

_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
# Thème lisible sur fond sombre / clair (ANSI 16 couleurs)
_C = {
    "match": "\033[96m",   # cyan clair
    "session": "\033[92m", # vert
    "mmr": "\033[95m",     # magenta
    "app": "\033[94m",     # bleu
    "warn": "\033[93m",    # jaune
}

_TAG_WIDTH = 8


def _stderr() -> object | None:
    """PyInstaller windowed (console=False) : sys.stderr peut être None."""
    return sys.stderr


def _stderr_color_ok() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    err = _stderr()
    if err is None:
        return False
    try:
        if not err.isatty():  # type: ignore[union-attr]
            return False
    except (AttributeError, OSError):
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            h = kernel32.GetStdHandle(-12)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:
            pass
    return True


_USE_COLOR = _stderr_color_ok()


def _ts_console() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _ts_file() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _print_tagged(tag: str, message: str, *, dim: bool = False) -> None:
    err = _stderr()
    if err is None:
        return
    tag = tag[:_TAG_WIDTH]
    try:
        if _USE_COLOR:
            col = _C.get(tag.strip(), "\033[97m")
            ts = f"{_DIM}{_ts_console()}{_RESET}"
            tag_pad = f"{_BOLD}{col}{tag:>{_TAG_WIDTH}}{_RESET}"
            body = f"{_DIM}{message}{_RESET}" if dim else message
            print(f"{ts}  {tag_pad}  {body}", file=err, flush=True)
        else:
            print(f"{_ts_console()}  [{tag:>{_TAG_WIDTH}}]  {message}", file=err, flush=True)
    except OSError:
        pass


def _append_capped(path: Path, line: str, cap_bytes: int, lock: threading.Lock) -> None:
    try:
        with lock:
            try:
                if path.stat().st_size > cap_bytes:
                    path.write_text("", encoding="utf-8")
            except FileNotFoundError:
                pass
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


def event_log(message: str, *, tag: str = "match") -> None:
    """Événements « historique » (match, session, …) — joli stderr + events.log."""
    line = f"[{_ts_file()}] [{tag}] {message}"
    _print_tagged(tag, message)
    _append_capped(EVENT_LOG_PATH, line, EVENT_LOG_CAP, _event_log_lock)


def mmr_log(message: str) -> None:
    line = f"[{_ts_file()}] {message}"
    _print_tagged("mmr", message)
    _append_capped(MMR_LOG_PATH, line, MMR_LOG_CAP, _mmr_log_lock)


def stats_log(message: str) -> None:
    """Client TCP Stats API — format simple, sans mise en forme (reconnexions, etc.)."""
    err = _stderr()
    if err is None:
        return
    try:
        print(f"[stats] {message}", file=err, flush=True)
    except OSError:
        pass


def api_dump(event: str, data: dict) -> None:
    try:
        line = json.dumps({"ts": now_iso(), "Event": event, "Data": data})
    except (TypeError, ValueError):
        return
    _append_capped(API_DUMP_PATH, line, API_DUMP_CAP_BYTES, _api_dump_lock)


def app_log(message: str, *, dim: bool = False) -> None:
    """Messages applicatifs (démarrage, singleton, etc.). Sur stderr uniquement."""
    _print_tagged("app", message, dim=dim)


def warn_log(message: str) -> None:
    """Avertissements (hotkeys, config, overlay)."""
    _print_tagged("warn", message)
