"""Stats API setup help — guide only; no access to game install files."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .stats_api_paths import STATS_API_INI_RELATIVE, example_stats_api_ini


class StatsApiHelpDialog(QDialog):
    def __init__(self, cfg: dict, parent=None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle("RL Live Tracker — Stats API setup")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "RL Live Tracker reads match events over TCP (127.0.0.1). "
            "Rocket League must export them via DefaultStatsAPI.ini — "
            "you create that file yourself in the game folder. "
            "This app only reads and writes its own data/ and logs/ folders."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #e4eaf4; font-size: 10pt;")
        layout.addWidget(intro)

        steps = QLabel(
            "<b>Setup steps</b><br>"
            "1. Open your Rocket League install (Epic or Steam → "
            "&quot;Browse local files&quot; or similar).<br>"
            f"2. Go to <code>{STATS_API_INI_RELATIVE}</code> "
            "(path is always under the game root, not your PC username).<br>"
            "3. Create or edit <code>DefaultStatsAPI.ini</code> using the example below.<br>"
            f"4. Set <code>Port=</code> to the same value as this tracker "
            f"(<b>{int(self._cfg.get('port') or 49123)}</b> in data/config.json).<br>"
            "5. Save the file and <b>restart Rocket League</b>.<br>"
            "6. Start RL Live Tracker while you play (borderless window recommended)."
        )
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        steps.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        steps.setStyleSheet("color: #e4eaf4; font-size: 10pt;")
        layout.addWidget(steps)

        example_lbl = QLabel("Example DefaultStatsAPI.ini")
        example_lbl.setStyleSheet("color: #c8d0e0; font-size: 10pt;")
        layout.addWidget(example_lbl)
        self._example = QPlainTextEdit()
        self._example.setReadOnly(True)
        self._example.setMaximumHeight(72)
        layout.addWidget(self._example)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy example")
        btn_copy.clicked.connect(self._copy_example)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.refresh()

    def refresh(self) -> None:
        port = int(self._cfg.get("port") or 49123)
        self._example.setPlainText(example_stats_api_ini(port=port))

    def _copy_example(self) -> None:
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText(self._example.toPlainText())
