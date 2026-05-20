"""Client TCP NDJSON Stats API Rocket League."""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .applog import api_dump, stats_log
from .constants import (
    EVT_GOAL_SCORED,
    EVT_MATCH_CREATED,
    EVT_MATCH_DESTROYED,
    EVT_MATCH_ENDED,
    EVT_MATCH_INITIALIZED,
    EVT_REPLAY_CREATED,
    EVT_ROUND_STARTED,
    EVT_UPDATE_STATE,
)
from .match_helpers import extract_winner_team_num_from_payload
from .storage import last_touch_player, player_key


SPECTATOR_FIELDS = ("Boost", "bBoosting", "bOnGround", "bOnWall", "bSupersonic")


class StatsClient(QObject):
    match_initialized = Signal(dict)
    match_ended = Signal(dict)
    match_destroyed = Signal()
    connection_status = Signal(bool)
    event_seen = Signal(str, dict)

    def __init__(self, host: str, port: int, api_dump_enabled: bool = False):
        super().__init__()
        self.host = host
        self.port = port
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="StatsClient")
        self._api_dump_enabled = bool(api_dump_enabled)
        self._paused = False
        self._started = False
        self._reset()

    def _reset(self):
        self._roster: dict[str, dict] = {}
        self._my_team: Optional[int] = None
        self._arena: str = ""
        self._match_guid: Optional[str] = None
        self._initialized_emitted = False
        self._last_emitted_roster_size = 0
        self._round_started = False
        self._spectator_warned = False
        self._score: list[int] = [0, 0]
        self._team_colors: dict[int, str] = {}
        self._match_ended_emitted = False
        self._in_replay = False
        self._update_state_count_this_match = 0
        self._last_game_block: Optional[dict] = None
        self._local_player_key: Optional[str] = None

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def stop(self) -> None:
        self._paused = False
        loop, task = self._loop, self._task
        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)
        if self._started:
            self._thread.join(timeout=3)
            self._started = False

    def pause(self) -> None:
        """Arrête les tentatives TCP (rare ; l'idle app repose surtout sur connection_status)."""
        if self._paused:
            return
        self._paused = True
        loop, task = self._loop, self._task
        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)
        self.connection_status.emit(False)

    def resume(self) -> None:
        if not self._paused:
            return
        self._paused = False
        # pause() cancels the asyncio task; the worker thread may have exited.
        if not self._thread.is_alive():
            self._started = False
            self._loop = None
            self._task = None
        self.start()

    def _run(self):
        try:
            asyncio.run(self._main())
        except Exception as e:
            stats_log(f"event loop crashed: {e}")

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.current_task()
        try:
            await self._connect_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self.connection_status.emit(False)

    async def _connect_loop(self):
        backoff = 1.0
        while True:
            while self._paused:
                await asyncio.sleep(0.5)
            try:
                stats_log(f"connecting tcp://{self.host}:{self.port}")
                await self._run_tcp()
                stats_log("disconnected; reconnecting")
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except OSError as e:
                self.connection_status.emit(False)
                stats_log(f"connect failed ({type(e).__name__}: {e}); retry in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _run_tcp(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        self.connection_status.emit(True)
        try:
            decoder = json.JSONDecoder()
            buf = ""
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    return
                buf += chunk.decode("utf-8", errors="replace")
                while True:
                    stripped = buf.lstrip()
                    if not stripped:
                        buf = ""
                        break
                    try:
                        obj, idx = decoder.raw_decode(stripped)
                    except json.JSONDecodeError:
                        buf = stripped
                        break
                    buf = stripped[idx:]
                    self._safe_handle(obj)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)

    def _safe_handle(self, msg) -> None:
        if not isinstance(msg, dict):
            return
        event = msg.get("Event", "?")
        if self._api_dump_enabled:
            should_dump = event != EVT_UPDATE_STATE
            if not should_dump and self._update_state_count_this_match < 3:
                should_dump = True
                self._update_state_count_this_match += 1
            if should_dump:
                raw_data = msg.get("Data")
                if isinstance(raw_data, str):
                    try:
                        decoded = json.loads(raw_data) if raw_data else {}
                    except json.JSONDecodeError:
                        decoded = raw_data
                else:
                    decoded = raw_data if raw_data is not None else {}
                api_dump(event, decoded if isinstance(decoded, dict) else {})
        try:
            self._handle(msg)
        except Exception as e:
            import traceback
            stats_log(f"handler error on {event}: {type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stderr)

    def _handle(self, msg: dict):
        event = msg.get("Event")
        data = msg.get("Data")
        if isinstance(data, str):
            try:
                data = json.loads(data) if data else {}
            except json.JSONDecodeError:
                data = {}
        if not isinstance(data, dict):
            data = {}
        if event == EVT_GOAL_SCORED:
            if self._classify_goal_scored(data):
                self.event_seen.emit(event, data)
        elif event:
            self.event_seen.emit(event, data)
        if event == EVT_UPDATE_STATE:
            self._on_update_state(data)
        elif event == EVT_MATCH_CREATED:
            self._reset()
            self._match_guid = data.get("MatchGuid")
        elif event == EVT_MATCH_INITIALIZED:
            self._maybe_emit_initialized()
        elif event == EVT_ROUND_STARTED:
            self._maybe_emit_initialized()
            if self._initialized_emitted and len(self._roster) > self._last_emitted_roster_size:
                self._emit_match_initialized()
            self._round_started = True
        elif event == EVT_MATCH_ENDED:
            self._on_match_ended(data)
        elif event == EVT_MATCH_DESTROYED:
            self.match_destroyed.emit()
            self._reset()
        elif event == EVT_REPLAY_CREATED:
            self._in_replay = True

    def _on_update_state(self, data: dict):
        if not isinstance(data, dict) or self._in_replay:
            return
        game = data.get("Game")
        if isinstance(game, dict):
            self._last_game_block = dict(game)
            arena = game.get("Arena")
            if isinstance(arena, str) and arena and arena != self._arena:
                self._arena = arena
            teams = game.get("Teams")
            if isinstance(teams, list):
                for t in teams:
                    if not isinstance(t, dict):
                        continue
                    tn = t.get("TeamNum")
                    if tn not in (0, 1):
                        continue
                    sc = t.get("Score")
                    if isinstance(sc, int):
                        self._score[int(tn)] = sc
                    if len(self._team_colors) < 2:
                        cp = t.get("ColorPrimary")
                        if (int(tn) not in self._team_colors and isinstance(cp, str)
                                and len(cp) == 6):
                            self._team_colors[int(tn)] = "#" + cp.upper()
        if self._round_started:
            return
        players = data.get("Players")
        if not isinstance(players, list):
            return
        spectator_team_hits: set[int] = set()
        for p in players:
            if not isinstance(p, dict):
                continue
            pid = p.get("PrimaryId")
            team = p.get("TeamNum")
            if not isinstance(pid, str) or team not in (0, 1):
                continue
            key = player_key(pid)
            name_raw = p.get("Name")
            name = name_raw if isinstance(name_raw, str) else "?"
            self._roster[key] = {
                "key": key,
                "primaryId": pid,
                "name": name,
                "team": int(team),
            }
            if self._local_player_key is None and any(
                p.get(flag) for flag in ("bLocalPlayer", "bIsLocal", "IsLocal", "bLocallyControlled")
            ):
                self._local_player_key = key
            if any(k in p for k in SPECTATOR_FIELDS):
                spectator_team_hits.add(int(team))
        if self._my_team is None and len(spectator_team_hits) == 1:
            (self._my_team,) = spectator_team_hits
        elif self._my_team is None and len(spectator_team_hits) > 1 and not self._spectator_warned:
            self._spectator_warned = True
            stats_log(f"spectator mode? both teams report spectator fields: {spectator_team_hits}")
        if not self._initialized_emitted:
            self._maybe_emit_initialized()
        elif len(self._roster) > self._last_emitted_roster_size:
            self._emit_match_initialized()

    def _on_match_ended(self, data: dict):
        # Ne pas ignorer sous replay : REPLAY_CREATED peut être reçu avant MatchEnded
        # (forfait / quit replay) et bloquait alors le décompte W/L.
        if self._match_ended_emitted:
            return
        winner = data.get("WinnerTeamNum") if isinstance(data, dict) else None
        if winner is None:
            merged: dict = {}
            if isinstance(data, dict):
                merged.update(data)
            if self._last_game_block:
                merged.setdefault("Game", self._last_game_block)
            winner = extract_winner_team_num_from_payload(merged)
        if winner is None or self._my_team is None or not self._roster:
            return
        self._match_ended_emitted = True
        self.match_ended.emit({
            "winner": int(winner),
            "myTeam": self._my_team,
            "arena": self._arena,
            "matchGuid": self._match_guid,
            "players": list(self._roster.values()),
            "score": list(self._score),
            "teamColors": dict(self._team_colors),
        })

    def _classify_goal_scored(self, data: dict) -> bool:
        scorer = data.get("Scorer")
        if not isinstance(scorer, dict):
            return False
        scorer_name = scorer.get("Name")
        if not scorer_name:
            return False
        scorer_team = scorer.get("TeamNum")
        _, last_team = last_touch_player(data)
        data["bOwnGoal"] = (
            scorer_team in (0, 1)
            and last_team in (0, 1)
            and scorer_team != last_team
        )
        return True

    def _maybe_emit_initialized(self):
        if (self._initialized_emitted or self._in_replay
                or self._my_team is None or not self._roster):
            return
        teams = {p["team"] for p in self._roster.values()}
        if len(teams) < 2:
            return
        self._initialized_emitted = True
        self._emit_match_initialized()

    def _emit_match_initialized(self):
        self._last_emitted_roster_size = len(self._roster)
        self.match_initialized.emit({
            "teamColors": dict(self._team_colors),
            "arena": self._arena,
            "myTeam": self._my_team,
            "players": list(self._roster.values()),
            "localPlayerKey": self._local_player_key,
        })
