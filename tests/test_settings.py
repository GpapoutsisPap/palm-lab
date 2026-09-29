"""Tests for user settings."""

import re
from pathlib import Path

import pytest

from palm_lab.settings import (
    Settings,
    SettingsError,
    load_settings,
    save_settings,
    settings_from_data,
)
from palm_lab.state import DEFAULT_COOLDOWN_SECONDS, DEFAULT_DWELL_SECONDS


def test_defaults_match_the_state_machine() -> None:
    """Out of the box, the window shows the timings the engine already uses."""
    settings = Settings()
    assert settings.camera_index == 0
    assert settings.dwell_seconds == DEFAULT_DWELL_SECONDS
    assert settings.cooldown_seconds == DEFAULT_COOLDOWN_SECONDS
    assert settings.sounds is True


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    """First run has no settings file yet, and that is fine."""
    assert load_settings(tmp_path / "settings.toml") == Settings()


def test_round_trip_through_disk(tmp_path: Path) -> None:
    """What the window saves is exactly what loads next time."""
    path = tmp_path / "deep" / "settings.toml"
    chosen = Settings(camera_index=1, dwell_seconds=1.2, cooldown_seconds=3.0, sounds=False)
    save_settings(chosen, path)
    assert load_settings(path) == chosen
    assert list(path.parent.iterdir()) == [path]


def test_partial_data_keeps_defaults_for_the_rest() -> None:
    """A settings file with one key is not an error."""
    assert settings_from_data({"camera_index": 2}) == Settings(camera_index=2)


def test_integers_are_accepted_for_times() -> None:
    """TOML writes 2 and 2.0 differently; both mean two seconds."""
    settings = settings_from_data({"dwell_seconds": 2})
    assert settings.dwell_seconds == 2.0


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"camera_index": -1}, "between 0 and"),
        ({"camera_index": 1.5}, "whole number"),
        ({"camera_index": True}, "whole number"),
        ({"dwell_seconds": 0.0}, "'dwell_seconds' must be between"),
        ({"dwell_seconds": 99}, "'dwell_seconds' must be between"),
        ({"dwell_seconds": "slow"}, "must be a number"),
        ({"cooldown_seconds": -1}, "'cooldown_seconds' must be between"),
        ({"cooldown_seconds": False}, "must be a number"),
        ({"sounds": 1}, "'sounds' must be true or false"),
        ({"sounds": "yes"}, "'sounds' must be true or false"),
        ({"volume": 3}, "Unknown setting 'volume'"),
        ({"close_action": "minimize"}, "'close_action' must be one of: ask, background, quit"),
        ({"close_action": True}, "'close_action' must be one of"),
    ],
)
def test_bad_values_are_rejected(data: dict[str, object], expected: str) -> None:
    """Each bad value gets a message naming the setting and the problem."""
    with pytest.raises(SettingsError, match=re.escape(expected)):
        settings_from_data(data)


def test_malformed_file_is_reported(tmp_path: Path) -> None:
    """A broken file raises rather than silently resetting the user's choices."""
    path = tmp_path / "settings.toml"
    path.write_text("camera_index = [", encoding="utf-8")
    with pytest.raises(SettingsError, match="not valid TOML"):
        load_settings(path)


def test_sounds_are_written_as_toml_booleans(tmp_path: Path) -> None:
    """The file stays readable and editable by hand."""
    path = save_settings(Settings(sounds=False), tmp_path / "settings.toml")
    assert "sounds = false\n" in path.read_text(encoding="utf-8")


def test_an_older_settings_file_keeps_sounds_on(tmp_path: Path) -> None:
    """Files written before the sounds switch existed still load."""
    path = tmp_path / "settings.toml"
    path.write_text("camera_index = 1\ndwell_seconds = 0.8\ncooldown_seconds = 5.0\n", "utf-8")
    assert load_settings(path) == Settings(camera_index=1)


def test_closing_asks_by_default() -> None:
    """Nobody is sent to the background, or has the app quit, without being asked."""
    assert Settings().close_action == "ask"


@pytest.mark.parametrize("action", ["ask", "background", "quit"])
def test_the_close_action_round_trips(tmp_path: Path, action: str) -> None:
    path = tmp_path / "settings.toml"
    save_settings(Settings(close_action=action), path)
    assert load_settings(path).close_action == action


def test_a_settings_file_from_before_closing_options_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text("camera_index = 1\nsounds = false\n", encoding="utf-8")
    assert load_settings(path).close_action == "ask"
