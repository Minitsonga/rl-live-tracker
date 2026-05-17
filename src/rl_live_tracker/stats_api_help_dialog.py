"""Stats API setup help — shown from the main app window (not F5 overlays)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .stats_api_paths import (
    example_stats_api_ini,
    resolve_default_stats_api_ini,
    stats_api_config_dir,
)


class StatsApiHelpDialog(QDialog):
    def __init__(self, cfg: dict, parent=None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle("RL Live Tracker — Stats API")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "Match stats use Rocket League's Stats API (TCP). "
            "Edit DefaultStatsAPI.ini in your game folder, then restart Rocket League."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel("File location"))
        self._path_label = QLabel("")
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._path_label)

        btn_row = QHBoxLayout()
        btn_open_config = QPushButton("Open Config folder")
        btn_open_ini = QPushButton("Open DefaultStatsAPI.ini")
        btn_open_config.clicked.connect(self._open_config_folder)
        btn_open_ini.clicked.connect(self._open_ini)
        btn_row.addWidget(btn_open_config)
        btn_row.addWidget(btn_open_ini)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("Example contents (Port must match data/config.json)"))
        self._example = QPlainTextEdit()
        self._example.setReadOnly(True)
        self._example.setMaximumHeight(80)
        layout.addWidget(self._example)

        hint = QLabel("Launch Rocket League once if the path is unknown.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.refresh()

    def refresh(self) -> None:
        port = int(self._cfg.get("port") or 49123)
        self._example.setPlainText(example_stats_api_ini(port=port))
        ini = resolve_default_stats_api_ini()
        if ini is not None:
            status = "found" if ini.is_file() else "not found yet — create it in Config"
            self._path_label.setText(f"{ini}\n({status})")
        else:
            self._path_label.setText(
                "Could not locate Rocket League.\n"
                "Start the game, or install under Epic Games / Steam default paths."
            )

    @staticmethod
    def _open_path(path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(path)])

    def _open_config_folder(self) -> None:
        ini = resolve_default_stats_api_ini()
        folder = stats_api_config_dir(ini)
        if folder is not None and folder.is_dir():
            self._open_path(folder)
            return
        if ini is not None:
            ini.parent.mkdir(parents=True, exist_ok=True)
            self._open_path(ini.parent)

    def _open_ini(self) -> None:
        ini = resolve_default_stats_api_ini()
        if ini is None:
            return
        if ini.is_file():
            self._open_path(ini)
            return
        ini.parent.mkdir(parents=True, exist_ok=True)
        ini.write_text(
            example_stats_api_ini(port=int(self._cfg.get("port") or 49123)),
            encoding="utf-8",
        )
        self.refresh()
        self._open_path(ini)
