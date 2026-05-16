from rl_live_tracker.match_helpers import extract_winner_team_num_from_payload


def test_extracts_direct_winner_team_num() -> None:
    payload = {"WinnerTeamNum": "1"}
    assert extract_winner_team_num_from_payload(payload) == 1


def test_extracts_from_nested_game_block() -> None:
    payload = {"Game": {"Results": {"WinningTeamNum": 0}}}
    assert extract_winner_team_num_from_payload(payload) == 0


def test_extracts_from_named_winner_and_teams() -> None:
    payload = {
        "Game": {
            "Winner": "Blue",
            "Teams": [{"Name": "Blue", "TeamNum": 0}, {"Name": "Orange", "TeamNum": 1}],
        }
    }
    assert extract_winner_team_num_from_payload(payload) == 0
