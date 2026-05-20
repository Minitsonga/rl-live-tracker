"""Police et stylesheet communs pour les fenêtres app (hub, Help, About)."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

_DIALOG_STYLESHEET = """
QDialog, QMessageBox {
    background-color: #181c2c;
    color: #e4eaf4;
}
QLabel {
    color: #e4eaf4;
    font-size: 10pt;
}
QPlainTextEdit {
    background-color: #0f1218;
    color: #e4eaf4;
    border: 1px solid #2a3348;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 9pt;
}
QPushButton {
    background-color: #252b3d;
    color: #e4eaf4;
    border: 1px solid #3a4560;
    padding: 6px 14px;
    border-radius: 4px;
    font-size: 10pt;
}
QPushButton:hover {
    background-color: #2f3649;
}
QPushButton:pressed {
    background-color: #1a1f2e;
}
QMenuBar {
    background-color: #181c2c;
    color: #e4eaf4;
}
QMenuBar::item:selected {
    background-color: #252b3d;
}
QMenu {
    background-color: #181c2c;
    color: #e4eaf4;
    border: 1px solid #2a3348;
}
QMenu::item:selected {
    background-color: #252b3d;
}
QMainWindow {
    background-color: #181c2c;
    color: #e4eaf4;
}
"""


def app_font() -> QFont:
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    return font


def apply_app_theme(app: QApplication) -> None:
    app.setFont(app_font())
    app.setStyleSheet(_DIALOG_STYLESHEET)
