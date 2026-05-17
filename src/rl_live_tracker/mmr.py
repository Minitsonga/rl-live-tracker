"""MMR via tracker.network (sans clé API) — curl_cffi + cache disque."""
from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from .applog import mmr_log, warn_log
from .paths import (
    MMR_CACHE_PATH,
    MMR_HISTORY_PATH,
    load_jsonl,
    now_iso,
    safe_atomic_write_text,
)
from .storage import player_key


MMR_PLATFORM_TO_TRN = {
    "Epic": "epic",
    "Steam": "steam",
    "PS4": "psn",
    "XboxOne": "xbl",
    "Switch": "switch",
}

MMR_PLAYLIST_IDS = {
    10: "1v1",
    11: "2v2",
    13: "3v3",
}
MMR_CATEGORIES = ("best", "1v1", "2v2", "3v3")
RANKED_PLAYLISTS = ("1v1", "2v2", "3v3")

MMR_RANK_ZONES = [
    (0, 195, "Bronze", "#B87333"),
    (195, 395, "Silver", "#C0C5CD"),
    (395, 595, "Gold", "#F0C674"),
    (595, 795, "Platinum", "#6FC8D6"),
    (795, 995, "Diamond", "#7FA9F2"),
    (995, 1195, "Champion", "#B59CEE"),
    (1195, 1565, "Grand Champion", "#EC4F50"),
    (1565, 2500, "Supersonic Legend", "#DB2C70"),
]

MMR_TIER_COLORS = {"Unranked": "#8E9379", **{name: color for _lo, _hi, name, color in MMR_RANK_ZONES}}

MMR_TTL_SECONDS = 600
MMR_FETCH_INTERVAL = 0.5


def mmr_lookup_handle(primary_id: str, name: str) -> Optional[tuple[str, str]]:
    parts = primary_id.split("|")
    if not parts:
        return None
    plat = MMR_PLATFORM_TO_TRN.get(parts[0])
    if not plat:
        return None
    if plat == "steam" and len(parts) >= 2 and parts[1]:
        return (plat, parts[1])
    if not name:
        return None
    return (plat, name)


def tier_color(tier: Optional[str]) -> str:
    if not tier:
        return MMR_TIER_COLORS["Unranked"]
    for prefix, color in MMR_TIER_COLORS.items():
        if tier.startswith(prefix):
            return color
    return "#E0E3E5"


def parse_trn_payload(data: dict) -> dict:
    info = (data or {}).get("platformInfo") or {}
    meta = (data or {}).get("metadata") or {}
    last_updated = (meta.get("lastUpdated") or {}).get("value")

    playlists: dict[str, dict] = {}
    for seg in (data or {}).get("segments") or []:
        if seg.get("type") != "playlist":
            continue
        attrs = seg.get("attributes") or {}
        pid = attrs.get("playlistId")
        label = MMR_PLAYLIST_IDS.get(pid)
        if not label:
            continue
        stats = seg.get("stats") or {}
        rating = (stats.get("rating") or {}).get("value")
        tier = ((stats.get("tier") or {}).get("metadata") or {}).get("name")
        div = ((stats.get("division") or {}).get("metadata") or {}).get("name")
        if rating is None:
            continue
        playlists[label] = {
            "mmr": int(rating),
            "tier": tier or "Unranked",
            "division": div or "",
        }

    best = None
    for label, p in playlists.items():
        if best is None or p["mmr"] > best["mmr"]:
            best = {**p, "playlist": label}

    return {
        "fetched_at": now_iso(),
        "lastUpdated": last_updated,
        "handle": info.get("platformUserHandle"),
        "playlists": playlists,
        "best": best,
    }


