from rl_live_tracker.match_outcome import should_ignore_late_match_ended
from rl_live_tracker.session_state import SessionState


def test_should_ignore_late_match_ended_when_outcome_already_recorded() -> None:
    assert should_ignore_late_match_ended(match_outcome_recorded=True) is True
    assert should_ignore_late_match_ended(match_outcome_recorded=False) is False


def test_destroy_without_end_counts_as_loss() -> None:
    session = SessionState()
    session.active_playlist = "2v2"
    session.on_match_ended_outcome(False)
    assert session.losses == 1
    assert session.wins == 0


def test_late_match_ended_after_synthetic_loss_does_not_flip_to_win() -> None:
    """Simule destroy→loss puis MatchEnded tardif : ne doit pas ajouter un W."""
    session = SessionState()
    session.active_playlist = "1v1"
    session.on_match_ended_outcome(False)
    losses_after_destroy = session.losses
    if should_ignore_late_match_ended(match_outcome_recorded=True):
        pass
    else:
        session.on_match_ended_outcome(True)
    assert session.losses == losses_after_destroy
    assert session.wins == 0


def test_match_ended_still_counts_loss() -> None:
    session = SessionState()
    session.active_playlist = "1v1"
    session.on_match_ended_outcome(False)
    assert session.losses == 1
