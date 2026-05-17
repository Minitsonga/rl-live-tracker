from unittest.mock import MagicMock

from rl_live_tracker.stats_client import StatsClient


def test_resume_restarts_dead_worker_thread():
    client = StatsClient("127.0.0.1", 49123)
    client._started = True
    client._thread = MagicMock()
    client._thread.is_alive.return_value = False
    client._paused = True

    client.resume()

    assert client._paused is False
    assert client._started is True
