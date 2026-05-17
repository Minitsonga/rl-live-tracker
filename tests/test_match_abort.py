from rl_live_tracker.match_outcome import should_count_match_outcome
from rl_live_tracker.session_state import SessionState


def test_should_count_match_outcome_only_when_match_ended() -> None:
    assert should_count_match_outcome(match_ended_recorded=True) is True
    assert should_count_match_outcome(match_ended_recorded=False) is False


def test_aborted_match_does_not_increment_losses() -> None:
    session = SessionState()
    session.active_playlist = "2v2"
    session.on_match_ended_outcome(True)
    session.on_match_ended_outcome(True)
    assert session.wins == 2

    session.active_playlist = "2v2"
    losses_before = session.losses
    session.clear_active_match_baseline()
    assert session.losses == losses_before
    assert session.wins == 2


def test_match_ended_still_counts_loss() -> None:
    session = SessionState()
    session.active_playlist = "1v1"
    session.on_match_ended_outcome(False)
    assert session.losses == 1
