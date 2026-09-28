"""Parse hotkey descriptions and send them as Windows keystrokes.

A hotkey target is a single key name ("media_play_pause", "f5") or a
combination joined with "+", modifiers first ("ctrl+alt+t", "win+d").
"""

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

MODIFIERS: dict[str, int] = {
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
}

MODIFIER_ALIASES: dict[str, str] = {
    "control": "ctrl",
    "windows": "win",
    "super": "win",
}

NAMED_KEYS: dict[str, int] = {
    # Media and volume
    "media_play_pause": 0xB3,
    "media_next": 0xB0,
    "media_previous": 0xB1,
    "media_stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "volume_mute": 0xAD,
    # Editing and navigation
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
}

KEY_ALIASES: dict[str, str] = {
    "play_pause": "media_play_pause",
    "next_track": "media_next",
    "previous_track": "media_previous",
    "mute": "volume_mute",
    "return": "enter",
    "escape": "esc",
    "del": "delete",
}

# Keys that Windows expects to be sent with the extended-key flag.
EXTENDED_KEYS = frozenset(
    {
        0x5B,
        0xB3,
        0xB0,
        0xB1,
        0xB2,
        0xAF,
        0xAE,
        0xAD,
        0x2E,
        0x2D,
        0x24,
        0x23,
        0x21,
        0x22,
        0x25,
        0x26,
        0x27,
        0x28,
        0x2C,
    }
)

KeySender = Callable[[int, int], None]


@dataclass(frozen=True)
class Hotkey:
    """A parsed hotkey: modifiers held down, then one key pressed."""

    modifiers: tuple[int, ...]
    key: int


def _key_code(name: str) -> int | None:
    """Virtual-key code for a single non-modifier key name, or None."""
    name = KEY_ALIASES.get(name, name)
    if name in NAMED_KEYS:
        return NAMED_KEYS[name]
    if len(name) == 1 and (name.isascii() and name.isalnum()):
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit():
        number = int(name[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1
    return None


def _modifier_code(name: str) -> int | None:
    return MODIFIERS.get(MODIFIER_ALIASES.get(name, name))


def parse_hotkey(text: str) -> Hotkey:
    """Turn "ctrl+shift+esc" into a Hotkey. Raises ValueError if invalid."""
    parts = [part.strip().lower() for part in text.split("+")]
    if not text.strip() or any(not part for part in parts):
        raise ValueError(f"hotkey {text!r} is empty or has a stray '+'")

    *modifier_names, key_name = parts

    modifiers: list[int] = []
    for name in modifier_names:
        code = _modifier_code(name)
        if code is None:
            raise ValueError(
                f"hotkey {text!r}: {name!r} is not a modifier "
                f"(expected one of: {', '.join(MODIFIERS)})"
            )
        if code in modifiers:
            raise ValueError(f"hotkey {text!r}: {name!r} appears twice")
        modifiers.append(code)

    key = _key_code(key_name)
    if key is None:
        # A modifier on its own is a valid hotkey: "win" opens the Start menu.
        key = _modifier_code(key_name)
    if key is None:
        raise ValueError(f"hotkey {text!r}: unknown key {key_name!r}")
    if key in modifiers:
        raise ValueError(f"hotkey {text!r}: {key_name!r} appears twice")

    return Hotkey(modifiers=tuple(modifiers), key=key)


def _keybd_event(vk: int, flags: int) -> None:
    """Send one key transition through the Win32 API."""
    if sys.platform != "win32":
        raise OSError("hotkeys are only supported on Windows")
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


def send_hotkey(hotkey: Hotkey, sender: KeySender | None = None) -> None:
    """Press modifiers, tap the key, release modifiers in reverse order.

    The sender defaults to the Win32 call, looked up at call time so tests can
    replace it.
    """
    send = sender if sender is not None else _keybd_event

    def flags(vk: int, release: bool) -> int:
        value = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0
        return (value | KEYEVENTF_KEYUP) if release else value

    for vk in hotkey.modifiers:
        send(vk, flags(vk, release=False))
    send(hotkey.key, flags(hotkey.key, release=False))
    send(hotkey.key, flags(hotkey.key, release=True))
    for vk in reversed(hotkey.modifiers):
        send(vk, flags(vk, release=True))
