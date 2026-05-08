"""Configuration JSON persistante."""
from __future__ import annotations

import json
from typing import Optional

from .applog import warn_log
from .paths import CONFIG_PATH, safe_atomic_write_text

THEME_PRESETS: dict[str, dict] = {
    "pro_classic": {
        "label": "Pro Classic",
        "background_rgba": [8, 12, 18, 86],
        "border_rgba": [0, 170, 255, 56],
        "border_radius_px": 4,
        "overlay_padding_px": [4, 6],
        "font_size": 10,
        "text_color": "#f4f7fc",
        "label_color": "#d4e2f4",
        "accent_color": "#00c8ff",
        "win_color": "#00e5a0",
        "loss_color": "#ff4060",
        "muted_color": "#b8c6d9",
    },
    "glass_minimal": {
        "label": "Glass Minimal",
        "background_rgba": [16, 20, 30, 54],
        "border_rgba": [220, 230, 255, 18],
        "border_radius_px": 10,
        "overlay_padding_px": [6, 10],
        "font_size": 9,
        "text_color": "#f5f8ff",
        "label_color": "#d6dff2",
        "accent_color": "#9bc6ff",
        "win_color": "#66e4b5",
        "loss_color": "#ff7b8f",
        "muted_color": "#a6b2c8",
    },
    "esports_hud": {
        "label": "Esports HUD",
        "background_rgba": [5, 9, 14, 116],
        "border_rgba": [0, 250, 255, 90],
        "border_radius_px": 2,
        "overlay_padding_px": [3, 5],
        "font_size": 11,
        "text_color": "#e8fcff",
        "label_color": "#bdeeff",
        "accent_color": "#00f6ff",
        "win_color": "#09f0aa",
        "loss_color": "#ff4f73",
        "muted_color": "#98b7ca",
    },
    "mono_terminal": {
        "label": "Mono Terminal",
        "background_rgba": [12, 18, 12, 120],
        "border_rgba": [138, 255, 138, 55],
        "border_radius_px": 0,
        "overlay_padding_px": [3, 5],
        "font_size": 10,
        "font_family": "Consolas",
        "text_color": "#dcffdc",
        "label_color": "#bdf0bd",
        "accent_color": "#9aff9a",
        "win_color": "#7dff9c",
        "loss_color": "#ff8f9e",
        "muted_color": "#9ec49e",
    },
}


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
    "theme_preset": "pro_classic",
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


def apply_theme_preset(cfg: dict, preset: str) -> bool:
    pid = str(preset or "").strip().lower()
    p = THEME_PRESETS.get(pid)
    if not p:
        return False
    cfg["theme_preset"] = pid
    for key in (
        "background_rgba",
        "border_rgba",
        "border_radius_px",
        "overlay_padding_px",
        "font_size",
        "font_family",
        "text_color",
        "label_color",
        "accent_color",
        "win_color",
        "loss_color",
        "muted_color",
    ):
        if key in p:
            cfg[key] = p[key]
    return True


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
    if "theme_preset" not in loaded:
        cfg["theme_preset"] = "pro_classic"
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
    # Keep visual tokens aligned with selected preset.
    if apply_theme_preset(cfg, str(cfg.get("theme_preset") or "pro_classic")):
        if loaded is not None:
            for key in (
                "background_rgba",
                "border_rgba",
                "border_radius_px",
                "overlay_padding_px",
                "font_size",
                "font_family",
                "text_color",
                "label_color",
                "accent_color",
                "win_color",
                "loss_color",
                "muted_color",
            ):
                if loaded.get(key) != cfg.get(key):
                    needs_rewrite = True
    if needs_rewrite:
        save_config(cfg)
    return cfg
