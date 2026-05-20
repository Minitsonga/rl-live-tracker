"""Règles de comptage W/L session (Stats API)."""
from __future__ import annotations


def should_ignore_late_match_ended(*, match_outcome_recorded: bool) -> bool:
    """True si MatchEnded doit être ignoré (défaite déjà comptée sur destroy)."""
    return match_outcome_recorded
