from rl_live_tracker.tray_prefs import (
    TrayWindowAction,
    apply_close_choice,
    apply_minimize_choice,
    resolve_close_action,
    resolve_minimize_action,
)


def _base_cfg() -> dict:
    return {
        "close_to_tray": False,
        "tray_minimize_prompt_done": False,
        "tray_close_prompt_done": False,
        "minimize_quits_app": False,
        "tray_close_default_quit": True,
    }


def test_resolve_close_hide_when_close_to_tray():
    cfg = _base_cfg()
    cfg["close_to_tray"] = True
    assert resolve_close_action(cfg) == TrayWindowAction.HIDE


def test_resolve_close_prompt_when_not_done():
    cfg = _base_cfg()
    assert resolve_close_action(cfg) is None


def test_resolve_close_quit_after_onboarding_default():
    cfg = _base_cfg()
    cfg["tray_close_prompt_done"] = True
    cfg["tray_close_default_quit"] = True
    assert resolve_close_action(cfg) == TrayWindowAction.QUIT


def test_resolve_minimize_prompt_first_time():
    cfg = _base_cfg()
    assert resolve_minimize_action(cfg) is None


def test_apply_close_hide_enables_close_to_tray():
    cfg = _base_cfg()
    apply_close_choice(cfg, TrayWindowAction.HIDE, remember=True)
    assert cfg["close_to_tray"] is True
    assert cfg["tray_close_prompt_done"] is True
    assert cfg["tray_close_default_quit"] is False


def test_apply_minimize_remember_quit():
    cfg = _base_cfg()
    apply_minimize_choice(cfg, TrayWindowAction.QUIT, remember=True)
    assert cfg["minimize_quits_app"] is True
    assert resolve_minimize_action(cfg) == TrayWindowAction.QUIT
