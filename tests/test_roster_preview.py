from rl_live_tracker.render_roster import render_roster_preview_html


def test_roster_preview_html_contains_sample_teams() -> None:
    cfg = {
        "show_mmr_ingame": True,
        "roster_mmr_preset": "full",
        "muted_color": "#b8c6d9",
        "accent_color": "#00c8ff",
    }

    html = render_roster_preview_html(cfg)

    assert "BLUE" in html
    assert "ORANGE" in html
    assert "Blue One" in html
    assert "Orange Two" in html
    assert "1V1" in html
    assert "2v2 :" in html


def test_roster_preview_respects_mmr_only_preset() -> None:
    cfg = {
        "show_mmr_ingame": True,
        "roster_mmr_preset": "mmr_only",
        "muted_color": "#b8c6d9",
        "accent_color": "#00c8ff",
    }

    html = render_roster_preview_html(cfg)

    assert "1V1" in html
    assert "1v1 :" in html
    assert "2v2 :" in html


def test_roster_preview_full_2v2_mmr_keeps_secondary_2v2() -> None:
    cfg = {
        "show_mmr_ingame": True,
        "roster_mmr_preset": "full_2v2_mmr",
        "muted_color": "#b8c6d9",
        "accent_color": "#00c8ff",
    }

    html = render_roster_preview_html(cfg)

    assert "1V1" in html
    assert "Div" in html
    assert "2v2 :" in html
