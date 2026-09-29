"""Tests for executing the actions in a binding."""

import os
import sys
import webbrowser

import pytest

from palm_lab.actions import hotkeys, runner
from palm_lab.actions.apps import KNOWN_APPS
from palm_lab.actions.errors import AppNotFoundError, LaunchFailedError
from palm_lab.actions.models import Action, ActionType, Binding


def _binding(*actions: Action, delay: float = 0.4) -> Binding:
    return Binding(gesture="peace", name="Test", actions=actions, step_delay_seconds=delay)


LAUNCH = Action(type=ActionType.LAUNCH, target="spotify")
URL = Action(type=ActionType.OPEN_URL, target="https://example.com")
HOTKEY = Action(type=ActionType.HOTKEY, target="media_play_pause")
# Built directly, bypassing the parser, to exercise the runner's own guard.
BAD_HOTKEY = Action(type=ActionType.HOTKEY, target="not_a_key")


@pytest.fixture(autouse=True)
def pressed(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record key events so no test ever presses a real key."""
    events: list[tuple[int, int]] = []
    monkeypatch.setattr(hotkeys, "_keybd_event", lambda vk, f: events.append((vk, f)))
    return events


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record launch targets instead of starting real applications."""
    calls: list[str] = []
    monkeypatch.setattr(runner, "_launch", calls.append)
    return calls


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record opened URLs instead of starting a real browser."""
    calls: list[str] = []
    monkeypatch.setattr(runner, "_open_url", calls.append)
    return calls


def test_launch_action_resolves_a_known_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """A friendly name is translated through the known-apps table."""
    seen: list[str] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", seen.append, raising=False)
    runner._launch("Spotify")
    assert seen == [KNOWN_APPS["spotify"]]


def test_launch_action_passes_an_unknown_target_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognised name is treated as a literal path."""
    seen: list[str] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", seen.append, raising=False)
    runner._launch(r"C:\Tools\thing.exe")
    assert seen == [r"C:\Tools\thing.exe"]


def test_missing_application_becomes_app_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FileNotFoundError is translated into a typed, explainable error."""

    def boom(_: str) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", boom, raising=False)
    result = runner.run_action(LAUNCH)
    assert isinstance(result.error, AppNotFoundError)
    assert "spotify" in result.error.user_message()


def test_other_os_errors_become_launch_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything else the OS raises is reported as a launch failure."""

    def boom(_: str) -> None:
        raise PermissionError("access denied")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", boom, raising=False)
    result = runner.run_action(LAUNCH)
    assert isinstance(result.error, LaunchFailedError)
    assert "access denied" in str(result.error)


def test_open_url_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """webbrowser returning False means no browser handled the URL."""
    monkeypatch.setattr(webbrowser, "open", lambda _: False)
    result = runner.run_action(URL)
    assert isinstance(result.error, LaunchFailedError)


def test_open_url_success(opened: list[str]) -> None:
    """A successful open produces a result with no error."""
    result = runner.run_action(URL)
    assert result.ok
    assert opened == ["https://example.com"]


def test_hotkey_action_sends_the_key(pressed: list[tuple[int, int]]) -> None:
    """A hotkey action presses and releases its key."""
    result = runner.run_action(HOTKEY)
    assert result.ok
    assert [vk for vk, _ in pressed] == [0xB3, 0xB3]


def test_invalid_hotkey_becomes_launch_failed(pressed: list[tuple[int, int]]) -> None:
    """A target the parser rejects is reported, and nothing is pressed."""
    result = runner.run_action(BAD_HOTKEY)
    assert isinstance(result.error, LaunchFailedError)
    assert "unknown key" in str(result.error)
    assert pressed == []


def test_hotkey_os_failure_becomes_launch_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the keyboard API is unavailable, the failure is reported, not raised."""

    def unavailable(vk: int, flags: int) -> None:
        raise OSError("hotkeys are only supported on Windows")

    monkeypatch.setattr(hotkeys, "_keybd_event", unavailable)
    result = runner.run_action(HOTKEY)
    assert isinstance(result.error, LaunchFailedError)
    assert "only supported on Windows" in str(result.error)


def test_every_action_runs_even_after_a_failure(launched: list[str], opened: list[str]) -> None:
    """Partial success: one bad action does not stop the ones after it."""
    binding = _binding(BAD_HOTKEY, LAUNCH, URL)
    results = runner.run_binding(binding, sleep=lambda _: None)
    assert [r.ok for r in results] == [False, True, True]
    assert launched == ["spotify"]
    assert opened == ["https://example.com"]


def test_one_result_per_action_in_order(launched: list[str]) -> None:
    """Results line up with the actions that produced them."""
    first = Action(type=ActionType.LAUNCH, target="one")
    second = Action(type=ActionType.LAUNCH, target="two")
    results = runner.run_binding(_binding(first, second), sleep=lambda _: None)
    assert [r.action for r in results] == [first, second]


def test_delay_goes_between_actions_not_before_the_first(
    launched: list[str],
) -> None:
    """Three actions means two gaps, and no wait before anything happens."""
    slept: list[float] = []
    binding = _binding(LAUNCH, LAUNCH, LAUNCH, delay=0.25)
    runner.run_binding(binding, sleep=slept.append)
    assert slept == [0.25, 0.25]


def test_single_action_binding_never_sleeps(launched: list[str]) -> None:
    """A one-step binding should fire immediately."""
    slept: list[float] = []
    runner.run_binding(_binding(LAUNCH), sleep=slept.append)
    assert slept == []
