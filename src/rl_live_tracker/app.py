"""Point d'entrée Qt : Stats API + MMR + deux overlays + tray."""
from __future__ import annotations

import os
import re
import sys
import subprocess
import threading
from typing import Any, Callable, Optional

from PySide6.QtCore import QLockFile, QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from . import __version__
from .autostart import is_autostart_enabled, set_autostart_enabled
from .config import apply_theme_preset, load_config, save_config
from .focus_rl import is_hwnd_foreground, is_rocket_league_foreground
from .mmr import MMRClient, RANKED_PLAYLISTS
from .paths import DATA_DIR, branding_path, now_iso
from .ui_theme import apply_app_theme
from .render_roster import (
    render_roster_html,
    render_roster_preview_html,
    roster_overlay_empty_html,
)
from .render_session import render_session_html
from .hub_window import InjectorWindow
from .overlay_settings_dialog import OverlaySettingsDialog
from .stats_api_help_dialog import StatsApiHelpDialog
from .overlay_widgets import TransparentOverlay
from .session_state import SessionState, mmr_for_playlist
from .stats_client import StatsClient
from .storage import append_match
from .updates import ReleaseInfo, check_for_update
from .tray_prefs import (
    TrayWindowAction,
    apply_close_choice,
    apply_minimize_choice,
    resolve_close_action,
    resolve_minimize_action,
)
from .applog import app_log, event_log, mmr_log, warn_log

_TIMER_ACTIVE_MS = 450
_TIMER_IDLE_MS = 5000


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


_WINDOW_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
_TRAY_ICON_SIZES = (16, 24, 32)


