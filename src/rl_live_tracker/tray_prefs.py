"""Logique tray (fermeture / minimisation) sans dépendance Qt."""
from __future__ import annotations

from enum import Enum
from typing import Optional


class TrayWindowAction(str, Enum):
    QUIT = "quit"
    HIDE = "hide"
    CANCEL = "cancel"


def resolve_minimize_action(cfg: dict) -> Optional[TrayWindowAction]:
    """
    None = afficher le dialogue de première utilisation.
    Sinon action directe (hide ou quit).
    """
    if bool(cfg.get("minimize_quits_app")):
        return TrayWindowAction.QUIT
    if not bool(cfg.get("tray_minimize_prompt_done")):
        return None
    return TrayWindowAction.HIDE


def resolve_close_action(cfg: dict) -> Optional[TrayWindowAction]:
    """
    None = afficher le dialogue de première utilisation (si close_to_tray est false).
    """
    if bool(cfg.get("close_to_tray")):
        return TrayWindowAction.HIDE
    if not bool(cfg.get("tray_close_prompt_done")):
        return None
    if bool(cfg.get("tray_close_default_quit", True)):
        return TrayWindowAction.QUIT
    return TrayWindowAction.HIDE


def apply_minimize_choice(cfg: dict, action: TrayWindowAction, *, remember: bool) -> None:
    if action == TrayWindowAction.CANCEL:
        return
    if remember:
        cfg["tray_minimize_prompt_done"] = True
        cfg["minimize_quits_app"] = action == TrayWindowAction.QUIT


def apply_close_choice(cfg: dict, action: TrayWindowAction, *, remember: bool) -> None:
    if action == TrayWindowAction.CANCEL:
        return
    if action == TrayWindowAction.HIDE:
        cfg["close_to_tray"] = True
    if remember:
        cfg["tray_close_prompt_done"] = True
        cfg["tray_close_default_quit"] = action == TrayWindowAction.QUIT