def load_mmr_cache() -> dict:
    if not MMR_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(MMR_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        warn_log(f"MMR cache unreadable, starting fresh: {e}")
        return {}


def save_mmr_cache(cache: dict) -> None:
    safe_atomic_write_text(MMR_CACHE_PATH, json.dumps(cache, indent=2, sort_keys=True), "mmr")


def append_mmr_history(entry: dict) -> None:
    try:
        with MMR_HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        warn_log(f"MMR history: write failed ({e})")


def load_mmr_history() -> list[dict]:
    return load_jsonl(MMR_HISTORY_PATH, "mmr-history")


class MMRClient(QObject):
    updated = Signal(str)

    _BASE_URL = "https://api.tracker.gg/api/v2/rocket-league/standard/profile/{plat}/{ident}"
    _HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://rocketleague.tracker.network",
        "Referer": "https://rocketleague.tracker.network/",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, enabled: bool = True, ttl_seconds: int = MMR_TTL_SECONDS):
        super().__init__()
        self._enabled = bool(enabled)
        self._ttl = max(60, int(ttl_seconds))
        self._cache: dict = load_mmr_cache()
        steam_nf = [k for k, v in self._cache.items()
                      if isinstance(v, dict) and v.get("not_found") and k.startswith("Steam|")]
        if steam_nf:
            for k in steam_nf:
                del self._cache[k]
            save_mmr_cache(self._cache)
            mmr_log(f"purged {len(steam_nf)} stale Steam not_found entries")
        self._cache_lock = threading.Lock()
        self._queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
        self._inflight: set[str] = set()
        self._stop = threading.Event()
        self._started = False
        self._thread = threading.Thread(target=self._worker, daemon=True, name="MMRFetcher")
        self._curl_requests: Any = None
        try:
            from curl_cffi import requests as _curl_requests  # noqa: PLC0415

            self._curl_requests = _curl_requests
            mmr_log(
                f"init enabled={self._enabled} ttl={self._ttl}s "
                f"cache_entries={len(self._cache)} curl_cffi=ok"
            )
        except ImportError as e:
            warn_log(f"curl_cffi missing ({e}) — MMR requests will fail (tracker.gg blocks urllib)")
            mmr_log(
                f"init enabled={self._enabled} ttl={self._ttl}s "
                f"cache_entries={len(self._cache)} curl_cffi=MISSING"
            )

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()
            mmr_log("worker thread started")

    def stop(self) -> None:
        self._stop.set()

    def set_enabled(self, on: bool) -> None:
        prev = self._enabled
        self._enabled = bool(on)
        if prev != self._enabled:
            mmr_log(f"set_enabled {prev} -> {self._enabled}")

    def is_enabled(self) -> bool:
        return self._enabled and self._curl_requests is not None

    def get(self, key: str) -> Optional[dict]:
        with self._cache_lock:
            entry = self._cache.get(key)
            return dict(entry) if entry else None

    def _is_stale(self, entry: Optional[dict]) -> bool:
        if not entry:
            return True
        ts = entry.get("fetched_at")
        if not isinstance(ts, str):
            return True
        try:
            t = datetime.fromisoformat(ts)
        except ValueError:
            return True
        age = (datetime.now(timezone.utc) - t).total_seconds()
        return age >= self._ttl

    def enqueue(self, primary_id: str, name: str, force: bool = False) -> None:
        key = player_key(primary_id)
        if not self._enabled:
            mmr_log(f"enqueue skip {key!r}: disabled")
            return
        if self._curl_requests is None:
            mmr_log(f"enqueue skip {key!r}: curl_cffi missing")
            return
        if key in self._inflight:
            mmr_log(f"enqueue skip {key!r}: in-flight")
            return
        if not force:
            with self._cache_lock:
                entry = self._cache.get(key)
            if not self._is_stale(entry):
                mmr_log(f"enqueue skip {key!r}: cache fresh")
                return
        handle = mmr_lookup_handle(primary_id, name)
        if handle is None:
            mmr_log(f"enqueue skip {key!r}: unsupported platform or missing name")
            return
        plat, ident = handle
        self._inflight.add(key)
        self._queue.put((key, plat, ident))
        mmr_log(f"enqueue{' [forced]' if force else ''} {key!r} -> {plat}/{ident!r}")

    def enqueue_roster(self, roster: list[dict]) -> None:
        mmr_log(f"enqueue_roster: {len(roster)} player(s)")
        for p in roster:
            pid = p.get("primaryId") or p.get("key")
            if not pid:
                continue
            self.enqueue(pid, p.get("name") or "")

    def _worker(self) -> None:
        last_request = 0.0
        while not self._stop.is_set():
            try:
                key, plat, ident = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            since = time.monotonic() - last_request
            if since < MMR_FETCH_INTERVAL:
                wait = MMR_FETCH_INTERVAL - since
                self._stop.wait(wait)
                if self._stop.is_set():
                    break
            try:
                self._fetch_one(key, plat, ident)
            except Exception as e:
                mmr_log(f"{key!r} fetch FAILED: {type(e).__name__}: {e}")
            finally:
                self._inflight.discard(key)
            last_request = time.monotonic()

    def _http_get(self, url: str) -> tuple[int, bytes]:
        if self._curl_requests is not None:
            r = self._curl_requests.get(
                url,
                headers=self._HEADERS,
                impersonate="chrome120",
                timeout=15,
            )
            return int(r.status_code), bytes(r.content)

        headers = dict(self._HEADERS)
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return int(resp.getcode()), resp.read()
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            return int(e.code), body

    def _fetch_one(self, key: str, plat: str, ident: str) -> None:
        if self._curl_requests is None:
            return
        url = self._BASE_URL.format(plat=plat, ident=ident)
        mmr_log(f"GET {url}")
        t0 = time.monotonic()
        status, raw = self._http_get(url)
        dt = (time.monotonic() - t0) * 1000
        mmr_log(f"  -> HTTP {status} in {dt:.0f}ms")
        if status == 404:
            with self._cache_lock:
                self._cache[key] = {
                    "fetched_at": now_iso(),
                    "not_found": True,
                    "handle": ident,
                }
                save_mmr_cache(self._cache)
            self.updated.emit(key)
            return
        if status != 200:
            mmr_log(f"  {key!r} HTTP {status}")
            if status == 403:
                warn_log("tracker.gg returned 403 — install curl_cffi (pip install curl_cffi)")
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            mmr_log(f"  {key!r} bad JSON: {e}")
            return
        data = (payload or {}).get("data")
        if not isinstance(data, dict):
            mmr_log(f"  {key!r} no .data")
            return
        entry = parse_trn_payload(data)
        with self._cache_lock:
            self._cache[key] = entry
            save_mmr_cache(self._cache)
        mmr_log(f"  {key!r} OK best={entry.get('best')}")
        self.updated.emit(key)
