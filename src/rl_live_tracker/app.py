"""Point d'entrée Qt : Stats API + MMR + deux overlays + tray."""
from __future__ import annotations

import os
import subprocess
import re
import sys
import threading
from typing import Any, Callable, Optional

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from .config import apply_theme_preset, load_config, save_config
from .focus_rl import (
    is_hwnd_foreground,
    is_rocket_league_foreground,
    rocket_league_process_running,
)
from .mmr import MMRClient, RANKED_PLAYLISTS
from .paths import DATA_DIR, now_iso
from .render_roster import (
    render_roster_html,
    render_roster_preview_html,
    roster_overlay_empty_html,
)
from .render_session import render_session_html
from .menu_overlay import MenuPanel
from .overlay_widgets import TransparentOverlay
from .session_state import SessionState, mmr_for_playlist
from .stats_client import StatsClient
from .storage import append_match
from .applog import app_log, event_log, mmr_log, warn_log


def _arena_readable(arena: str, max_len: int = 42) -> str:
    s = (arena or "").replace("_", " ").strip() or "?"
    return s if len(s) <= max_len else f"{s[: max_len - 1]}…"


def _trn_last_updated_is_newer(cur_lu: Any, baseline_lu: Any) -> bool:
    """Compare TRN metadata.lastUpdated (ISO, epoch s/ms, ou ordre lexicographique)."""
    if cur_lu is None or baseline_lu is None:
        return False
    if cur_lu == baseline_lu:
        return False
    from datetime import datetime, timezone

    def as_epoch(x: Any) -> Optional[float]:
        if isinstance(x, (int, float)):
            v = float(x)
            return v / 1000.0 if v > 1e12 else v
        s = str(x).strip()
        if s.isdigit():
            v = float(s)
            return v / 1000.0 if v > 1e12 else v
        return None

    ca, ba = as_epoch(cur_lu), as_epoch(baseline_lu)
    if ca is not None and ba is not None:
        return ca > ba
    sa, sb = str(cur_lu).strip(), str(baseline_lu).strip()
    try:
        da = datetime.fromisoformat(sa.replace("Z", "+00:00"))
        db = datetime.fromisoformat(sb.replace("Z", "+00:00"))
        if da.tzinfo is None:
            da = da.replace(tzinfo=timezone.utc)
        if db.tzinfo is None:
            db = db.replace(tzinfo=timezone.utc)
        return da > db
    except ValueError:
        return sa > sb


def _make_tray_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setBrush(QColor(0, 200, 255))
    p.setPen(QColor(0, 140, 180))
    p.drawRoundedRect(8, 8, 48, 48, 10, 10)
    p.end()
    return QIcon(pix)


def _hotkey_to_pynput(spec: str) -> str:
    s = spec.strip().lower()
    if re.match(r"^f\d+$", s):
        return f"<{s}>"
    parts = [p.strip() for p in s.replace("_", "+").split("+")]
    return "+".join(f"<{p}>" if len(p) > 1 else p for p in parts)


def _start_hotkeys_merged(mapping: dict[str, Callable[[], None]]) -> None:
    try:
        from pynput import keyboard
    except ImportError:
        warn_log("pynput missing — pip install pynput (F5 hotkeys disabled)")
        return
    if not mapping:
        return

    def runner():
        try:
            with keyboard.GlobalHotKeys(mapping) as gl:
                gl.join()
        except Exception as e:
            warn_log(f"keyboard listener stopped: {e}")

    threading.Thread(target=runner, daemon=True, name="Hotkeys").start()


