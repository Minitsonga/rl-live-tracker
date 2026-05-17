from pathlib import Path, PureWindowsPath

from rl_live_tracker.stats_api_paths import (
    STATS_API_INI_NAME,
    example_stats_api_ini,
    stats_api_ini_from_exe,
)

_EPIC_EXE = PureWindowsPath(
    r"C:\Program Files\Epic Games\rocketleague\TAGame\Binaries\Win64\RocketLeague.exe"
)
_EPIC_INI = PureWindowsPath(
    r"C:\Program Files\Epic Games\rocketleague\TAGame\Config\DefaultStatsAPI.ini"
)


def test_stats_api_ini_from_exe_epic_layout():
    ini = stats_api_ini_from_exe(Path(_EPIC_EXE))
    assert ini == _EPIC_INI
    assert ini.name == STATS_API_INI_NAME
    assert ini.parent.name == "Config"
    assert ini.parent.parent.name == "TAGame"


def test_example_stats_api_ini_uses_port():
    text = example_stats_api_ini(port=49123)
    assert "Port=49123" in text
    assert "PacketSendRate=2" in text
