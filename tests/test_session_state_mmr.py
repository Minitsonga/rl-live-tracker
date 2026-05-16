from rl_live_tracker.session_state import SessionState


def _entry(mmr_2v2: int) -> dict:
    return {"playlists": {"2v2": {"mmr": mmr_2v2}}}


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
