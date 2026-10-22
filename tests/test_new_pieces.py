"""Tests for the newer action pieces: wait, type text, volume, folders, settings, Windows."""

import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from palm_lab.actions import desktop, hotkeys, runner
from palm_lab.actions.errors import ActionFailedError, InvalidBindingError
from palm_lab.actions.models import Action, ActionType, Binding, bindings_from_data
from palm_lab.actions.targets import (
    VolumeCommand,
    parse_system,
    parse_volume,
    parse_wait,
    settings_uri,
)

# Targets ---------------------------------------------------------------------------


@pytest.mark.parametrize(("target", "seconds"), [("2", 2.0), ("1.5", 1.5), ("0.5 s", 0.5)])
def test_wait_reads_seconds(target: str, seconds: float) -> None:
    assert parse_wait(target) == seconds


@pytest.mark.parametrize("target", ["0", "61", "soon", "nan"])
def test_wait_refuses_nonsense(target: str) -> None:
    with pytest.raises(ValueError):
        parse_wait(target)


@pytest.mark.parametrize(
    ("target", "command"),
    [
        ("30", VolumeCommand(level=30)),
        ("100%", VolumeCommand(level=100)),
        ("Mute", VolumeCommand(mute=True)),
        ("mic_unmute", VolumeCommand(microphone=True, mute=False)),
    ],
)
def test_volume_reads_a_level_or_a_word(target: str, command: VolumeCommand) -> None:
    assert parse_volume(target) == command


@pytest.mark.parametrize("target", ["101", "-5", "loud"])
def test_volume_refuses_nonsense(target: str) -> None:
    with pytest.raises(ValueError):
        parse_volume(target)


def test_settings_pages_become_links() -> None:
    assert settings_uri("Bluetooth") == "ms-settings:bluetooth"
    assert settings_uri("ms-settings:gaming-gamemode") == "ms-settings:gaming-gamemode"
    with pytest.raises(ValueError, match="not a Settings page"):
        settings_uri("https://example.com")


def test_windows_commands_are_a_fixed_list() -> None:
    assert parse_system("Lock") == "lock"
    with pytest.raises(ValueError, match="expected one of: lock, show_desktop, screenshot"):
        parse_system("shutdown")


def test_bindings_check_the_new_pieces_when_saved() -> None:
    def binding(kind: str, target: str) -> dict[str, object]:
        return {
            "binding": [
                {"gesture": "fist", "name": "X", "action": [{"type": kind, "target": target}]}
            ]
        }

    (ok,) = bindings_from_data(binding("volume", "40"))
    assert ok.actions[0].type is ActionType.VOLUME
    with pytest.raises(InvalidBindingError, match="Binding 1, action 1: volume must be between"):
        bindings_from_data(binding("volume", "400"))
    with pytest.raises(InvalidBindingError, match="Binding 1, action 1: wait must be between"):
        bindings_from_data(binding("wait", "300"))


# Typing ------------------------------------------------------------------------------


def unicode_units(events: Sequence[desktop.KeyEvent]) -> list[int]:
    return [unit for vk, unit, flags in events if not flags & desktop.KEYEVENTF_KEYUP and vk == 0]


def test_typing_sends_each_character_as_itself() -> None:
    """Greek types correctly whatever keyboard layout is active."""
    events = desktop.plan_typing("Γειά")
    assert unicode_units(events) == [ord(c) for c in "Γειά"]
    assert all(flags & desktop.KEYEVENTF_UNICODE for vk, _, flags in events)
    assert len(events) == 8  # a press and a release each


def test_new_lines_and_tabs_are_pressed_as_keys() -> None:
    events = desktop.plan_typing("a\r\nb\tc")
    keys = [vk for vk, _, flags in events if vk and not flags & desktop.KEYEVENTF_KEYUP]
    assert keys == [desktop.VK_RETURN, desktop.VK_TAB]  # \r\n is one Enter


def test_an_emoji_is_sent_as_its_two_halves() -> None:
    assert unicode_units(desktop.plan_typing("\U0001f44d")) == [0xD83D, 0xDC4D]


def test_typing_goes_in_batches_and_reports_blocking() -> None:
    sent: list[int] = []
    pauses: list[float] = []

    def send(batch: Sequence[desktop.KeyEvent]) -> int:
        sent.append(len(batch))
        return len(batch)

    desktop.type_text("x" * 100, send=send, sleep=pauses.append)
    assert sum(sent) == 200 and max(sent) <= desktop.TYPE_BATCH_EVENTS
    assert len(pauses) == len(sent) - 1
    with pytest.raises(OSError, match="blocked"):
        desktop.type_text("x", send=lambda batch: 0)


