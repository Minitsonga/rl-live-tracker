from rl_live_tracker.render_session import render_session_html
from rl_live_tracker.session_state import SessionState


def _cfg() -> dict:
    return {
        "accent_color": "#00c8ff",
        "text_color": "#f4f7fc",
        "label_color": "#d4e2f4",
        "win_color": "#00e5a0",
        "loss_color": "#ff4060",
        "muted_color": "#b8c6d9",
        "show_mmr_ingame": True,
    }


def test_status_row_shows_playlist_and_connected_in_match() -> None:
    session = SessionState()
    session.active_playlist = "2v2"
    session.stats_connected = True

    html = render_session_html(_cfg(), session, in_match=True)

    assert "2v2" in html
    assert "width:8px; height:8px;" in html
    assert "background:#00e5a0" in html


def test_status_row_shows_menu_and_offline_out_of_match() -> None:
    session = SessionState()
    session.active_playlist = "other"
    session.stats_connected = False

    html = render_session_html(_cfg(), session, in_match=False)

    assert "Menu" in html
    assert "background:#ff4060" in html


def test_status_row_shows_reconnecting_when_in_match_and_disconnected() -> None:
    session = SessionState()
    session.active_playlist = "other"
    session.stats_connected = False

    html = render_session_html(_cfg(), session, in_match=True)

    assert "Other" in html
    assert "background:#ffb347" in html
