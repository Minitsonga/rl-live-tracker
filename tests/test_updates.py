from rl_live_tracker.updates import is_newer_version


def test_is_newer_version_release_after_beta() -> None:
    assert is_newer_version("1.0.0", "1.0.0-beta.2") is True


def test_is_newer_version_same_beta() -> None:
    assert is_newer_version("1.0.0-beta.2", "1.0.0-beta.2") is False


def test_is_newer_version_patch() -> None:
    assert is_newer_version("1.0.1", "1.0.0-beta.2") is True


def test_is_newer_version_older() -> None:
    assert is_newer_version("1.0.0-beta.1", "1.0.0-beta.2") is False