# Volume ------------------------------------------------------------------------------


def test_setting_a_level_also_unmutes() -> None:
    steps = desktop.plan_volume(VolumeCommand(level=30))
    assert [(what, value) for _, _, what, value in steps] == [("level", 0.3), ("mute", False)]
    assert {flow for flow, *_ in steps} == {desktop.E_RENDER}


def test_microphone_mute_reaches_the_call_microphone_too() -> None:
    steps = desktop.plan_volume(VolumeCommand(microphone=True, mute=True))
    assert {(flow, role) for flow, role, _, _ in steps} == {
        (desktop.E_CAPTURE, desktop.E_CONSOLE),
        (desktop.E_CAPTURE, desktop.E_COMMUNICATIONS),
    }


# Folders -----------------------------------------------------------------------------


def test_paths_expand_home_and_variables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PALM_TEST_DIR", str(tmp_path))
    variable = "%PALM_TEST_DIR%" if sys.platform == "win32" else "$PALM_TEST_DIR"
    assert desktop.resolve_path(f"{variable}/notes") == tmp_path / "notes"
    assert desktop.resolve_path('"~/x"') == Path.home() / "x"


def test_a_known_folder_falls_back_to_the_home_folder_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(desktop, "_known_folder_path", lambda folder_id: None)
    assert desktop.resolve_path("Downloads") == Path.home() / "Downloads"


def test_opening_something_missing_says_so(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="nothing at"):
        desktop.open_path(str(tmp_path / "missing"))


# The runner ----------------------------------------------------------------------------


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, object]]:
    """Record what each newer piece would do, instead of doing it."""
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(desktop, "type_text", lambda text: seen.append(("type", text)))
    monkeypatch.setattr(desktop, "set_volume", lambda command: seen.append(("volume", command)))
    monkeypatch.setattr(desktop, "open_path", lambda target: seen.append(("open", target)))
    monkeypatch.setattr(desktop, "open_settings", lambda uri: seen.append(("settings", uri)))
    monkeypatch.setattr(desktop, "lock_pc", lambda: seen.append(("lock", None)))
    monkeypatch.setattr(hotkeys, "_keybd_event", lambda vk, flags: seen.append(("key", vk)))
    return seen


def act(kind: ActionType, target: str) -> Action:
    return Action(type=kind, target=target)


def test_each_new_piece_reaches_its_windows_call(calls: list[tuple[str, object]]) -> None:
    for action in (
        act(ActionType.TYPE_TEXT, "hello"),
        act(ActionType.VOLUME, "mute"),
        act(ActionType.OPEN_PATH, "Downloads"),
        act(ActionType.SETTINGS, "sound"),
        act(ActionType.SYSTEM, "lock"),
    ):
        assert runner.run_action(action).ok
    assert calls == [
        ("type", "hello"),
        ("volume", VolumeCommand(mute=True)),
        ("open", "Downloads"),
        ("settings", "ms-settings:sound"),
        ("lock", None),
    ]


def test_show_desktop_and_screenshot_press_windows_shortcuts(
    calls: list[tuple[str, object]],
) -> None:
    runner.run_action(act(ActionType.SYSTEM, "show_desktop"))
    runner.run_action(act(ActionType.SYSTEM, "screenshot"))
    pressed = [vk for kind, vk in calls if kind == "key"]
    assert pressed[:2] == [0x5B, ord("D")]  # Win down, D down
    assert ord("S") in pressed and 0x10 in pressed  # Win+Shift+S


def test_a_failing_piece_explains_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_speakers(command: VolumeCommand) -> None:
        raise OSError("there are no speakers to change")

    monkeypatch.setattr(desktop, "set_volume", no_speakers)
    result = runner.run_action(act(ActionType.VOLUME, "50"))
    assert isinstance(result.error, ActionFailedError)
    assert result.error.user_message() == "Volume didn’t work. There are no speakers to change."


def test_wait_pauses_instead_of_the_usual_gap_between_pieces(
    calls: list[tuple[str, object]],
) -> None:
    pauses: list[float] = []
    binding = Binding(
        gesture="peace",
        name="Quick note",
        actions=(
            act(ActionType.SETTINGS, "sound"),
            act(ActionType.WAIT, "2"),
            act(ActionType.TYPE_TEXT, "hi"),
            act(ActionType.TYPE_TEXT, "there"),
        ),
        step_delay_seconds=0.4,
    )
    results = runner.run_binding(binding, sleep=pauses.append)
    assert all(r.ok for r in results)
    assert pauses == [2.0, 0.4]  # the wait itself, then the usual gap between the two typings
