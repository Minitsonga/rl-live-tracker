"""Règles de comptage W/L session (Stats API)."""
from __future__ import annotations


def should_count_match_outcome(*, match_ended_recorded: bool) -> bool:
    """True seulement si MatchEnded a été traité (fin officielle)."""
    return match_ended_recorded