def _fallback_cyan_icon(size: int = 64) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setBrush(QColor(0, 200, 255))
    p.setPen(QColor(0, 140, 180))
    m = max(2, size // 8)
    p.drawRoundedRect(m, m, size - 2 * m, size - 2 * m, size // 6, size // 6)
    p.end()
    return QIcon(pix)


def _icon_from_png(png_path: str, sizes: tuple[int, ...]) -> QIcon:
    base = QPixmap(png_path)
    if base.isNull():
        return QIcon()
    icon = QIcon()
    for side in sizes:
        scaled = base.scaled(
            side,
            side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(1.0)
        icon.addPixmap(scaled)
    return icon


def _icon_from_ico() -> QIcon:
    ico = branding_path("app.ico")
    if not ico.is_file():
        return QIcon()
    icon = QIcon(str(ico))
    return icon if not icon.isNull() else QIcon()


def _app_window_icon() -> QIcon:
    """Barre des tâches / titre : .ico multi-résolution (évite le flou HiDPI)."""
    icon = _icon_from_ico()
    if not icon.isNull():
        return icon
    png = branding_path("app_icon.png")
    if png.is_file():
        icon = _icon_from_png(str(png), _WINDOW_ICON_SIZES)
        if not icon.isNull():
            return icon
    return _fallback_cyan_icon(256)


def _make_tray_icon() -> QIcon:
    """Zone de notification : petites tailles (déjà nettes à l'échelle tray)."""
    png = branding_path("app_icon.png")
    if png.is_file():
        icon = _icon_from_png(str(png), _TRAY_ICON_SIZES)
        if not icon.isNull():
            return icon
    return _fallback_cyan_icon(32)


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


class _UpdateCheckThread(QThread):
    finished = Signal(object, object)  # bool | None, ReleaseInfo | None

    def run(self) -> None:
        try:
            newer, info = check_for_update()
            self.finished.emit(newer, info)
        except Exception:
            self.finished.emit(None, None)


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
        # True après MatchEnded ou défaite synthétique (destroy sans fin).
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
        apply_app_theme(self.app)
        self.app.setWindowIcon(_app_window_icon())

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

        self._injector = InjectorWindow()
        self._injector.setWindowIcon(_app_window_icon())
        self._overlay_settings = OverlaySettingsDialog(self.cfg)
        self._wire_injector_signals()
        self._wire_overlay_settings_signals()

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
        # True = Stats API TCP connectée (mode actif) ; False = idle (pause client).
        self._stats_runtime_active = False
        self._stats_was_connected = False
        self._update_thread: Optional[_UpdateCheckThread] = None
        self._stats_api_help: Optional[StatsApiHelpDialog] = None

        self.refresh_requested.connect(self._do_refresh)
        self.menu_toggle_requested.connect(self._toggle_menu)
        self.mmr_client.updated.connect(self._on_mmr_updated)
        self.stats.connection_status.connect(self._on_stats_conn)

        self.stats.start()
        self._setup_tray()
        self._setup_hotkeys()
        self._do_refresh()
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(_TIMER_ACTIVE_MS)
        self._focus_timer.timeout.connect(self._on_focus_tick)
        self._focus_timer.start()
        if bool(self.cfg.get("idle_when_rl_closed", True)):
            self._apply_idle_runtime(silent=True)
        else:
            self._apply_active_runtime(silent=True)
        self._sync_autostart_from_registry()
        if bool(self.cfg.get("check_updates_on_startup", True)):
            QTimer.singleShot(8000, self._check_updates_startup)
        self._sync_injector_settings_menu()
        self._refresh_injector_status()
        if not bool(self.cfg.get("start_minimized_to_tray")):
            self._injector.show_injector()
        app_log("Ready — F5 overlay settings · tray opens app window")

    def _user_focus_in_settings_panel(self) -> bool:
        """True si l'utilisateur interagit encore avec le menu (sinon ex. Alt+Tab vers une autre app)."""
        if self._drag_mode:
            return True
        if self._overlay_settings.isActiveWindow():
            return True
        w: Optional[QWidget] = QApplication.focusWidget()
        while w is not None:
            if w is self._overlay_settings:
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
            wid = int(self._overlay_settings.effectiveWinId())
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
        if self._overlay_settings.isVisible() and not self._preview_ok_while_menu_open():
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
            if self._overlay_settings.isVisible():
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

    def _idle_on_stats_disconnect(self) -> bool:
        return bool(self.cfg.get("idle_when_rl_closed", True))

    def _apply_idle_runtime(self, *, silent: bool = False) -> None:
        self.stats.resume()
        self._stats_runtime_active = False
        self._focus_timer.setInterval(_TIMER_IDLE_MS)
        if self._tray is not None:
            self._tray.setToolTip("RL Live Tracker — waiting for Rocket League")
        self.overlay_session.hide()
        self.overlay_roster.hide()
        self._refresh_injector_status()
        if not silent:
            app_log("Idle — Stats API disconnected", dim=True)

    def _apply_active_runtime(self, *, silent: bool = False) -> None:
        self.stats.resume()
        self._stats_runtime_active = True
        self._focus_timer.setInterval(_TIMER_ACTIVE_MS)
        if self._tray is not None:
            self._tray.setToolTip("RL Live Tracker")
        self._seed_mmr_from_cache()
        self._sync_overlay_visibility()
        self._refresh_injector_status()
        if not silent:
            app_log("Active — Stats API connected", dim=True)

    def _refresh_injector_status(self) -> None:
        if self.session.stats_connected:
            self._injector.set_status_message("Rocket League is running.")
        else:
            self._injector.set_status_message("Waiting for Rocket League.")

    def _sync_autostart_from_registry(self) -> None:
        if sys.platform != "win32":
            return
        reg = is_autostart_enabled()
        cfg_val = bool(self.cfg.get("launch_at_windows_startup"))
        if reg != cfg_val:
            self.cfg["launch_at_windows_startup"] = reg
            save_config(self.cfg)

    def _sync_injector_settings_menu(self) -> None:
        self._injector.set_tray_settings_checked(
            close_to_tray=bool(self.cfg.get("close_to_tray")),
            start_minimized=bool(self.cfg.get("start_minimized_to_tray")),
            check_updates_on_startup=bool(self.cfg.get("check_updates_on_startup", True)),
            autostart=bool(self.cfg.get("launch_at_windows_startup")),
        )

    def _on_menu_autostart_toggled(self, checked: bool) -> None:
        ok = set_autostart_enabled(bool(checked))
        if not ok and checked:
            warn_log("Could not enable Windows autostart")
            return
        self.cfg["launch_at_windows_startup"] = bool(checked)
        save_config(self.cfg)
        self._injector.set_autostart_checked(bool(checked))

    def _on_menu_close_to_tray_toggled(self, checked: bool) -> None:
        self.cfg["close_to_tray"] = bool(checked)
        save_config(self.cfg)

    def _on_menu_start_minimized_toggled(self, checked: bool) -> None:
        self.cfg["start_minimized_to_tray"] = bool(checked)
        save_config(self.cfg)

    def _on_menu_check_updates_startup_toggled(self, checked: bool) -> None:
        self.cfg["check_updates_on_startup"] = bool(checked)
        save_config(self.cfg)

    def _prompt_tray_minimize(self) -> TrayWindowAction:
        box = QMessageBox(self._injector)
        box.setWindowTitle("RL Live Tracker")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("The window will be hidden.")
        box.setInformativeText(
            "Quit the application completely, or keep it running in the system tray?"
        )
        quit_btn = box.addButton("Quit", QMessageBox.ButtonRole.DestructiveRole)
        hide_btn = box.addButton("Hide to tray", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(hide_btn)
        cb = QCheckBox("Don't ask again")
        box.setCheckBox(cb)
        box.exec()
        clicked = box.clickedButton()
        remember = cb.isChecked()
        if clicked == quit_btn:
            action = TrayWindowAction.QUIT
        elif clicked == hide_btn:
            action = TrayWindowAction.HIDE
        else:
            action = TrayWindowAction.CANCEL
        apply_minimize_choice(self.cfg, action, remember=remember)
        if remember:
            save_config(self.cfg)
            self._sync_injector_settings_menu()
        return action

    def _prompt_tray_close(self) -> TrayWindowAction:
        box = QMessageBox(self._injector)
        box.setWindowTitle("RL Live Tracker")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Close the application?")
        box.setInformativeText(
            "Closing the window will exit RL Live Tracker completely.\n"
            "You can hide it to the system tray instead and keep overlays running."
        )
        quit_btn = box.addButton(
            "Quit application", QMessageBox.ButtonRole.DestructiveRole
        )
        hide_btn = box.addButton("Hide to tray", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(quit_btn)
        cb = QCheckBox("Don't ask again")
        box.setCheckBox(cb)
        box.exec()
        clicked = box.clickedButton()
        remember = cb.isChecked()
        if clicked == quit_btn:
            action = TrayWindowAction.QUIT
        elif clicked == hide_btn:
            action = TrayWindowAction.HIDE
        else:
            action = TrayWindowAction.CANCEL
        apply_close_choice(self.cfg, action, remember=remember)
        if remember:
            save_config(self.cfg)
            self._sync_injector_settings_menu()
        return action

    def _on_injector_minimize_requested(self) -> None:
        action = resolve_minimize_action(self.cfg)
        if action is None:
            action = self._prompt_tray_minimize()
        if action == TrayWindowAction.CANCEL:
            self._injector.cancel_pending_minimize()
            return
        if action == TrayWindowAction.QUIT:
            self.app.quit()
            return
        self._injector.hide_to_tray()

    def _on_injector_close_requested(self) -> None:
        action = resolve_close_action(self.cfg)
        if action is None:
            action = self._prompt_tray_close()
        if action == TrayWindowAction.CANCEL:
            return
        if action == TrayWindowAction.HIDE:
            self._injector.hide_to_tray()
            return
        self.app.quit()

    def _check_updates_startup(self) -> None:
        dismissed = str(self.cfg.get("last_dismissed_version") or "")
        if dismissed and dismissed == __version__:
            return
        self._run_update_check(notify_if_current=False)

    def _run_update_check(self, *, notify_if_current: bool = True) -> None:
        if self._update_thread is not None and self._update_thread.isRunning():
            return
        self._update_thread = _UpdateCheckThread(self)
        self._update_thread.finished.connect(
            lambda newer, info: self._on_update_check_done(newer, info, notify_if_current)
        )
        self._update_thread.start()

    def _on_update_check_done(
        self,
        newer: object,
        info: object,
        notify_if_current: bool,
    ) -> None:
        if newer is None:
            return
        if not isinstance(info, ReleaseInfo):
            return
        if newer is True:
            dismissed = str(self.cfg.get("last_dismissed_version") or "")
            if dismissed != info.version:
                box = QMessageBox(self._injector)
                box.setWindowTitle("RL Live Tracker")
                box.setIcon(QMessageBox.Icon.Question)
                box.setText("An update is available:")
                body = (info.body or "").strip()
                if body:
                    box.setInformativeText(
                        f"{info.tag_name}\n\n{body[:400]}".strip()
                    )
                else:
                    box.setInformativeText(
                        f"{info.tag_name}\n\nYou are running v{__version__}."
                    )
                box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                box.setDefaultButton(QMessageBox.StandardButton.Yes)
                if box.exec() == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(info.html_url)
                else:
                    self.cfg["last_dismissed_version"] = info.version
                    save_config(self.cfg)
        else:
            if notify_if_current:
                QMessageBox.information(
                    self._injector,
                    "RL Live Tracker",
                    f"You are on the latest release (v{__version__}).",
                )

    def _clear_post_pending(self) -> None:
        self.post_pending["active"] = False
        self.post_pending["baseline_lu"] = ""
        self.post_pending["playlist"] = ""
        self.post_pending["baseline_mmr"] = None
        self.post_pending["baseline_reliable"] = False

    def _reset_session_for_rl_exit(self) -> None:
        self.session.reset_session()
        self._clear_post_pending()
        self.state["in_match"] = False
        self.state["roster"] = []
        self._match_outcome_recorded = True
        self._last_lobby_sig = None
        event_log("Session reset (Stats API disconnected)", tag="session")
        self.refresh_requested.emit()

    def _open_injector(self) -> None:
        self._sync_injector_settings_menu()
        self._refresh_injector_status()
        self._injector.show_injector()

    def _open_overlay_settings(self) -> None:
        if not self._overlay_settings_allowed():
            self._notify_overlay_settings_need_rl_focus()
            return
        self._overlay_settings.present(
            self._visibility["session"],
            self._visibility["roster"],
            bool(self.cfg.get("show_mmr_ingame", True)),
            self._lobby_preview_enabled,
        )

    def _overlay_settings_allowed(self) -> bool:
        if not self.cfg.get("require_rl_focus"):
            return True
        return is_rocket_league_foreground()

    def _notify_overlay_settings_need_rl_focus(self) -> None:
        if self._tray is not None:
            self._tray.showMessage(
                "RL Live Tracker",
                "Open overlay settings (F5) while Rocket League is in the foreground.",
                QSystemTrayIcon.MessageIcon.Information,
                4500,
            )
        else:
            warn_log("Overlay settings (F5): bring Rocket League to the foreground.")

    def _show_about(self) -> None:
        QMessageBox.about(
            self._injector,
            "About RL Live Tracker",
            f"<b>RL Live Tracker</b><br>"
            f"Version {__version__}<br><br>"
            f"Data folder:<br><code>{DATA_DIR}</code><br><br>"
            f'<a href="https://github.com/Minitsonga/rl-live-tracker">GitHub</a>',
        )

    def _show_stats_api_help(self) -> None:
        if self._stats_api_help is None:
            self._stats_api_help = StatsApiHelpDialog(self.cfg, self._injector)
        self._stats_api_help.refresh()
        self._stats_api_help.show()
        self._stats_api_help.raise_()
        self._stats_api_help.activateWindow()

    def _open_data_folder(self) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(DATA_DIR))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(DATA_DIR)])
        except Exception as e:
            warn_log(f"open data folder: {e}")

    def _seed_mmr_from_cache(self) -> None:
        sid = self.cfg.get("self_player_id")
        if not sid:
            return
        self._apply_self_mmr_from_cache(sid)

    def _apply_self_mmr_from_cache(self, player_key: str) -> None:
        """Même logique qu'avant la refonte : mode actif TRN, sinon best (comme au démarrage)."""
        entry = self.mmr_client.get(player_key)
        if not entry or entry.get("not_found"):
            return
        pl = self.session.active_playlist
        m = mmr_for_playlist(entry, pl)
        if m is None:
            best = entry.get("best") or {}
            if best.get("mmr") is not None:
                m = int(best["mmr"])
        if m is not None:
            self.session.current_mmr = m

    def _sync_session_mmr_from_cache(self) -> None:
        """Rafraîchit le MMR session depuis le cache (comme le lobby lit _mmr_db à chaque frame)."""
        if not bool(self.cfg.get("show_mmr_ingame", True)):
            return
        sid = self.cfg.get("self_player_id")
        if not sid:
            return
        self._apply_self_mmr_from_cache(sid)

    def _ensure_self_player_id(self, payload: dict) -> None:
        if self.cfg.get("self_player_id"):
            return
        local_key = payload.get("localPlayerKey")
        if isinstance(local_key, str) and local_key:
            self.cfg["self_player_id"] = local_key
            save_config(self.cfg)
            mmr_log(f"auto self_player_id (local)={local_key!r}")
            event_log(f"Self player detected (local): {local_key!r}", tag="app")
            return
        mt = payload.get("myTeam")
        same = [p for p in payload.get("players") or [] if p.get("team") == mt]
        if len(same) == 1:
            self.cfg["self_player_id"] = same[0]["key"]
            save_config(self.cfg)
            mmr_log(f"auto self_player_id={self.cfg['self_player_id']!r}")
            event_log(
                f"Self player detected: {same[0].get('name', '?')!r}",
                tag="app",
            )

    def _wire_signals(self) -> None:
        self.stats.match_initialized.connect(self._on_match_initialized)
        self.stats.match_ended.connect(self._on_match_ended)
        self.stats.match_destroyed.connect(self._on_match_destroyed)

    def _wire_injector_signals(self) -> None:
        self._injector.quitRequested.connect(self.app.quit)
        self._injector.closeRequested.connect(self._on_injector_close_requested)
        self._injector.minimizeRequested.connect(self._on_injector_minimize_requested)
        self._injector.checkUpdatesRequested.connect(
            lambda: self._run_update_check(notify_if_current=True)
        )
        self._injector.openDataFolderRequested.connect(self._open_data_folder)
        self._injector.autostartToggled.connect(self._on_menu_autostart_toggled)
        self._injector.closeToTrayToggled.connect(self._on_menu_close_to_tray_toggled)
        self._injector.startMinimizedToTrayToggled.connect(
            self._on_menu_start_minimized_toggled
        )
        self._injector.checkUpdatesOnStartupToggled.connect(
            self._on_menu_check_updates_startup_toggled
        )
        self._injector.aboutRequested.connect(self._show_about)
        self._injector.statsApiHelpRequested.connect(self._show_stats_api_help)

    def _wire_overlay_settings_signals(self) -> None:
        self._overlay_settings.toggleSession.connect(self._on_menu_toggle_session)
        self._overlay_settings.toggleRoster.connect(self._on_menu_toggle_roster)
        self._overlay_settings.toggleMmr.connect(self._on_menu_toggle_mmr)
        self._overlay_settings.anchorChanged.connect(self._on_menu_anchor)
        self._overlay_settings.themePresetChanged.connect(self._on_menu_theme_preset)
        self._overlay_settings.lobbyPreviewToggled.connect(
            self._on_menu_lobby_preview_toggled
        )
        self._overlay_settings.dragRequested.connect(self._on_menu_drag_requested)
        self._overlay_settings.dragFinished.connect(self._on_menu_drag_finished)
        self._overlay_settings.rosterMmrPresetChanged.connect(
            self._on_menu_roster_mmr_preset
        )

    def _on_menu_roster_mmr_preset(self, preset: str) -> None:
        self.cfg["roster_mmr_preset"] = str(preset).strip().lower()
        save_config(self.cfg)
        self._do_refresh()

    def _on_menu_toggle_session(self, checked: bool) -> None:
        self._visibility["session"] = bool(checked)
        self.cfg["show_session_overlay"] = bool(checked)
        save_config(self.cfg)
        self._do_refresh()

    def _on_menu_toggle_roster(self, checked: bool) -> None:
        self._visibility["roster"] = bool(checked)
        self.cfg["show_roster_overlay"] = bool(checked)
        save_config(self.cfg)
        self._do_refresh()

    def _on_menu_toggle_mmr(self, checked: bool) -> None:
        self.cfg["show_mmr_ingame"] = bool(checked)
        save_config(self.cfg)
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
        if self._overlay_settings.isVisible():
            self._overlay_settings.sync_from_app(
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
        if self._overlay_settings.isVisible():
            self._overlay_settings.sync_from_app(
                self._visibility["session"],
                self._visibility["roster"],
                bool(self.cfg.get("show_mmr_ingame", True)),
                self._lobby_preview_enabled,
            )
        self._do_refresh()

    def _toggle_menu(self) -> None:
        if self._overlay_settings.isVisible():
            self._overlay_settings.close_settings()
            return
        self._open_overlay_settings()

    def _on_stats_conn(self, ok: bool) -> None:
        prev = self._stats_was_connected
        self._stats_was_connected = ok
        self.session.stats_connected = ok
        if self._idle_on_stats_disconnect():
            if ok and not self._stats_runtime_active:
                self._apply_active_runtime()
            elif not ok and self._stats_runtime_active:
                self._apply_idle_runtime()
        if prev and not ok:
            self._reset_session_for_rl_exit()
        self.refresh_requested.emit()

    def _on_match_initialized(self, payload: dict) -> None:
        self._match_outcome_recorded = False
        self.state["in_match"] = True
        self.state["roster"] = payload["players"]
        # Ne pas couper le poll post-match du match précédent (sinon delta / cumul perdus).

        self._ensure_self_player_id(payload)

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
            if sid:
                for p in payload["players"]:
                    if p.get("key") == sid:
                        self.mmr_client.enqueue(
                            p.get("primaryId") or "",
                            p.get("name") or "",
                            force=False,
                        )
                        break

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
        if self._match_outcome_recorded:
            return
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
        """MatchDestroyed sans MatchEnded : défaite par défaut (forfait, quit, lobby annulé)."""
        self._match_outcome_recorded = True
        self.session.on_match_ended_outcome(False)
        event_log(
            "Match closed without end event — counted as loss",
            tag="session",
        )

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
                if m is None:
                    best = cur.get("best") or {}
                    if best.get("mmr") is not None:
                        m = int(best["mmr"])
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
        self._sync_session_mmr_from_cache()
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
        self._overlay_settings.set_drag_toggle_state(self._drag_mode)
        self.overlay_session.set_drag_enabled(self._drag_mode)
        self.overlay_roster.set_drag_enabled(self._drag_mode)
        self._sync_overlay_visibility()

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

        act_open = QAction("Open RL Live Tracker", menu)
        act_open.triggered.connect(self._open_injector)

        act_updates = QAction("Check for updates", menu)
        def _tray_check_updates() -> None:
            self._open_injector()
            self._run_update_check(notify_if_current=True)

        act_updates.triggered.connect(_tray_check_updates)

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.app.quit)

        menu.addAction(act_open)
        menu.addAction(act_updates)
        menu.addAction(act_quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()

        self._tray = tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._open_injector()

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
