"""Clés joueurs et playlist dérivée du nombre de joueurs."""
from __future__ import annotations

import json
from typing import Optional

from .paths import MATCHES_PATH


def player_key(primary_id: str) -> str:
    parts = primary_id.split("|")
    return f"{parts[0]}|{parts[1]}" if len(parts) >= 2 else primary_id


_PLAYLIST_BY_PLAYER_COUNT = {2: "1v1", 4: "2v2", 6: "3v3"}


def playlist_from_player_count(n: int) -> str:
    return _PLAYLIST_BY_PLAYER_COUNT.get(n, "other")


def match_playlist(record: dict) -> str:
    pl = record.get("playlist")
    if isinstance(pl, str) and pl:
        return pl
    players = record.get("players") or []
    return playlist_from_player_count(len(players))


def append_match(record: dict) -> None:
    try:
        with MATCHES_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def last_touch_player(data: dict) -> tuple[Optional[str], Optional[int]]:
    last_touch = data.get("BallLastTouch")
    if not isinstance(last_touch, dict):
        return (None, None)
    player = last_touch.get("Player")
    if not isinstance(player, dict):
        return (None, None)
    name = player.get("Name")
    team = player.get("TeamNum")
    return (
        name if isinstance(name, str) else None,
        team if isinstance(team, int) and team in (0, 1) else None,
    )
