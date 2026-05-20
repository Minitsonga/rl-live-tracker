from rl_live_tracker.stats_api_paths import (
    STATS_API_INI_RELATIVE,
    example_stats_api_ini,
)


def test_stats_api_ini_relative_is_documentation_only():
    assert STATS_API_INI_RELATIVE == "TAGame/Config/DefaultStatsAPI.ini"
    assert "/" in STATS_API_INI_RELATIVE
    assert "C:" not in STATS_API_INI_RELATIVE


def test_example_stats_api_ini_uses_port():
    text = example_stats_api_ini(port=49123)
    assert "Port=49123" in text
    assert "PacketSendRate=2" in text
