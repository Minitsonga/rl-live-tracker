from pathlib import Path

from rl_live_tracker.stats_api_paths import (
    example_stats_api_ini,
    stats_api_ini_from_exe,
)


def test_stats_api_ini_from_exe_epic_layout():
    exe = Path(
        r"C:\Program Files\Epic Games\rocketleague\TAGame\Binaries\Win64\RocketLeague.exe"
    )
    ini = stats_api_ini_from_exe(exe)
    assert ini == Path(
        r"C:\Program Files\Epic Games\rocketleague\TAGame\Config\DefaultStatsAPI.ini"
    )


def test_example_stats_api_ini_uses_port():
    text = example_stats_api_ini(port=49123)
    assert "Port=49123" in text
    assert "PacketSendRate=2" in text
