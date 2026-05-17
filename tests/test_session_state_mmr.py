from rl_live_tracker.session_state import SessionState, session_mmr_from_entry


def _entry(mmr_2v2: int) -> dict:
    return {"playlists": {"2v2": {"mmr": mmr_2v2}}}


def test_session_mmr_prefers_active_playlist_then_best() -> None:
    entry = {
        "playlists": {"2v2": {"mmr": 1100}, "3v3": {"mmr": 1400}},
        "best": {"mmr": 1400, "playlist": "3v3"},
    }
    assert session_mmr_from_entry(entry, "2v2") == 1100
    assert session_mmr_from_entry(entry, "other") == 1100


def test_post_match_reliable_baseline_updates_last_and_total() -> None:
    session = SessionState()

    delta = session.apply_post_match_trn(
        _entry(1212),
        "2v2",
        frozen_match_start_mmr=1200,
        baseline_reliable=True,
    )

    assert delta == 12
    assert session.last_match_delta == 12
    assert session.current_mmr == 1212
    assert session.session_delta_display("2v2") == 12


def test_post_match_unreliable_baseline_keeps_total_but_hides_last() -> None:
    session = SessionState()

    delta = session.apply_post_match_trn(
        _entry(1230),
        "2v2",
        frozen_match_start_mmr=1200,
        baseline_reliable=False,
    )

    assert delta == 30
    # cumulative session still reflects TRN movement
    assert session.session_delta_display("2v2") == 30
    # but "last" is unknown when baseline was reconstructed
    assert session.last_match_delta is None
    assert session.current_mmr == 1230
