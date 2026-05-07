"""État session : W/L et streaks par playlist, MMR courant, deltas par mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Keep SessionState testable without Qt runtime:
# importing mmr pulls PySide6, which is not needed for pure logic tests.
try:
    from .mmr import RANKED_PLAYLISTS
except ModuleNotFoundError:
    RANKED_PLAYLISTS = ("1v1", "2v2", "3v3")
from .storage import playlist_from_player_count


def mmr_for_playlist(entry: Optional[dict], playlist: str) -> Optional[int]:
    if not entry or entry.get("not_found"):
        return None
    pls = entry.get("playlists") or {}
    row = pls.get(playlist)
    if isinstance(row, dict) and row.get("mmr") is not None:
        return int(row["mmr"])
    return None


@dataclass
class PlaylistSession:
    wins: int = 0
    losses: int = 0
    win_streak: int = 0
    loss_streak: int = 0
    last_match_delta: Optional[int] = None
    mmr_delta_session: int = 0


class SessionState:
    def __init__(self) -> None:
        self.self_name: Optional[str] = None
        self.active_playlist: str = "other"
        self._by_pl: dict[str, PlaylistSession] = {}
        self._mmr_at_match_start: Optional[int] = None
        self._mmr_baseline_reliable: bool = False
        self.current_mmr: Optional[int] = None
        # Dernier delta TRN appliqué (carte session), indépendant du mode affiché / lobby suivant.
        self.last_completed_mmr_delta: Optional[int] = None
        # Premier MMR TRN vu par playlist pour cette session (réconciliation cumul si post-match échoue).
        self.mmr_session_start: dict[str, int] = {}
        self.stats_connected: bool = False

    def _pl(self, key: str) -> PlaylistSession:
        if key not in self._by_pl:
            self._by_pl[key] = PlaylistSession()
        return self._by_pl[key]

    @property
    def wins(self) -> int:
        return self._pl(self.active_playlist).wins

    @property
    def losses(self) -> int:
        return self._pl(self.active_playlist).losses

    @property
    def win_streak(self) -> int:
        return self._pl(self.active_playlist).win_streak

    @property
    def loss_streak(self) -> int:
        return self._pl(self.active_playlist).loss_streak

    @property
    def last_match_delta(self) -> Optional[int]:
        return self.last_completed_mmr_delta

    def session_delta_by_playlist(self) -> dict[str, int]:
        """Compat logs : cumul MMR session par playlist."""
        return {k: v.mmr_delta_session for k, v in self._by_pl.items() if v.mmr_delta_session != 0}

    def reset_counters(self) -> None:
        self._by_pl.clear()
        self._mmr_at_match_start = None
        self._mmr_baseline_reliable = False
        self.current_mmr = None
        self.last_completed_mmr_delta = None
        self.mmr_session_start.clear()

    def record_session_start_mmr_if_needed(
        self, playlist: str, mmr: Optional[int]
    ) -> None:
        """Mémorise le MMR TRN initial par mode (première partie de la session sur ce mode)."""
        if playlist not in RANKED_PLAYLISTS or mmr is None:
            return
        if playlist not in self.mmr_session_start:
            self.mmr_session_start[playlist] = int(mmr)

    def reconcile_mmr_delta_from_session_start(
        self,
        self_entry: Optional[dict],
        playlist: str,
    ) -> bool:
        """Si TRN a bougé depuis le début de session sur ce mode, aligne le cumul sur (MMR actuel − départ).

        Ne remplace pas le cumul incrémental si le MMR TRN est encore égal au départ (API en retard) :
        dans ce cas on garde les deltas déjà appliqués."""
        if playlist not in RANKED_PLAYLISTS:
            return False
        if not self_entry or self_entry.get("not_found"):
            return False
        start = self.mmr_session_start.get(playlist)
        if start is None:
            return False
        now = mmr_for_playlist(self_entry, playlist)
        if now is None:
            return False
        now_i, start_i = int(now), int(start)
        if now_i == start_i:
            return False
        st = self._pl(playlist)
        inferred = now_i - start_i
        st.mmr_delta_session = inferred
        if playlist == self.active_playlist:
            self.current_mmr = now_i
        return True

    def on_match_initialized(self, roster: list[dict], self_entry: Optional[dict]) -> None:
        n = len(roster)
        self.active_playlist = playlist_from_player_count(n)
        self._mmr_at_match_start = None
        self._mmr_baseline_reliable = False
        if self.active_playlist in RANKED_PLAYLISTS:
            m = mmr_for_playlist(self_entry, self.active_playlist)
            if m is not None:
                self._mmr_at_match_start = m
                self._mmr_baseline_reliable = True
                self.current_mmr = m
                self.record_session_start_mmr_if_needed(self.active_playlist, m)

    def ensure_baseline_for_playlist(self, playlist: str, self_entry: Optional[dict]) -> None:
        if playlist not in RANKED_PLAYLISTS:
            return
        if self._mmr_at_match_start is not None:
            return
        m = mmr_for_playlist(self_entry, playlist)
        if m is not None:
            self._mmr_at_match_start = m
            self._mmr_baseline_reliable = True
            self.current_mmr = m
            self.record_session_start_mmr_if_needed(playlist, m)

    def freeze_baseline_at_match_end(
        self, playlist: str, self_entry: Optional[dict]
    ) -> tuple[Optional[int], bool]:
        if playlist not in RANKED_PLAYLISTS:
            return None, False
        reliable = self._mmr_baseline_reliable
        if self._mmr_at_match_start is None:
            m = mmr_for_playlist(self_entry, playlist)
            if m is not None:
                self._mmr_at_match_start = m
                reliable = False
        return self._mmr_at_match_start, reliable

    def on_match_ended_outcome(self, won: bool) -> None:
        st = self._pl(self.active_playlist)
        if won:
            st.wins += 1
            st.win_streak += 1
            st.loss_streak = 0
        else:
            st.losses += 1
            st.loss_streak += 1
            st.win_streak = 0

    def apply_post_match_trn(
        self,
        self_entry: Optional[dict],
        playlist: str,
        frozen_match_start_mmr: Optional[int],
        baseline_reliable: bool = True,
    ) -> Optional[int]:
        """Applique le delta MMR. `frozen_match_start_mmr` est capturé à la fin du match
        (voir post_pending baseline_mmr) — ne jamais relire _mmr_at_match_start ici (courses async)."""
        st = self._pl(playlist)
        new_mmr = mmr_for_playlist(self_entry, playlist)
        old = frozen_match_start_mmr

        if old is not None and new_mmr is not None and playlist in RANKED_PLAYLISTS:
            d = int(new_mmr) - int(old)
            st.last_match_delta = d
            st.mmr_delta_session += d
            # If start baseline was reconstructed at match end (missing match init/load),
            # d can include multiple matches; keep it for session total, but don't show it as "Last".
            self.last_completed_mmr_delta = d if baseline_reliable else None
            self.current_mmr = int(new_mmr)
            return d
        if new_mmr is not None and self.active_playlist == playlist:
            self.current_mmr = int(new_mmr)
        return None

    def session_delta_display(self, playlist: str) -> Optional[int]:
        if playlist not in RANKED_PLAYLISTS:
            return None
        return self._pl(playlist).mmr_delta_session
