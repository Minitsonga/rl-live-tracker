"""Configuration JSON persistante."""
from __future__ import annotations

import json
from typing import Optional

from .applog import warn_log
from .paths import CONFIG_PATH, safe_atomic_write_text

THEME_PRESETS: dict[str, dict] = {
    "classic": {
        "label": "Classic",
        "background_rgba": [6, 8, 12, 68],
        "border_rgba": [0, 200, 255, 28],
        "text_color": "#f4f7fc",
        "label_color": "#d4e2f4",
        "accent_color": "#00c8ff",
        "win_color": "#00e5a0",
        "loss_color": "#ff4060",
        "muted_color": "#b8c6d9",
    },
    "rocketstats_dark": {
        "label": "RocketStats Dark",
        "background_rgba": [8, 11, 16, 92],
        "border_rgba": [48, 134, 255, 58],
        "text_color": "#edf4ff",
        "label_color": "#c8d7ef",
        "accent_color": "#38b6ff",
        "win_color": "#22e29f",
        "loss_color": "#ff617a",
        "muted_color": "#9eb1ca",
    },
    "neon_cyan": {
        "label": "Neon Cyan",
        "background_rgba": [4, 10, 15, 90],
        "border_rgba": [0, 229, 255, 72],
        "text_color": "#e8f7ff",
        "label_color": "#b7ddef",
        "accent_color": "#00e5ff",
        "win_color": "#00f5b0",
        "loss_color": "#ff4b7d",
        "muted_color": "#9fc2d4",
    },
    "stealth_gray": {
        "label": "Stealth Gray",
        "background_rgba": [12, 14, 18, 84],
        "border_rgba": [118, 128, 146, 42],
        "text_color": "#edf0f6",
        "label_color": "#c9ceda",
        "accent_color": "#9fb8ff",
        "win_color": "#48d89f",
        "loss_color": "#ff6a78",
        "muted_color": "#a7afbf",
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
    "theme_preset": "classic",
    "session_overlay_opacity": 100,
    "roster_overlay_opacity": 100,
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
        cfg["theme_preset"] = "classic"
        changed = True
    # clamp per-overlay opacity sliders
    for k in ("session_overlay_opacity", "roster_overlay_opacity"):
        raw = cfg.get(k, 100)
        try:
            v = int(raw)
        except (TypeError, ValueError):
            v = 100
        vv = max(10, min(100, v))
        if raw != vv:
            cfg[k] = vv
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
    if apply_theme_preset(cfg, str(cfg.get("theme_preset") or "classic")):
        if loaded is not None:
            for key in (
                "background_rgba",
                "border_rgba",
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
