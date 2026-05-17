"""Main app injector window (BakkesMod-style) — not overlay settings."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont
from PySide6.QtWidgets import QLabel, QMainWindow, QMenuBar, QVBoxLayout, QWidget


class InjectorWindow(QMainWindow):
    """Native Windows utility window: centered status + menu bar only."""

    quitRequested = Signal()
    closeRequested = Signal()
    minimizeRequested = Signal()
    checkUpdatesRequested = Signal()
    openDataFolderRequested = Signal()
    autostartToggled = Signal(bool)
    closeToTrayToggled = Signal(bool)
    startMinimizedToTrayToggled = Signal(bool)
    checkUpdatesOnStartupToggled = Signal(bool)
    aboutRequested = Signal()
    statsApiHelpRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._message = "Starting…"
        self._suppress_minimize_once = False

        self.setWindowTitle("RL Live Tracker")
        self.resize(420, 140)
        self.setMinimumSize(360, 120)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 12)

        layout.addStretch(1)

        self._status = QLabel(self._message)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        self._status.setFont(font)
        layout.addWidget(self._status)

        layout.addStretch(1)

        self._build_menus()

    def _build_menus(self) -> None:
        bar = QMenuBar(self)
        self.setMenuBar(bar)

        file_menu = bar.addMenu("&File")
        act_folder = QAction("Open data folder", self)
        act_folder.triggered.connect(self.openDataFolderRequested.emit)
        file_menu.addAction(act_folder)
        act_updates = QAction("Check for updates", self)
        act_updates.triggered.connect(self.checkUpdatesRequested.emit)
        file_menu.addAction(act_updates)
        act_releases = QAction("Releases", self)
        act_releases.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/Minitsonga/rl-live-tracker/releases")
            )
        )
        file_menu.addAction(act_releases)
        file_menu.addSeparator()
        act_exit = QAction("E&xit", self)
        act_exit.triggered.connect(self.quitRequested.emit)
        file_menu.addAction(act_exit)

        settings_menu = bar.addMenu("&Settings")
        self._act_close_tray = QAction("Close to system tray", self)
        self._act_close_tray.setCheckable(True)
        self._act_close_tray.toggled.connect(self.closeToTrayToggled.emit)
        settings_menu.addAction(self._act_close_tray)

        self._act_start_minimized = QAction("Start minimized to tray", self)
        self._act_start_minimized.setCheckable(True)
        self._act_start_minimized.toggled.connect(self.startMinimizedToTrayToggled.emit)
        settings_menu.addAction(self._act_start_minimized)

        self._act_updates_startup = QAction("Check for updates on startup", self)
        self._act_updates_startup.setCheckable(True)
        self._act_updates_startup.toggled.connect(self.checkUpdatesOnStartupToggled.emit)
        settings_menu.addAction(self._act_updates_startup)

        settings_menu.addSeparator()
        self._act_autostart = QAction("Run on startup", self)
        self._act_autostart.setCheckable(True)
        self._act_autostart.toggled.connect(self.autostartToggled.emit)
        settings_menu.addAction(self._act_autostart)

        help_menu = bar.addMenu("&Help")
        act_stats_api = QAction("Stats API setup…", self)
        act_stats_api.triggered.connect(self.statsApiHelpRequested.emit)
        help_menu.addAction(act_stats_api)
        act_about = QAction("About", self)
        act_about.triggered.connect(self.aboutRequested.emit)
        help_menu.addAction(act_about)

    def _set_checkable(self, action: QAction, checked: bool) -> None:
        action.blockSignals(True)
        action.setChecked(bool(checked))
        action.blockSignals(False)

    def set_tray_settings_checked(
        self,
        *,
        close_to_tray: bool,
        start_minimized: bool,
        check_updates_on_startup: bool,
        autostart: bool,
    ) -> None:
        self._set_checkable(self._act_close_tray, close_to_tray)
        self._set_checkable(self._act_start_minimized, start_minimized)
        self._set_checkable(self._act_updates_startup, check_updates_on_startup)
        self._set_checkable(self._act_autostart, autostart)

    def set_autostart_checked(self, checked: bool) -> None:
        self._set_checkable(self._act_autostart, bool(checked))

    def set_status_message(self, message: str) -> None:
        self._message = str(message).strip() or "—"
        self._status.setText(self._message)

    def set_status_lines(self, lines: list[str]) -> None:
        """Backward-compatible: first non-empty line only."""
        for line in lines:
            if str(line).strip():
                self.set_status_message(str(line).strip())
                return
        self.set_status_message("—")

    def show_injector(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self) -> None:
        self.hide()

    def cancel_pending_minimize(self) -> None:
        """Restore window after user cancelled a minimize-to-tray prompt."""
        self._suppress_minimize_once = True
        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            if self._suppress_minimize_once:
                self._suppress_minimize_once = False
                super().changeEvent(event)
                return
            self.minimizeRequested.emit()
            event.accept()
            return
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.closeRequested.emit()
        event.ignore()


HubWindow = InjectorWindow
