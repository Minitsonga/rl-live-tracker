"""État app à réinitialiser à la fermeture de Rocket League (sans Qt)."""


def clear_post_pending(post_pending: dict) -> None:
    post_pending["active"] = False
    post_pending["baseline_lu"] = ""
    post_pending["playlist"] = ""
    post_pending["baseline_mmr"] = None
    post_pending["baseline_reliable"] = False


def reset_match_app_state(state: dict) -> None:
    state["in_match"] = False
    state["roster"] = []


def test_clear_post_pending() -> None:
    pending = {
        "active": True,
        "baseline_lu": "abc",
        "playlist": "2v2",
        "baseline_mmr": 1200,
        "baseline_reliable": True,
    }
    clear_post_pending(pending)
    assert pending["active"] is False
    assert pending["baseline_lu"] == ""
    assert pending["playlist"] == ""
    assert pending["baseline_mmr"] is None
    assert pending["baseline_reliable"] is False


def test_reset_match_app_state() -> None:
    state = {"in_match": True, "roster": [{"key": "x"}]}
    reset_match_app_state(state)
    assert state["in_match"] is False
    assert state["roster"] == []
