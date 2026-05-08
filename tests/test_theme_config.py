from copy import deepcopy

from rl_live_tracker.config import DEFAULT_CONFIG, THEME_PRESETS, apply_theme_preset


def test_apply_theme_preset_updates_visual_keys() -> None:
    cfg = deepcopy(DEFAULT_CONFIG)

    changed = apply_theme_preset(cfg, "broadcast_panel")

    assert changed is True
    assert cfg["theme_preset"] == "broadcast_panel"
    preset = THEME_PRESETS["broadcast_panel"]
    assert cfg["background_rgba"] == preset["background_rgba"]
    assert cfg["border_rgba"] == preset["border_rgba"]
    assert cfg["accent_color"] == preset["accent_color"]


def test_apply_theme_preset_rejects_unknown_id() -> None:
    cfg = deepcopy(DEFAULT_CONFIG)
    before = dict(cfg)

    changed = apply_theme_preset(cfg, "does-not-exist")

    assert changed is False
    assert cfg == before