class AppController(QObject):
    refresh_requested = Signal()
    # Émis depuis le thread pynput : le slot s'exécute sur le thread Qt (GUI).
    menu_toggle_requested = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.session = SessionState()
        self.state: dict[str, Any] = {
            "roster": [],
            "in_match": False,
        }
        # True après MatchEnded traité ; si MatchDestroyed sans fin, on compte une défaite (quit / replay).
        self._match_outcome_recorded = True
        self.post_pending = {
            "active": False,
            "baseline_lu": "",
            "playlist": "",
            "baseline_mmr": None,  # int figé fin de match pour fallback si lastUpdated TRN ne bouge pas
            "baseline_reliable": False,  # True si baseline capturée au chargement du match
        }
        self.poll_token = 0
        self._last_lobby_sig: Any = None
        self._lobby_preview_enabled = False

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.overlay_session = TransparentOverlay(
            self.cfg,
            "width_session",
            "position_session",
            word_wrap=False,
        )
        self.overlay_roster = TransparentOverlay(
            self.cfg,
            "width_roster",
            "position_roster",
        )
        self.overlay_session.positionCommitted.connect(lambda: self._on_overlay_position_committed("session"))
        self.overlay_roster.positionCommitted.connect(lambda: self._on_overlay_position_committed("roster"))

        self._menu = MenuPanel(self.cfg)
        self._wire_menu_signals()

        self.mmr_client = MMRClient(enabled=bool(self.cfg.get("mmr_enabled", True)))
        self.mmr_client.start()

        self.stats = StatsClient(
            self.cfg["host"],
            int(self.cfg["port"]),
            api_dump_enabled=bool(self.cfg.get("api_debug_dump")),
        )

        self._wire_signals()
        self._seed_mmr_from_cache()

        vis_s = bool(
            self.cfg.get(
                "show_session_overlay",
                self.cfg.get("overlays_visible_default", True),
            )
        )
        vis_r = bool(
            self.cfg.get(
                "show_roster_overlay",
                self.cfg.get("roster_visible_default", False),
            )
        )
        self._visibility = {"session": vis_s, "roster": vis_r}
        self._drag_mode = False
        self._tray: Optional[QSystemTrayIcon] = None
        self._rl_was_running = (
            rocket_league_process_running() if sys.platform == "win32" else True
        )
        self._rl_process_poll_i = 0
        self._rl_process_poll_every = 4  # 4 × 450 ms ≈ 1.8 s

        self.refresh_requested.connect(self._do_refresh)
        self.menu_toggle_requested.connect(self._toggle_menu)
        self.mmr_client.updated.connect(self._on_mmr_updated)
        self.stats.connection_status.connect(self._on_stats_conn)

        self.stats.start()
        self._setup_tray()
        self._setup_hotkeys()
        self._do_refresh()
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(450)
        self._focus_timer.timeout.connect(self._on_focus_tick)
        self._focus_timer.start()
        app_log("Ready — F5 hotkey · tray icon by the clock")

    def _user_focus_in_settings_panel(self) -> bool:
        """True si l'utilisateur interagit encore avec le menu (sinon ex. Alt+Tab vers une autre app)."""
        if self._drag_mode:
            return True
        if self._menu.isActiveWindow():
            return True
        w: Optional[QWidget] = QApplication.focusWidget()
        while w is not None:
            if w is self._menu:
                return True
            w = w.parentWidget()
        return False

    def _preview_ok_while_menu_open(self) -> bool:
        """
        Overlays en prévisualisation : OK si RL ou le panneau réglages est la fenêtre Win32 active.
        (Win+D / bureau : ni l'un ni l'autre → False. La seule détection Qt focus est trop fragile.)
        """
        if sys.platform != "win32":
            return self._user_focus_in_settings_panel()
        try:
            wid = int(self._menu.effectiveWinId())
            menu_fg = is_hwnd_foreground(wid) if wid else self._user_focus_in_settings_panel()
        except Exception:
            menu_fg = self._user_focus_in_settings_panel()
        return bool(is_rocket_league_foreground() or menu_fg)

    def _sync_overlay_visibility(self) -> None:
        """Session, roster et menu réglages : masqués si RL n'est pas au premier plan (si activé)."""
        roster_visible = bool(self._visibility["roster"] or self._lobby_preview_enabled)
        allow = True
        if self.cfg.get("require_rl_focus"):
            allow = is_rocket_league_foreground()

        # Bureau / autre app : la fenêtre active n'est ni RL ni le menu → masquer les overlays.
        if self._menu.isVisible() and not self._preview_ok_while_menu_open():
            if self._drag_mode:
                if self._visibility["session"]:
                    self.overlay_session.show()
                    self.overlay_session.raise_()
                else:
                    self.overlay_session.hide()
                if roster_visible:
                    self.overlay_roster.show()
                    self.overlay_roster.raise_()
                else:
                    self.overlay_roster.hide()
            else:
                self.overlay_session.hide()
                self.overlay_roster.hide()
            return

        if not allow:
            # Le menu F5 est ouvert : RL n'a souvent plus le focus (fenêtre Qt au 1er plan).
            if self._menu.isVisible():
                if self._drag_mode:
                    if self._visibility["session"]:
                        self.overlay_session.show()
                        self.overlay_session.raise_()
                    else:
                        self.overlay_session.hide()
                    if roster_visible:
                        self.overlay_roster.show()
                        self.overlay_roster.raise_()
                    else:
                        self.overlay_roster.hide()
                else:
                    # Prévisualisation (focus encore dans le panneau réglages)
                    if self._visibility["session"]:
                        self.overlay_session.show()
                        self.overlay_session.raise_()
                    else:
                        self.overlay_session.hide()
                    if roster_visible:
                        self.overlay_roster.show()
                        self.overlay_roster.raise_()
                    else:
                        self.overlay_roster.hide()
                return
            if self._drag_mode:
                self._drag_mode = False
                self.overlay_session.set_drag_enabled(False)
                self.overlay_roster.set_drag_enabled(False)
            self.overlay_session.hide()
            self.overlay_roster.hide()
            return

        if self._drag_mode:
            if self._visibility["session"]:
                self.overlay_session.show()
                self.overlay_session.raise_()
            else:
                self.overlay_session.hide()
            if roster_visible:
                self.overlay_roster.show()
                self.overlay_roster.raise_()
            else:
                self.overlay_roster.hide()
            return

        if self._visibility["session"]:
            self.overlay_session.show()
        else:
            self.overlay_session.hide()
        if roster_visible:
            self.overlay_roster.show()
        else:
            self.overlay_roster.hide()

    def _on_focus_tick(self) -> None:
        self._sync_overlay_visibility()
        self._rl_process_poll_i += 1
        if self._rl_process_poll_i >= self._rl_process_poll_every:
            self._rl_process_poll_i = 0
            self._watch_rl_process_exit()

    def _watch_rl_process_exit(self) -> None:
        if sys.platform != "win32":
            return
        ok = rocket_league_process_running()
        if self._rl_was_running and not ok:
            self.session.reset_counters()
            event_log("Session counters reset (Rocket League closed)", tag="session")
            self.refresh_requested.emit()
        self._rl_was_running = ok

    def _settings_menu_allowed(self) -> bool:
        if not self.cfg.get("require_rl_focus"):
            return True
        return is_rocket_league_foreground()

    def _notify_settings_need_rl_focus(self) -> None:
        if self._tray is not None:
            self._tray.showMessage(
                "RL Live Tracker",
                "Open settings (F5) while Rocket League is in the foreground.",
                QSystemTrayIcon.MessageIcon.Information,
                4500,
            )
        else:
            warn_log("Settings (F5): bring Rocket League to the foreground to open the menu.")

    def _try_present_settings_menu(self) -> bool:
        if not self._settings_menu_allowed():
            self._notify_settings_need_rl_focus()
            return False
        self._menu.present(
            self._visibility["session"],
            self._visibility["roster"],
            bool(self.cfg.get("show_mmr_ingame", True)),
            self._lobby_preview_enabled,
        )
        return True

    def _seed_mmr_from_cache(self) -> None:
        sid = self.cfg.get("self_player_id")
        if not sid:
            return
        e = self.mmr_client.get(sid)
        if e and not e.get("not_found"):
            b = e.get("best") or {}
            if b.get("mmr") is not None:
                self.session.current_mmr = int(b["mmr"])

    def _wire_signals(self) -> None:
        self.stats.match_initialized.connect(self._on_match_initialized)
        self.stats.match_ended.connect(self._on_match_ended)
        self.stats.match_destroyed.connect(self._on_match_destroyed)

    def _wire_menu_signals(self) -> None:
        self._menu.toggleSession.connect(self._on_menu_toggle_session)
        self._menu.toggleRoster.connect(self._on_menu_toggle_roster)
        self._menu.toggleMmr.connect(self._on_menu_toggle_mmr)
        self._menu.anchorChanged.connect(self._on_menu_anchor)
        self._menu.themePresetChanged.connect(self._on_menu_theme_preset)
        self._menu.lobbyPreviewToggled.connect(self._on_menu_lobby_preview_toggled)
        self._menu.dragRequested.connect(self._on_menu_drag_requested)
        self._menu.dragFinished.connect(self._on_menu_drag_finished)
        self._menu.menuClosed.connect(self._sync_tray_from_state)
        self._menu.rosterMmrPresetChanged.connect(self._on_menu_roster_mmr_preset)

    def _on_menu_roster_mmr_preset(self, preset: str) -> None:
        self.cfg["roster_mmr_preset"] = str(preset).strip().lower()
        save_config(self.cfg)
        self._do_refresh()

    def _on_menu_toggle_session(self, checked: bool) -> None:
        self._visibility["session"] = bool(checked)
        self.cfg["show_session_overlay"] = bool(checked)
        save_config(self.cfg)
        if hasattr(self, "_act_sess") and self._act_sess is not None:
            self._act_sess.blockSignals(True)
            self._act_sess.setChecked(bool(checked))
            self._act_sess.blockSignals(False)
        self._do_refresh()

    def _on_menu_toggle_roster(self, checked: bool) -> None:
        self._visibility["roster"] = bool(checked)
        self.cfg["show_roster_overlay"] = bool(checked)
        save_config(self.cfg)
        if hasattr(self, "_act_roster") and self._act_roster is not None:
            self._act_roster.blockSignals(True)
            self._act_roster.setChecked(bool(checked))
            self._act_roster.blockSignals(False)
        self._do_refresh()

    def _on_menu_toggle_mmr(self, checked: bool) -> None:
        self.cfg["show_mmr_ingame"] = bool(checked)
        save_config(self.cfg)
        if hasattr(self, "_act_mmr_ingame") and self._act_mmr_ingame is not None:
            self._act_mmr_ingame.blockSignals(True)
            self._act_mmr_ingame.setChecked(bool(checked))
            self._act_mmr_ingame.blockSignals(False)
        self._do_refresh()

    def _on_menu_anchor(self, which: str, anchor: str) -> None:
        key = f"position_{which}_anchor"
        self.cfg[key] = str(anchor).lower()
        save_config(self.cfg)
        if which == "session":
            self.overlay_session.reposition()
        else:
            self.overlay_roster.reposition()

    def _on_menu_theme_preset(self, preset: str) -> None:
        if apply_theme_preset(self.cfg, str(preset).strip().lower()):
            save_config(self.cfg)
            self._do_refresh()

    def _on_menu_lobby_preview_toggled(self, checked: bool) -> None:
        self._lobby_preview_enabled = bool(checked)
        self._do_refresh()

    def _on_overlay_position_committed(self, which: str) -> None:
        if which == "session":
            x, y = self.overlay_session.current_pos()
            self.cfg["position_session_custom_xy"] = [x, y]
            self.cfg["position_session_anchor"] = "custom"
        else:
            x, y = self.overlay_roster.current_pos()
            self.cfg["position_roster_custom_xy"] = [x, y]
            self.cfg["position_roster_anchor"] = "custom"
        save_config(self.cfg)
        if self._menu.isVisible():
            self._menu.sync_from_app(
                self._visibility["session"],
                self._visibility["roster"],
                bool(self.cfg.get("show_mmr_ingame", True)),
                self._lobby_preview_enabled,
            )

    def _on_menu_drag_requested(self) -> None:
        self._set_drag_mode(True)

    def _on_menu_drag_finished(self) -> None:
        self._set_drag_mode(False)
        roster_visible = bool(self._visibility["roster"] or self._lobby_preview_enabled)
        if self._visibility["session"]:
            sx, sy = self.overlay_session.current_pos()
            self.cfg["position_session_custom_xy"] = [sx, sy]
            self.cfg["position_session_anchor"] = "custom"
        if roster_visible:
            rx, ry = self.overlay_roster.current_pos()
            self.cfg["position_roster_custom_xy"] = [rx, ry]
            self.cfg["position_roster_anchor"] = "custom"
        save_config(self.cfg)
        if self._menu.isVisible():
            self._menu.sync_from_app(
                self._visibility["session"],
                self._visibility["roster"],
                bool(self.cfg.get("show_mmr_ingame", True)),
                self._lobby_preview_enabled,
            )
        self._do_refresh()

    def _toggle_menu(self) -> None:
        if self._menu.isVisible():
            self._menu.close_menu()
            return
        self._try_present_settings_menu()

    def _sync_tray_from_state(self) -> None:
        if hasattr(self, "_act_sess") and self._act_sess is not None:
            self._act_sess.blockSignals(True)
            self._act_sess.setChecked(self._visibility["session"])
            self._act_sess.blockSignals(False)
        if hasattr(self, "_act_roster") and self._act_roster is not None:
            self._act_roster.blockSignals(True)
            self._act_roster.setChecked(self._visibility["roster"])
            self._act_roster.blockSignals(False)
        if hasattr(self, "_act_mmr_ingame") and self._act_mmr_ingame is not None:
            self._act_mmr_ingame.blockSignals(True)
            self._act_mmr_ingame.setChecked(bool(self.cfg.get("show_mmr_ingame", True)))
            self._act_mmr_ingame.blockSignals(False)
        if hasattr(self, "_act_drag") and self._act_drag is not None:
            self._act_drag.blockSignals(True)
            self._act_drag.setChecked(bool(self._drag_mode))
            self._act_drag.blockSignals(False)

    def _on_stats_conn(self, ok: bool) -> None:
        self.session.stats_connected = ok
        self.refresh_requested.emit()

    def _on_match_initialized(self, payload: dict) -> None:
        self._match_outcome_recorded = False
        self.state["in_match"] = True
        self.state["roster"] = payload["players"]
        # Ne pas couper le poll post-match du match précédent (sinon delta / cumul perdus).

        if not self.cfg.get("self_player_id"):
            mt = payload["myTeam"]
            same = [p for p in payload["players"] if p["team"] == mt]
            if len(same) == 1:
                self.cfg["self_player_id"] = same[0]["key"]
                mmr_log(f"auto self_player_id={self.cfg['self_player_id']!r}")
                event_log(
                    f"Self player detected: {same[0].get('name', '?')!r}",
                    tag="app",
                )
                save_config(self.cfg)

        sid = self.cfg.get("self_player_id")
        if sid:
            for p in payload["players"]:
                if p["key"] == sid:
                    self.session.self_name = p["name"]
                    break

        self_entry = self.mmr_client.get(sid) if sid else None
        self.session.on_match_initialized(payload["players"], self_entry)
        if sid and self_entry:
            self.session.ensure_baseline_for_playlist(self.session.active_playlist, self_entry)

        if self.mmr_client.is_enabled():
            self.mmr_client.enqueue_roster(payload["players"])

        keys = tuple(sorted(p.get("key") or "" for p in payload["players"]))
        pl = self.session.active_playlist
        sig = (keys, pl, str(payload.get("arena", "")))
        if sig != self._last_lobby_sig:
            self._last_lobby_sig = sig
            mt = int(payload.get("myTeam", 0))
            side = "orange" if mt == 1 else "blue"
            event_log(
                f"Lobby · {pl.upper()} · {_arena_readable(str(payload.get('arena', '')))} "
                f"· {side} team · {len(payload['players'])} player(s)"
            )

        self.refresh_requested.emit()

    def _on_match_ended(self, payload: dict) -> None:
        self._match_outcome_recorded = True
        self.state["in_match"] = False
        won = payload["winner"] == payload["myTeam"]
        self.session.on_match_ended_outcome(won)

        sid = self.cfg.get("self_player_id")
        pl = self.session.active_playlist
        record = {
            "matchGuid": payload.get("matchGuid"),
            "endedAt": now_iso(),
            "arena": payload["arena"],
            "myTeam": payload["myTeam"],
            "winner": payload["winner"],
            "result": "W" if won else "L",
            "score": payload.get("score"),
            "playlist": pl,
            "players": payload["players"],
        }
        append_match(record)

        sc = payload.get("score")
        if isinstance(sc, (list, tuple)) and len(sc) >= 2:
            s0, s1 = int(sc[0]), int(sc[1])
        else:
            s0, s1 = 0, 0
        lbl = "Win" if won else "Loss"
        event_log(f"End · {pl.upper()} · {lbl} {s0}-{s1}")

        if sid and self.mmr_client.is_enabled():
            # Finaliser le TRN en attente du match précédent avant d'écraser post_pending.
            if self.post_pending.get("active"):
                ent_prev = self.mmr_client.get(sid)
                self._try_apply_pending(ent_prev)
                if self.post_pending.get("active"):
                    pl_ab = self.post_pending.get("playlist") or "other"
                    if self.session.reconcile_mmr_delta_from_session_start(
                        ent_prev, pl_ab
                    ):
                        event_log(
                            f"MMR total realigned · {pl_ab.upper()} · "
                            "(current TRN − session start, pending dropped)"
                        )
                        mmr_log(
                            f"reconcile(abandon): pl={pl_ab!r} "
                            f"cumul={self.session.session_delta_by_playlist()!r}"
                        )
                    self.post_pending["active"] = False
            be = self.mmr_client.get(sid)
            blu = (be or {}).get("lastUpdated") or ""
            frozen, reliable = self.session.freeze_baseline_at_match_end(pl, be)
            if frozen is None and pl in RANKED_PLAYLISTS:
                frozen = self.session.current_mmr
                reliable = False
            self.post_pending["active"] = True
            self.post_pending["baseline_lu"] = blu
            self.post_pending["playlist"] = pl
            self.post_pending["baseline_mmr"] = frozen
            self.post_pending["baseline_reliable"] = bool(reliable)
            self_player = next((p for p in payload["players"] if p["key"] == sid), None)
            if self_player:
                self._start_post_match_poll(self_player)
            if frozen is None:
                mmr_log("post-match: baseline MMR missing (empty TRN cache?) — session delta may stay empty")

        self.refresh_requested.emit()

    def _post_match_trn_ready(self, cur: Optional[dict]) -> bool:
        if not self.post_pending.get("active") or not cur or cur.get("not_found"):
            return False
        blu = self.post_pending.get("baseline_lu") or ""
        clu = (cur or {}).get("lastUpdated") or ""
        pl = self.post_pending.get("playlist") or "other"
        base_m = self.post_pending.get("baseline_mmr")
        new_m = mmr_for_playlist(cur, pl)
        if _trn_last_updated_is_newer(clu, blu):
            return True
        if base_m is not None and new_m is not None and new_m != base_m:
            return True
        return False

    def _start_post_match_poll(self, self_player: dict) -> None:
        if not self.mmr_client.is_enabled():
            return
        sid = self.cfg.get("self_player_id")
        if not sid:
            return
        self.poll_token += 1
        tok = self.poll_token

        # Rafraîchir tout de suite : avant c’était 120 s entre chaque tentative (trop long).
        self.mmr_client.enqueue(
            self_player.get("primaryId") or "",
            self_player.get("name") or "",
            force=True,
        )

        # Attentes entre essais si TRN n’a pas encore bougé (ms)
        retry_delays_ms = [2000, 3000, 5000, 7000, 10000, 15000, 20000]

        def attempt(i: int) -> None:
            if self.poll_token != tok:
                return
            cur = self.mmr_client.get(sid)
            if self._post_match_trn_ready(cur):
                mmr_log("poll: TRN data ready (lastUpdated or playlist MMR)")
                self._try_apply_pending(cur)
                return
            if i >= len(retry_delays_ms):
                mmr_log("poll: budget exhausted — TRN unchanged")
                pl_done = self.post_pending.get("playlist") or "other"
                sid_poll = self.cfg.get("self_player_id")
                if sid_poll:
                    ent = self.mmr_client.get(sid_poll)
                    if self.session.reconcile_mmr_delta_from_session_start(
                        ent, pl_done
                    ):
                        event_log(
                            f"MMR total realigned · {pl_done.upper()} · "
                            "(current TRN − session start)"
                        )
                        mmr_log(
                            f"reconcile(poll): pl={pl_done!r} "
                            f"cumul={self.session.session_delta_by_playlist()!r}"
                        )
                self.post_pending["active"] = False
                self.refresh_requested.emit()
                return
            mmr_log(f"poll attempt {i + 1}/{len(retry_delays_ms)} force refresh")
            self.mmr_client.enqueue(
                self_player.get("primaryId") or "",
                self_player.get("name") or "",
                force=True,
            )
            QTimer.singleShot(int(retry_delays_ms[i]), lambda: attempt(i + 1))

        # Laisser ~1 s au 1er fetch forcé avant le 1er contrôle
        QTimer.singleShot(1000, lambda: attempt(0))

    def _try_apply_pending(self, entry: Optional[dict]) -> None:
        if not self.post_pending.get("active"):
            return
        if not entry or entry.get("not_found"):
            return
        pl = self.post_pending.get("playlist") or "other"
        base_mmr = self.post_pending.get("baseline_mmr")
        base_reliable = bool(self.post_pending.get("baseline_reliable"))
        d = self.session.apply_post_match_trn(
            entry,
            pl,
            base_mmr,
            baseline_reliable=base_reliable,
        )
        if d is not None:
            event_log(f"TRN updated · {pl.upper()} · {d:+} MMR (last match)")
            mmr_log(
                f"post-match: playlist={pl!r} delta={d:+} session_cumul={self.session.session_delta_by_playlist()!r}"
            )
            self.post_pending["active"] = False
            self.refresh_requested.emit()

    def _synthetic_aborted_match_loss(self) -> None:
        """Quit early / replay sans MatchEnded côté app : la partie était en cours → équivalent défaite."""
        self._match_outcome_recorded = True
        self.session.on_match_ended_outcome(False)
        event_log(
            "Match closed without end event — counted as loss (forfeit / quit during replay)",
            tag="session",
        )
        self.refresh_requested.emit()

    def _on_match_destroyed(self) -> None:
        if self.state["in_match"] and not self._match_outcome_recorded:
            self._synthetic_aborted_match_loss()
        self.state["in_match"] = False
        self.state["roster"] = []
        self._last_lobby_sig = None
        event_log("Lobby closed — waiting for next")
        self.refresh_requested.emit()

    def _on_mmr_updated(self, key: str) -> None:
        sid = self.cfg.get("self_player_id")
        if sid and key == sid:
            cur = self.mmr_client.get(key)
            if self.state["in_match"]:
                self.session.ensure_baseline_for_playlist(self.session.active_playlist, cur)
            if self.post_pending.get("active") and cur and self._post_match_trn_ready(cur):
                self._try_apply_pending(cur)
            if cur and not cur.get("not_found"):
                ap = self.session.active_playlist
                m = mmr_for_playlist(cur, ap)
                if m is not None:
                    self.session.current_mmr = m
        self.refresh_requested.emit()

    def _mmr_db(self) -> dict[str, Optional[dict]]:
        out: dict[str, Optional[dict]] = {}
        for p in self.state["roster"]:
            k = p.get("key")
            if k:
                out[k] = self.mmr_client.get(k)
        return out

    def _do_refresh(self) -> None:
        html_sess = render_session_html(
            self.cfg,
            self.session,
            in_match=bool(self.state.get("in_match")),
        )
        self.overlay_session.set_html(html_sess)

        roster = self.state["roster"]
        pl = self.session.active_playlist
        if roster and self.state["in_match"]:
            html_r = render_roster_html(
                self.cfg, roster, self._mmr_db(), pl
            )
            self.overlay_roster.set_html(html_r)
        elif self._lobby_preview_enabled:
            self.overlay_roster.set_html(render_roster_preview_html(self.cfg))
        else:
            self.overlay_roster.set_html(roster_overlay_empty_html(self.cfg))

        self._sync_overlay_visibility()

    def _set_drag_mode(self, enabled: bool) -> None:
        self._drag_mode = bool(enabled)
        self._menu.set_drag_toggle_state(self._drag_mode)
        self.overlay_session.set_drag_enabled(self._drag_mode)
        self.overlay_roster.set_drag_enabled(self._drag_mode)
        self._sync_overlay_visibility()
        if hasattr(self, "_act_drag") and self._act_drag is not None:
            self._act_drag.blockSignals(True)
            self._act_drag.setChecked(self._drag_mode)
            self._act_drag.blockSignals(False)

    def _persist_custom_positions_if_needed(self) -> None:
        if str(self.cfg.get("position_session_anchor", "")).lower() == "custom":
            sx, sy = self.overlay_session.current_pos()
            self.cfg["position_session_custom_xy"] = [sx, sy]
        if str(self.cfg.get("position_roster_anchor", "")).lower() == "custom":
            rx, ry = self.overlay_roster.current_pos()
            self.cfg["position_roster_custom_xy"] = [rx, ry]
        save_config(self.cfg)

    def _setup_hotkeys(self) -> None:
        mapping: dict[str, Callable[[], None]] = {}

        def _on_hotkey():
            self.menu_toggle_requested.emit()

        menu_specs = list(self.cfg.get("menu_toggle_hotkeys") or ["f5"])
        for spec in menu_specs:
            try:
                mapping[_hotkey_to_pynput(spec)] = _on_hotkey
            except Exception as e:
                warn_log(f"menu hotkey ignored {spec!r}: {e}")

        for spec in list(self.cfg.get("toggle_hotkeys") or []):
            try:
                k = _hotkey_to_pynput(spec)
                if k in mapping:
                    warn_log(f"hotkey collision {k!r} — toggle_hotkeys {spec!r} skipped")
                    continue
                mapping[k] = _on_hotkey
            except Exception as e:
                warn_log(f"hotkey ignored {spec!r}: {e}")

        for spec in list(self.cfg.get("roster_toggle_hotkeys") or []):
            try:
                k = _hotkey_to_pynput(spec)
                if k in mapping:
                    warn_log(f"hotkey collision {k!r} — roster_toggle {spec!r} skipped")
                    continue
                mapping[k] = _on_hotkey
            except Exception as e:
                warn_log(f"hotkey ignored {spec!r}: {e}")

        for spec in list(self.cfg.get("mmr_tracker_toggle_hotkeys") or []):
            try:
                k = _hotkey_to_pynput(spec)
                if k in mapping:
                    warn_log(f"hotkey collision {k!r} — mmr_tracker_toggle {spec!r} skipped")
                    continue
                mapping[k] = _on_hotkey
            except Exception as e:
                warn_log(f"hotkey ignored {spec!r}: {e}")

        for spec in list(self.cfg.get("mmr_ingame_toggle_hotkeys") or []):
            try:
                k = _hotkey_to_pynput(spec)
                if k in mapping:
                    warn_log(f"hotkey collision {k!r} — mmr_ingame_toggle {spec!r} skipped")
                    continue
                mapping[k] = _on_hotkey
            except Exception as e:
                warn_log(f"hotkey ignored {spec!r}: {e}")

        _start_hotkeys_merged(mapping)

    def _setup_tray(self) -> None:
        self._tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(_make_tray_icon(), self.app)
        tray.setToolTip("RL Live Tracker")

        menu = QMenu()

        act_settings = QAction("Settings (F5)…", menu)

        def _open_settings() -> None:
            self._try_present_settings_menu()

        act_settings.triggered.connect(_open_settings)

        act_sess = QAction("Show Stats Tracker", menu)
        act_sess.setCheckable(True)
        act_sess.setChecked(self._visibility["session"])

        def _sync_sess(checked: bool) -> None:
            self._visibility["session"] = bool(checked)
            self.cfg["show_session_overlay"] = bool(checked)
            save_config(self.cfg)
            self._do_refresh()

        act_sess.toggled.connect(_sync_sess)

        act_roster = QAction("Show Lobby Ranks", menu)
        act_roster.setCheckable(True)
        act_roster.setChecked(self._visibility["roster"])

        def _sync_roster(checked: bool) -> None:
            self._visibility["roster"] = bool(checked)
            self.cfg["show_roster_overlay"] = bool(checked)
            save_config(self.cfg)
            self._do_refresh()

        act_roster.toggled.connect(_sync_roster)

        act_mmr = QAction("MMR tracker.network", menu)
        act_mmr.setCheckable(True)
        act_mmr.setChecked(self.mmr_client.is_enabled())

        def _mmr_tog(checked: bool) -> None:
            self.mmr_client.set_enabled(bool(checked))
            self.cfg["mmr_enabled"] = bool(checked)
            save_config(self.cfg)

        act_mmr.toggled.connect(_mmr_tog)

        act_mmr_ingame = QAction("Show in-game MMR", menu)
        act_mmr_ingame.setCheckable(True)
        act_mmr_ingame.setChecked(bool(self.cfg.get("show_mmr_ingame", True)))

        def _mmr_ingame_tog(checked: bool) -> None:
            self.cfg["show_mmr_ingame"] = bool(checked)
            save_config(self.cfg)
            self._do_refresh()

        act_mmr_ingame.toggled.connect(_mmr_ingame_tog)

        act_drag = QAction("Drag overlays (global)", menu)
        act_drag.setCheckable(True)
        act_drag.setChecked(False)

        def _drag_tog(checked: bool) -> None:
            self._set_drag_mode(bool(checked))

        act_drag.toggled.connect(_drag_tog)

        act_reset = QAction("Reset session counters", menu)

        def _reset() -> None:
            self.session.reset_counters()
            event_log("Session counters cleared (tray · manual reset)", tag="session")
            self._do_refresh()

        act_reset.triggered.connect(_reset)

        act_folder = QAction("Open data folder", menu)

        def _open_folder() -> None:
            try:
                if sys.platform == "win32":
                    os.startfile(str(DATA_DIR))  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", str(DATA_DIR)])

            except Exception as e:
                warn_log(f"open data folder: {e}")

        act_folder.triggered.connect(_open_folder)

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.app.quit)

        menu.addAction(act_settings)
        menu.addSeparator()
        menu.addAction(act_sess)
        menu.addAction(act_roster)
        menu.addSeparator()
        menu.addAction(act_mmr)
        menu.addAction(act_mmr_ingame)
        menu.addAction(act_drag)
        menu.addSeparator()
        menu.addAction(act_reset)
        menu.addAction(act_folder)
        menu.addSeparator()
        menu.addAction(act_quit)

        tray.setContextMenu(menu)
        tray.show()

        self._tray = tray
        self._act_sess = act_sess
        self._act_roster = act_roster
        self._act_mmr_tracker = act_mmr
        self._act_mmr_ingame = act_mmr_ingame
        self._act_drag = act_drag

    def run(self) -> int:
        rc = self.app.exec()
        self._persist_custom_positions_if_needed()
        self.stats.stop()
        self.mmr_client.stop()
        return rc


def run() -> int:
    lock_path = DATA_DIR / ".rl-live-tracker.lock"
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        app_log("Another instance is already running — exiting.", dim=True)
        return 1

    ctrl = AppController()
    return ctrl.run()
