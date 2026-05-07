from copy import deepcopy

from rl_live_tracker.config import DEFAULT_CONFIG, _migrate_loaded


def test_migrate_legacy_hotkeys_and_overlays() -> None:
    loaded = {
        "toggle_hotkeys": ["f9"],
        "position_session": "top-center",
        "position_roster": "bottom-left",
        "overlays_visible_default": False,
        "roster_visible_default": True,
    }
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.update(loaded)

    changed = _migrate_loaded(cfg, loaded)

    assert changed is True
    assert cfg["menu_toggle_hotkeys"] == ["f5"]
    assert cfg["toggle_hotkeys"] == []
    assert cfg["position_session_anchor"] == "top-right"
    assert cfg["position_roster_anchor"] == "bottom-left"
    assert cfg["show_session_overlay"] is False
    assert cfg["show_roster_overlay"] is True


def test_migrate_prefers_custom_coordinates() -> None:
    loaded = {
        "position_session_custom_xy": [200, 350],
        "position_roster_custom_xy": [10, 40],
    }
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.update(loaded)

    changed = _migrate_loaded(cfg, loaded)

    assert changed is True
    assert cfg["position_session_anchor"] == "custom"
    assert cfg["position_roster_anchor"] == "custom"
