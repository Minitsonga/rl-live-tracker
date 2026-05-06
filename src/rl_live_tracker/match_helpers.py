"""Extraction gagnant fin de match si WinnerTeamNum manquant (doc Psyonix : Game.Winner + Teams)."""
from __future__ import annotations


def _coerce_int_team(val) -> int | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _extract_winner_team_num(data: dict, depth: int = 0) -> int | None:
    if depth > 6 or not isinstance(data, dict):
        return None
    keys = (
        "WinnerTeamNum", "winnerTeamNum", "WinningTeamNum", "winningTeamNum",
        "Winner", "WinningTeam", "winner_team", "WinningTeamIndex", "WinningTeamNumber",
    )
    for k in keys:
        t = _coerce_int_team(data.get(k))
        if t is not None:
            return t
    for sub in ("Match", "Game", "Stats", "Results", "Data"):
        subd = data.get(sub)
        if isinstance(subd, dict) and subd is not data:
            t = _extract_winner_team_num(subd, depth + 1)
            if t is not None:
                return t
    return None


def _winner_team_num_from_named_winner(game: dict) -> int | None:
    if not isinstance(game, dict):
        return None
    raw = game.get("Winner")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return _coerce_int_team(raw)
    if not isinstance(raw, str) or not raw.strip():
        return None
    wnorm = raw.strip().lower()
    teams = game.get("Teams")
    if isinstance(teams, list):
        for t in teams:
            if not isinstance(t, dict):
                continue
            name = (t.get("Name") or "").strip().lower()
            if name == wnorm:
                return _coerce_int_team(t.get("TeamNum"))
        for t in teams:
            if not isinstance(t, dict):
                continue
            name = (t.get("Name") or "").strip().lower()
            if name and (wnorm in name or name in wnorm):
                return _coerce_int_team(t.get("TeamNum"))
    blue_tokens = frozenset({"blue", "bleu", "bleue", "bleus", "azul", "blau"})
    orange_tokens = frozenset({"orange", "oranges", "naranja"})
    parts = {_p for _p in wnorm.replace(",", " ").split() if _p}
    if wnorm in blue_tokens or parts & blue_tokens:
        return 0
    if wnorm in orange_tokens or parts & orange_tokens:
        return 1
    return None


def extract_winner_team_num_from_payload(data: dict) -> int | None:
    if not isinstance(data, dict):
        return None
    n = _extract_winner_team_num(data)
    if n is not None:
        return n
    game = data.get("Game")
    if isinstance(game, dict):
        n = _extract_winner_team_num(game)
        if n is not None:
            return n
        n = _winner_team_num_from_named_winner(game)
        if n is not None:
            return n
    return None
