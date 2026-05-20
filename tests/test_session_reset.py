from rl_live_tracker.session_state import SessionState


def test_reset_session_clears_wl_streaks_and_mmr_cumul() -> None:
    session = SessionState()
    session.active_playlist = "2v2"
    session.on_match_ended_outcome(True)
    session.on_match_ended_outcome(False)
    assert session.wins == 1
    assert session.losses == 1
    assert session.win_streak == 0
    assert session.loss_streak == 1

    session.active_playlist = "1v1"
    session.on_match_ended_outcome(True)
    session.current_mmr = 1500
    session.last_completed_mmr_delta = 12
    session.mmr_session_start["1v1"] = 1488
    pl = session._pl("1v1")
    pl.mmr_delta_session = 12

    session.reset_session()

    assert session.active_playlist == "other"
    assert session.self_name is None
    assert session.current_mmr is None
    assert session.last_completed_mmr_delta is None
    assert session.mmr_session_start == {}
    assert session.session_delta_by_playlist() == {}

    session.active_playlist = "2v2"
    assert session.wins == 0
    assert session.losses == 0
    session.active_playlist = "1v1"
    assert session.wins == 0


def test_reset_counters_delegates_to_reset_session() -> None:
    session = SessionState()
    session.active_playlist = "3v3"
    session.on_match_ended_outcome(True)
    session.reset_counters()
    session.active_playlist = "3v3"
    assert session.wins == 0
