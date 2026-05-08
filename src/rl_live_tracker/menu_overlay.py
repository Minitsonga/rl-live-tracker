"""F5 settings panel: visibility, anchors, themes and per-overlay opacity."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import THEME_PRESETS
from .overlay_widgets import CORNER_ANCHORS, resolve_overlay_screen
from .render_roster import ROSTER_MMR_PRESET_OPTIONS


ANCHOR_ORDER = CORNER_ANCHORS + ("custom",)
ANCHOR_LABELS = {
    "top-left": "◤ TL",
    "top-right": "◥ TR",
    "bottom-left": "◣ BL",
    "bottom-right": "◢ BR",
    "custom": "Custom",
}


class MenuPanel(QWidget):
    toggleSession = Signal(bool)
    toggleRoster = Signal(bool)
    toggleMmr = Signal(bool)
    rosterMmrPresetChanged = Signal(str)
    themePresetChanged = Signal(str)
    overlayOpacityChanged = Signal(str, int)  # which: "session"|"roster"
    lobbyPreviewToggled = Signal(bool)
    anchorChanged = Signal(str, str)  # "session"|"roster", anchor id
    dragRequested = Signal()
    dragFinished = Signal()
    menuClosed = Signal()

    def __init__(self, cfg: dict):
        super().__init__()
        self._cfg = cfg
        self._drag_from_menu = False

        self.setWindowFlags(
            Qt.Tool
            | Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAutoFillBackground(True)
        self.setWindowTitle("RL Live Tracker — Settings")

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 10)

        title = QLabel("RL Live Tracker")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color: #e8f0ff; background: transparent;")
        root.addWidget(title)

        sub = QLabel("F5 or Esc: close")
        sub.setStyleSheet("color: #9ab0cc; font-size: 9px; background: transparent;")
        root.addWidget(sub)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(0,200,255,40); max-height: 1px;")
        root.addWidget(line)

        self._btn_drag = QPushButton("Drag overlays: OFF")
        self._btn_drag.setCursor(Qt.PointingHandCursor)
        self._btn_drag.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 120, 160, 120); color: #e8f8ff;"
            "  border: 1px solid rgba(0, 200, 255, 80); border-radius: 4px;"
            "  padding: 6px 10px; font-size: 10px;"
            "}"
            "QPushButton:hover { background: rgba(0, 140, 180, 160); }"
        )
        self._btn_drag.clicked.connect(self._on_drag_clicked)
        root.addWidget(self._btn_drag)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid rgba(80, 110, 150, 90); border-radius: 4px; top: -1px; }"
            "QTabBar::tab { background: rgba(40, 52, 72, 220); color: #c8d8ec; padding: 6px 10px; margin-right: 3px; border-radius: 3px; }"
            "QTabBar::tab:selected { background: rgba(0, 100, 140, 200); color: #ffffff; }"
        )
        root.addWidget(tabs)

        tab_global = QWidget()
        g_layout = QVBoxLayout(tab_global)
        g_layout.setContentsMargins(8, 8, 8, 8)
        g_layout.setSpacing(8)

        sec_display = QLabel("Display")
        sec_display.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        g_layout.addWidget(sec_display)

        self._cb_session = QCheckBox("Show match_summary")
        self._cb_roster = QCheckBox("Show lobby_ranks")
        self._cb_mmr = QCheckBox("Show in-game MMR")
        for cb in (self._cb_session, self._cb_roster, self._cb_mmr):
            cb.setStyleSheet(
                "QCheckBox {"
                "  color: #e4eaf4; spacing: 8px;"
                "  background: rgba(40, 52, 72, 220);"
                "  padding: 6px 8px; border-radius: 4px;"
                "  border: 1px solid rgba(80, 110, 150, 90);"
                "}"
                "QCheckBox:hover { background: rgba(50, 64, 88, 255); }"
                "QCheckBox::indicator { width: 16px; height: 16px; }"
            )
        self._cb_session.toggled.connect(self.toggleSession.emit)
        self._cb_roster.toggled.connect(self.toggleRoster.emit)
        self._cb_mmr.toggled.connect(self.toggleMmr.emit)
        g_layout.addWidget(self._cb_session)
        g_layout.addWidget(self._cb_roster)
        g_layout.addWidget(self._cb_mmr)

        sec_theme = QLabel("Theme preset")
        sec_theme.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        g_layout.addWidget(sec_theme)
        self._combo_theme = QComboBox()
        for pid, payload in THEME_PRESETS.items():
            self._combo_theme.addItem(str(payload.get("label") or pid), pid)
        self._combo_theme.currentIndexChanged.connect(self._emit_theme_preset)
        self._style_combo(self._combo_theme)
        g_layout.addWidget(self._combo_theme)

        g_layout.addStretch(1)
        tabs.addTab(tab_global, "Global settings")

        tab_session = QWidget()
        s_layout = QVBoxLayout(tab_session)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(8)
        sec_session = QLabel("match_summary")
        sec_session.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        s_layout.addWidget(sec_session)
        self._session_group, sess_row = self._build_anchor_row("session")
        s_layout.addLayout(sess_row)
        session_opacity_box, self._slider_session_opacity, self._lbl_session_opacity = self._build_opacity_slider(
            "session",
            "Opacity (background + border)",
        )
        s_layout.addWidget(session_opacity_box)
        s_layout.addStretch(1)
        tabs.addTab(tab_session, "Stats Tracker")

        tab_roster = QWidget()
        r_layout = QVBoxLayout(tab_roster)
        r_layout.setContentsMargins(8, 8, 8, 8)
        r_layout.setSpacing(8)
        sec_roster = QLabel("lobby_ranks")
        sec_roster.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        r_layout.addWidget(sec_roster)
        sec_mmr = QLabel("Lobby MMR line")
        sec_mmr.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        r_layout.addWidget(sec_mmr)
        self._combo_roster_mmr = QComboBox()
        for _pid, label in ROSTER_MMR_PRESET_OPTIONS:
            self._combo_roster_mmr.addItem(label, _pid)
        self._combo_roster_mmr.currentIndexChanged.connect(self._emit_roster_mmr_preset)
        self._style_combo(self._combo_roster_mmr)
        r_layout.addWidget(self._combo_roster_mmr)
        self._roster_group, rost_row = self._build_anchor_row("roster")
        r_layout.addLayout(rost_row)
        self._cb_lobby_preview = QCheckBox("Preview lobby overlay (outside match)")
        self._cb_lobby_preview.setStyleSheet(
            "QCheckBox {"
            "  color: #e4eaf4; spacing: 8px;"
            "  background: rgba(40, 52, 72, 220);"
            "  padding: 6px 8px; border-radius: 4px;"
            "  border: 1px solid rgba(80, 110, 150, 90);"
            "}"
            "QCheckBox:hover { background: rgba(50, 64, 88, 255); }"
            "QCheckBox::indicator { width: 16px; height: 16px; }"
        )
        self._cb_lobby_preview.toggled.connect(self.lobbyPreviewToggled.emit)
        r_layout.addWidget(self._cb_lobby_preview)
        roster_opacity_box, self._slider_roster_opacity, self._lbl_roster_opacity = self._build_opacity_slider(
            "roster",
            "Opacity (background + border)",
        )
        r_layout.addWidget(roster_opacity_box)
        r_layout.addStretch(1)
        tabs.addTab(tab_roster, "Lobby Ranks")

        self.setStyleSheet(
            "MenuPanel {"
            "  background-color: rgb(24, 30, 44);"
            "  border: 1px solid rgba(0, 200, 255, 120);"
            "  border-radius: 8px;"
            "}"
        )

        sc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        sc.activated.connect(self._on_escape)

        self.adjustSize()

    def _style_combo(self, combo: QComboBox) -> None:
        combo.setStyleSheet(
            "QComboBox {"
            "  background: rgba(40, 52, 72, 220); color: #e4eaf4;"
            "  border: 1px solid rgba(80, 110, 150, 90); border-radius: 4px;"
            "  padding: 5px 8px; font-size: 10px; min-height: 22px;"
            "}"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView {"
            "  background: rgb(32, 42, 58); color: #e4eaf4; selection-background-color: rgba(0, 100, 140, 200);"
            "}"
        )

    def _build_opacity_slider(self, which: str, title: str) -> tuple[QWidget, QSlider, QLabel]:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        row.addWidget(lbl)
        val = QLabel("100%")
        val.setStyleSheet("color: #e4eaf4; font-size: 9px; background: transparent;")
        row.addWidget(val)
        row.addStretch(1)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 6px; background: rgba(60,80,110,120); border-radius: 3px; }"
            "QSlider::handle:horizontal { width: 12px; margin: -4px 0; background: rgba(0,200,255,200); border-radius: 6px; }"
        )
        slider.valueChanged.connect(lambda v, w=which, vlab=val: self._on_opacity_changed(w, int(v), vlab))

        wrap = QVBoxLayout()
        wrap.setSpacing(4)
        wrap.addLayout(row)
        wrap.addWidget(slider)
        container = QWidget()
        container.setLayout(wrap)
        return container, slider, val

    def _build_anchor_row(self, which: str) -> tuple[QButtonGroup, QHBoxLayout]:
        row = QHBoxLayout()
        row.setSpacing(4)
        group = QButtonGroup(self)
        group.setExclusive(True)

        for i, aid in enumerate(ANCHOR_ORDER):
            b = QPushButton(ANCHOR_LABELS[aid])
            b.setCheckable(True)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton {"
                "  background: rgba(30, 40, 56, 180); color: #c8d8ec;"
                "  border: 1px solid rgba(80, 100, 130, 90); border-radius: 3px;"
                "  font-size: 9px; padding: 2px 4px;"
                "}"
                "QPushButton:checked {"
                "  background: rgba(0, 100, 140, 200); color: #ffffff;"
                "  border: 1px solid rgba(0, 200, 255, 120);"
                "}"
            )
            group.addButton(b, i)
            row.addWidget(b)

        def _on_btn(btn: QAbstractButton, w: str = which) -> None:
            bid = group.id(btn)
            if 0 <= bid < len(ANCHOR_ORDER):
                self.anchorChanged.emit(w, ANCHOR_ORDER[bid])

        group.buttonClicked.connect(_on_btn)
        return group, row

    def _emit_roster_mmr_preset(self, _index: int) -> None:
        pid = self._combo_roster_mmr.currentData()
        if pid:
            self.rosterMmrPresetChanged.emit(str(pid))

    def _emit_theme_preset(self, _index: int) -> None:
        pid = self._combo_theme.currentData()
        if pid:
            self.themePresetChanged.emit(str(pid))

    def _on_opacity_changed(self, which: str, value: int, label: QLabel) -> None:
        label.setText(f"{int(value)}%")
        self.overlayOpacityChanged.emit(which, int(value))

    def _sync_roster_mmr_combo(self) -> None:
        preset = str(self._cfg.get("roster_mmr_preset") or "full").strip().lower()
        self._combo_roster_mmr.blockSignals(True)
        try:
            for i in range(self._combo_roster_mmr.count()):
                if str(self._combo_roster_mmr.itemData(i)) == preset:
                    self._combo_roster_mmr.setCurrentIndex(i)
                    break
            else:
                self._combo_roster_mmr.setCurrentIndex(0)
        finally:
            self._combo_roster_mmr.blockSignals(False)

    def _sync_theme_combo(self) -> None:
        preset = str(self._cfg.get("theme_preset") or "classic").strip().lower()
        self._combo_theme.blockSignals(True)
        try:
            for i in range(self._combo_theme.count()):
                if str(self._combo_theme.itemData(i)) == preset:
                    self._combo_theme.setCurrentIndex(i)
                    break
            else:
                self._combo_theme.setCurrentIndex(0)
        finally:
            self._combo_theme.blockSignals(False)

    def _sync_opacity_sliders(self) -> None:
        s = int(self._cfg.get("session_overlay_opacity", 100) or 100)
        r = int(self._cfg.get("roster_overlay_opacity", 100) or 100)
        s = max(0, min(100, s))
        r = max(0, min(100, r))
        self._slider_session_opacity.blockSignals(True)
        self._slider_roster_opacity.blockSignals(True)
        self._slider_session_opacity.setValue(s)
        self._slider_roster_opacity.setValue(r)
        self._slider_session_opacity.blockSignals(False)
        self._slider_roster_opacity.blockSignals(False)
        self._lbl_session_opacity.setText(f"{s}%")
        self._lbl_roster_opacity.setText(f"{r}%")

    def _sync_anchor_group(self, group: QButtonGroup, anchor: str) -> None:
        group.blockSignals(True)
        try:
            idx = ANCHOR_ORDER.index(anchor) if anchor in ANCHOR_ORDER else 0
            btn = group.button(idx)
            if btn:
                btn.setChecked(True)
        finally:
            group.blockSignals(False)

    def sync_from_app(
        self,
        vis_session: bool,
        vis_roster: bool,
        show_mmr: bool,
        preview_lobby: bool,
    ) -> None:
        self._cb_session.blockSignals(True)
        self._cb_roster.blockSignals(True)
        self._cb_mmr.blockSignals(True)
        self._cb_lobby_preview.blockSignals(True)
        self._cb_session.setChecked(vis_session)
        self._cb_roster.setChecked(vis_roster)
        self._cb_mmr.setChecked(show_mmr)
        self._cb_lobby_preview.setChecked(preview_lobby)
        self._cb_session.blockSignals(False)
        self._cb_roster.blockSignals(False)
        self._cb_mmr.blockSignals(False)
        self._cb_lobby_preview.blockSignals(False)

        sa = str(self._cfg.get("position_session_anchor") or "top-right").lower()
        ra = str(self._cfg.get("position_roster_anchor") or "top-left").lower()
        self._sync_anchor_group(self._session_group, sa)
        self._sync_anchor_group(self._roster_group, ra)
        self._sync_roster_mmr_combo()
        self._sync_theme_combo()
        self._sync_opacity_sliders()

    def is_drag_from_menu_active(self) -> bool:
        return self._drag_from_menu

    def _on_drag_clicked(self) -> None:
        if not self._drag_from_menu:
            self._drag_from_menu = True
            self._btn_drag.setText("Drag overlays: ON")
            self.dragRequested.emit()
        else:
            self._drag_from_menu = False
            self._btn_drag.setText("Drag overlays: OFF")
            self.dragFinished.emit()

    def set_drag_toggle_state(self, enabled: bool) -> None:
        self._drag_from_menu = bool(enabled)
        self._btn_drag.setText("Drag overlays: ON" if self._drag_from_menu else "Drag overlays: OFF")

    def _on_escape(self) -> None:
        self.close_menu()

    def present(self, vis_session: bool, vis_roster: bool, show_mmr: bool, preview_lobby: bool) -> None:
        self.sync_from_app(vis_session, vis_roster, show_mmr, preview_lobby)
        self._btn_drag.setText("Drag overlays: ON" if self._drag_from_menu else "Drag overlays: OFF")
        self.show()
        self.raise_()
        self.activateWindow()
        self._center_on_screen()

    def close_menu(self) -> None:
        self.hide()
        self.menuClosed.emit()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        self.adjustSize()
        screen = resolve_overlay_screen(self._cfg)
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.left() + (geo.width() - self.width()) // 2
        y = geo.top() + (geo.height() - self.height()) // 2
        self.move(max(geo.left(), x), max(geo.top(), y))
