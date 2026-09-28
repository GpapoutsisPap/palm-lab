"""Tests for parsing and sending hotkeys."""

import re
import sys

import pytest

from palm_lab.actions import hotkeys
from palm_lab.actions.hotkeys import (
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    MODIFIERS,
    NAMED_KEYS,
    Hotkey,
    parse_hotkey,
    send_hotkey,
)

CTRL = MODIFIERS["ctrl"]
ALT = MODIFIERS["alt"]
SHIFT = MODIFIERS["shift"]
WIN = MODIFIERS["win"]
DOWN_EXT = KEYEVENTF_EXTENDEDKEY
UP = KEYEVENTF_KEYUP
UP_EXT = KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("media_play_pause", Hotkey((), 0xB3), id="media-key"),
        pytest.param("volume_up", Hotkey((), 0xAF), id="volume-key"),
        pytest.param("a", Hotkey((), ord("A")), id="letter"),
        pytest.param("7", Hotkey((), ord("7")), id="digit"),
        pytest.param("f5", Hotkey((), 0x74), id="function-key"),
        pytest.param("f24", Hotkey((), 0x87), id="highest-function-key"),
        pytest.param("ctrl+c", Hotkey((CTRL,), ord("C")), id="one-modifier"),
        pytest.param("ctrl+alt+t", Hotkey((CTRL, ALT), ord("T")), id="two-modifiers"),
        pytest.param("ctrl+shift+esc", Hotkey((CTRL, SHIFT), 0x1B), id="named-with-mods"),
        pytest.param("win+d", Hotkey((WIN,), ord("D")), id="windows-key"),
        pytest.param("win", Hotkey((), WIN), id="modifier-alone"),
    ],
)
def test_parses_valid_hotkeys(text: str, expected: Hotkey) -> None:
    """Named keys, letters, digits, F-keys and combinations all parse."""
    assert parse_hotkey(text) == expected


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("play_pause", "media_play_pause"),
        ("next_track", "media_next"),
        ("previous_track", "media_previous"),
        ("mute", "volume_mute"),
        ("escape", "esc"),
        ("return", "enter"),
        ("control+c", "ctrl+c"),
        ("windows+d", "win+d"),
        ("super+d", "win+d"),
    ],
)
def test_aliases_resolve_to_the_same_hotkey(alias: str, canonical: str) -> None:
    """Friendly alternative names mean exactly the same thing."""
    assert parse_hotkey(alias) == parse_hotkey(canonical)


def test_case_and_spacing_do_not_matter() -> None:
    """Config written by hand should not be punished for style."""
    assert parse_hotkey(" Ctrl + Alt + T ") == parse_hotkey("ctrl+alt+t")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("", "empty", id="empty"),
        pytest.param("ctrl+", "stray '+'", id="trailing-plus"),
        pytest.param("+a", "stray '+'", id="leading-plus"),
        pytest.param("ctrl++a", "stray '+'", id="double-plus"),
        pytest.param("banana", "unknown key 'banana'", id="unknown-key"),
        pytest.param("f25", "unknown key 'f25'", id="function-key-too-high"),
        pytest.param("f0", "unknown key 'f0'", id="function-key-zero"),
        pytest.param("a+b", "'a' is not a modifier", id="non-modifier-first"),
        pytest.param("ctrl+ctrl+a", "appears twice", id="duplicate-modifier"),
        pytest.param("ctrl+ctrl", "appears twice", id="modifier-repeated-as-key"),
    ],
)
def test_rejects_invalid_hotkeys(text: str, expected: str) -> None:
    """Every malformed hotkey raises ValueError with a readable reason."""
    with pytest.raises(ValueError, match=re.escape(expected)):
        parse_hotkey(text)


def test_every_named_key_parses() -> None:
    """No entry in the key table is unreachable through the parser."""
    for name, code in NAMED_KEYS.items():
        assert parse_hotkey(name).key == code


def test_combination_presses_and_releases_in_order() -> None:
    """Modifiers go down first and come up last, in reverse order."""
    events: list[tuple[int, int]] = []
    send_hotkey(parse_hotkey("ctrl+alt+t"), sender=lambda vk, f: events.append((vk, f)))
    assert events == [
        (CTRL, 0),
        (ALT, 0),
        (ord("T"), 0),
        (ord("T"), UP),
        (ALT, UP),
        (CTRL, UP),
    ]


def test_media_keys_use_the_extended_flag() -> None:
    """Windows ignores media keys sent without the extended-key flag."""
    events: list[tuple[int, int]] = []
    send_hotkey(parse_hotkey("media_play_pause"), sender=lambda vk, f: events.append((vk, f)))
    assert events == [(0xB3, DOWN_EXT), (0xB3, UP_EXT)]


def test_windows_key_uses_the_extended_flag() -> None:
    """The Windows key is an extended key too."""
    events: list[tuple[int, int]] = []
    send_hotkey(parse_hotkey("win+d"), sender=lambda vk, f: events.append((vk, f)))
    assert events[0] == (WIN, DOWN_EXT)
    assert events[-1] == (WIN, UP_EXT)


def test_default_sender_is_looked_up_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replacing the module's sender affects calls without an explicit one."""
    events: list[tuple[int, int]] = []
    monkeypatch.setattr(hotkeys, "_keybd_event", lambda vk, f: events.append((vk, f)))
    send_hotkey(parse_hotkey("f5"))
    assert [vk for vk, _ in events] == [0x74, 0x74]


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows guard")
def test_sending_off_windows_raises_os_error() -> None:
    """Outside Windows there is no keyboard API to call."""
    with pytest.raises(OSError, match="only supported on Windows"):
        send_hotkey(parse_hotkey("f5"))
