"""F5 settings panel: visibility, corner anchors + custom, mouse drag mode."""
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
    QVBoxLayout,
    QWidget,
)

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

        sec1 = QLabel("Display")
        sec1.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; background: transparent;")
        root.addWidget(sec1)

        self._cb_session = QCheckBox("Session win/loss card")
        self._cb_roster = QCheckBox("Lobby roster (ranks)")
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
        root.addWidget(self._cb_session)
        root.addWidget(self._cb_roster)
        root.addWidget(self._cb_mmr)

        sec_mmr = QLabel("Lobby MMR line")
        sec_mmr.setStyleSheet(
            "color: #b8d4f0; font-size: 9px; font-weight: bold; margin-top: 4px; background: transparent;"
        )
        root.addWidget(sec_mmr)
        self._combo_roster_mmr = QComboBox()
        self._combo_roster_mmr.blockSignals(True)
        for _pid, label in ROSTER_MMR_PRESET_OPTIONS:
            self._combo_roster_mmr.addItem(label, _pid)
        self._combo_roster_mmr.blockSignals(False)
        self._combo_roster_mmr.setStyleSheet(
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
        self._combo_roster_mmr.currentIndexChanged.connect(self._emit_roster_mmr_preset)
        root.addWidget(self._combo_roster_mmr)

        sec2 = QLabel("Position — session")
        sec2.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; margin-top: 4px; background: transparent;")
        root.addWidget(sec2)
        self._session_group, sess_row = self._build_anchor_row("session")
        root.addLayout(sess_row)

        sec3 = QLabel("Position — roster")
        sec3.setStyleSheet("color: #b8d4f0; font-size: 9px; font-weight: bold; margin-top: 4px; background: transparent;")
        root.addWidget(sec3)
        self._roster_group, rost_row = self._build_anchor_row("roster")
        root.addLayout(rost_row)

        self._btn_drag = QPushButton("Drag to reposition…")
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
    ) -> None:
        self._cb_session.blockSignals(True)
        self._cb_roster.blockSignals(True)
        self._cb_mmr.blockSignals(True)
        self._cb_session.setChecked(vis_session)
        self._cb_roster.setChecked(vis_roster)
        self._cb_mmr.setChecked(show_mmr)
        self._cb_session.blockSignals(False)
        self._cb_roster.blockSignals(False)
        self._cb_mmr.blockSignals(False)

        sa = str(self._cfg.get("position_session_anchor") or "top-right").lower()
        ra = str(self._cfg.get("position_roster_anchor") or "top-left").lower()
        self._sync_anchor_group(self._session_group, sa)
        self._sync_anchor_group(self._roster_group, ra)
        self._sync_roster_mmr_combo()

    def is_drag_from_menu_active(self) -> bool:
        return self._drag_from_menu

    def _on_drag_clicked(self) -> None:
        if not self._drag_from_menu:
            self._drag_from_menu = True
            self._btn_drag.setText("Finish dragging")
            self.dragRequested.emit()
        else:
            self._drag_from_menu = False
            self._btn_drag.setText("Drag to reposition…")
            self.dragFinished.emit()

    def _on_escape(self) -> None:
        self.close_menu()

    def present(self, vis_session: bool, vis_roster: bool, show_mmr: bool) -> None:
        self.sync_from_app(vis_session, vis_roster, show_mmr)
        self.show()
        self.raise_()
        self.activateWindow()
        self._center_on_screen()

    def close_menu(self) -> None:
        had_drag = self._drag_from_menu
        if had_drag:
            self._drag_from_menu = False
            self._btn_drag.setText("Drag to reposition…")
        self.hide()
        self.menuClosed.emit()
        # Après hide() : évite la réentrance si dragFinished déclenche _do_refresh → _sync (focus perdu).
        if had_drag:
            self.dragFinished.emit()

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
