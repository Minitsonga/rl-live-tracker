"""Configuration JSON persistante."""
from __future__ import annotations

import json
from typing import Optional

from .applog import warn_log
from .paths import CONFIG_PATH, safe_atomic_write_text


DEFAULT_CONFIG = {
    "_comment": "RL Live Tracker — edit and restart the app.",
    "host": "127.0.0.1",
    "port": 49123,
    "mmr_enabled": True,
    "api_debug_dump": False,
    "self_player_id": None,
    # True = masquer les overlays (session / roster) si RL n'est pas au premier plan (Alt+Tab, bureau…).
    "require_rl_focus": True,
    # Une seule hotkey par défaut : panneau réglages (F5). Les autres listes vides = désactivées.
    "menu_toggle_hotkeys": ["f5"],
    "toggle_hotkeys": [],
    "roster_toggle_hotkeys": [],
    "mmr_tracker_toggle_hotkeys": [],
    "mmr_ingame_toggle_hotkeys": [],
    # Écran pour les ancres (coins) : "primary" | "cursor" | index 0-based (ex. 1 = 2e écran)
    "overlay_screen": "primary",
    "show_mmr_ingame": True,
    # Lobby roster TRN: full | mmr_only | full_2v2_mmr (compact/rank_only → full)
    "roster_mmr_preset": "full",
    "show_session_overlay": True,
    "show_roster_overlay": False,
    # Ancres : top-left | top-right | bottom-left | bottom-right | custom
    "position_session_anchor": "top-right",
    "position_roster_anchor": "top-left",
    "position_session_custom_xy": None,
    "position_roster_custom_xy": None,
    # Legacy (migration uniquement) — préférer *_anchor
    "position_session": "top-right",
    "position_roster": "top-left",
    "margin": 12,
    # Largeur maximale du contenu (les overlays peuvent être plus étroits selon le texte).
    "width_session": 180,
    # Carte session seule : 0 = largeur au contenu (plafonnée par width_session). Entre 0 et 1 = élargir
    # vers le plafond pour que monter width_session (ex. 260) se voie même si le texte est plus étroit.
    "session_width_fill": 0.0,
    "width_roster": 268,
    "background_rgba": [6, 8, 12, 68],
    "border_rgba": [0, 200, 255, 28],
    "border_radius_px": 4,
    "text_color": "#f4f7fc",
    "label_color": "#d4e2f4",
    "accent_color": "#00c8ff",
    "win_color": "#00e5a0",
    "loss_color": "#ff4060",
    "muted_color": "#b8c6d9",
    "font_family": "Segoe UI",
    "font_size": 10,
    "overlay_padding_px": [4, 6],
    "overlays_visible_default": True,
    "roster_visible_default": False,
}


def _migrate_loaded(cfg: dict, loaded: Optional[dict]) -> bool:
    """Retourne True si la config doit être réécrite sur disque."""
    changed = False
    if loaded is None:
        return False
    # menu_toggle_hotkeys depuis toggle_hotkeys legacy
    if "menu_toggle_hotkeys" not in loaded:
        th = loaded.get("toggle_hotkeys")
        if isinstance(th, list) and th:
            cfg["menu_toggle_hotkeys"] = [str(th[0]).lower()]
        else:
            cfg["menu_toggle_hotkeys"] = ["f5"]
        changed = True
    # Ancres : d'abord custom_xy explicite, sinon position_session / position_roster legacy
    for name, default_anchor in (("session", "top-right"), ("roster", "top-left")):
        anchor_key = f"position_{name}_anchor"
        xy_key = f"position_{name}_custom_xy"
        if anchor_key not in loaded:
            xy = loaded.get(xy_key)
            if (
                isinstance(xy, (list, tuple))
                and len(xy) == 2
                and all(isinstance(v, (int, float)) for v in xy)
            ):
                cfg[anchor_key] = "custom"
            else:
                legacy_key = "position_session" if name == "session" else "position_roster"
                ps = str(loaded.get(legacy_key) or default_anchor).lower()
                if ps == "top-center":
                    ps = "top-right"
                if ps not in ("top-left", "top-right", "bottom-left", "bottom-right", "custom"):
                    ps = default_anchor
                cfg[anchor_key] = ps
            changed = True
    if "show_session_overlay" not in loaded:
        cfg["show_session_overlay"] = bool(loaded.get("overlays_visible_default", True))
        changed = True
    if "show_roster_overlay" not in loaded:
        cfg["show_roster_overlay"] = bool(loaded.get("roster_visible_default", False))
        changed = True
    # Ancien défaut session = F9 → F5
    if cfg.get("toggle_hotkeys") == ["f9"]:
        cfg["toggle_hotkeys"] = []
        cfg["menu_toggle_hotkeys"] = ["f5"]
        changed = True
    return changed


def save_config(cfg: dict) -> None:
    safe_atomic_write_text(CONFIG_PATH, json.dumps(cfg, indent=2, ensure_ascii=False), "config")


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    loaded: Optional[dict] = None
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (json.JSONDecodeError, OSError) as e:
            warn_log(f"config file unreadable: {e}")
    needs_rewrite = loaded is None or any(k not in loaded for k in DEFAULT_CONFIG)
    if _migrate_loaded(cfg, loaded):
        needs_rewrite = True
    if needs_rewrite:
        save_config(cfg)
    return cfg
