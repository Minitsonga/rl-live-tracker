"""Répertoires runtime : data/, logs/."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_APP_NAME = "RLLiveTracker"


def app_root() -> Path:
    """Racine données utilisateur (dev : repo ; frozen : %LocalAppData%\\RLLiveTracker)."""
    if getattr(sys, "frozen", False):
        base = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        root = base / _APP_NAME
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(__file__).resolve().parents[2]


ROOT_DIR = app_root()
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"

for _d in (DATA_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA_DIR / "config.json"
MATCHES_PATH = DATA_DIR / "matches.jsonl"
MMR_CACHE_PATH = DATA_DIR / "mmr_cache.json"
MMR_HISTORY_PATH = DATA_DIR / "mmr_history.jsonl"

MMR_LOG_PATH = LOG_DIR / "mmr.log"
API_DUMP_PATH = LOG_DIR / "api_dump.log"
EVENT_LOG_PATH = LOG_DIR / "events.log"


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def safe_atomic_write_text(path: Path, text: str, tag: str) -> bool:
    try:
        atomic_write_text(path, text)
        return True
    except OSError as e:
        print(f"[{tag}] could not write {path.name}: {e}", file=sys.stderr)
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def load_jsonl(path: Path, tag: str) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        print(f"[{tag}] read failed: {e}", file=sys.stderr)
    return out
