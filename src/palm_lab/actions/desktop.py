"""The Windows calls behind the newer action pieces: typing, volume, folders, lock.

Each piece is split in two. The planning (which keys to send, which device to
mute) is plain Python and is tested everywhere. The Windows call itself is a
small ctypes function here, so palm-lab needs no extra libraries:

- Typing uses SendInput with KEYEVENTF_UNICODE: each character goes to the
  app as itself, so Greek or accented text types correctly whatever keyboard
  layout is active. It reaches ordinary desktop apps; Windows doesn't let it
  into apps running as administrator, and many games ignore it.
- Volume talks to Windows' Core Audio (IAudioEndpointVolume) through COM,
  calling methods by their slot in the interface's table, as pycaw does.
- Known folders are asked of Windows (SHGetKnownFolderPath), so Documents is
  found even when OneDrive has moved it.
"""

import ctypes
import os
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from palm_lab.actions.targets import KNOWN_FOLDERS, VolumeCommand

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_TAB = 0x09
# Keys go in batches, with a pause between, so a slow app's queue can keep up.
TYPE_BATCH_EVENTS = 80
TYPE_BATCH_PAUSE = 0.01

KeyEvent = tuple[int, int, int]  # (virtual key, UTF-16 unit, flags)


def plan_typing(text: str) -> list[KeyEvent]:
    """The key presses that type text: Enter and Tab as keys, the rest as characters.

    A character outside the 16-bit range (most emoji) is two UTF-16 units, sent
    one after the other, which Windows apps put back together.
    """
    events: list[KeyEvent] = []
    for char in text.replace("\r\n", "\n").replace("\r", "\n"):
        if char in "\n\t":
            vk = VK_RETURN if char == "\n" else VK_TAB
            events += [(vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP)]
            continue
        encoded = char.encode("utf-16-le")
        for i in range(0, len(encoded), 2):
            unit = int.from_bytes(encoded[i : i + 2], "little")
            events += [(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return events


def _batches(events: Sequence[KeyEvent], size: int = TYPE_BATCH_EVENTS) -> list[Sequence[KeyEvent]]:
    return [events[i : i + size] for i in range(0, len(events), size)]


def type_text(
    text: str,
    send: Callable[[Sequence[KeyEvent]], int] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Type text into whatever app is in front."""
    sender = send if send is not None else _send_input
    for index, batch in enumerate(_batches(plan_typing(text))):
        if index:
            sleep(TYPE_BATCH_PAUSE)
        if sender(batch) < len(batch):
            raise OSError("Windows blocked the typing (is the app running as administrator?)")


def known_folder(name: str) -> Path | None:
    """Where one of Windows' own folders really is, or None if it isn't one."""
    entry = KNOWN_FOLDERS.get(name.strip().lower())
    if entry is None:
        return None
    label, folder_id = entry
    found = _known_folder_path(folder_id)
    return found if found is not None else Path.home() / label


def resolve_path(target: str) -> Path:
    """A known folder's name, or a path (with ~ and %VARIABLES% expanded)."""
    folder = known_folder(target)
    if folder is not None:
        return folder
    return Path(os.path.expandvars(os.path.expanduser(target.strip().strip('"'))))


def open_path(target: str) -> None:
    path = resolve_path(target)
    if not path.exists():
        raise FileNotFoundError(f"there's nothing at {path}")
    _start(str(path))


def open_settings(uri: str) -> None:
    _start(uri)


def _start(target: str) -> None:
    if sys.platform != "win32":
        raise OSError("this action only works on Windows")
    os.startfile(target)


def lock_pc() -> None:
    if sys.platform != "win32":
        raise OSError("this action only works on Windows")
    if not ctypes.windll.user32.LockWorkStation():
        raise OSError("Windows refused to lock the PC")


# Windows-only plumbing -----------------------------------------------------------------


def _send_input(events: Sequence[KeyEvent]) -> int:
    if sys.platform != "win32":
        raise OSError("typing only works on Windows")
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class MOUSEINPUT(ctypes.Structure):  # only here so the union has the right size
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    input_keyboard = 1
    array = (INPUT * len(events))()
    for slot, (vk, unit, flags) in zip(array, events, strict=True):
        slot.type = input_keyboard
        slot.union.ki = KEYBDINPUT(vk, unit, flags, 0, 0)
    send = ctypes.WinDLL("user32", use_last_error=True).SendInput
    send.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    send.restype = wintypes.UINT
    return int(send(len(events), array, ctypes.sizeof(INPUT)))


def _guid(text: str) -> "ctypes.Array[ctypes.c_char]":
    return ctypes.create_string_buffer(uuid.UUID(text).bytes_le, 16)


def _known_folder_path(folder_id: str) -> Path | None:
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    result = ctypes.c_wchar_p()
    hr = shell32.SHGetKnownFolderPath(_guid(folder_id), 0, None, ctypes.byref(result))
    try:
        return Path(result.value) if hr == 0 and result.value else None
    finally:
        ole32.CoTaskMemFree.argtypes = [wintypes.LPVOID]
        ole32.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))  # Windows allocated it


# Volume: Core Audio through COM ----------------------------------------------------

CLSID_MM_DEVICE_ENUMERATOR = "BCDE0395-E52F-467C-8E3D-C4579291692E"
IID_IMM_DEVICE_ENUMERATOR = "A95664D2-9614-4F35-A746-DE8DB63617E6"
IID_IAUDIO_ENDPOINT_VOLUME = "5CDF2C82-841E-4546-9722-0CF74078229A"
CLSCTX_INPROC_SERVER = 0x1
CLSCTX_ALL = 0x17
COINIT_APARTMENTTHREADED = 0x2
E_RENDER, E_CAPTURE = 0, 1
E_CONSOLE, E_MULTIMEDIA, E_COMMUNICATIONS = 0, 1, 2
# Slots in each interface's method table; IUnknown takes 0-2 (pycaw's definitions).
SLOT_RELEASE = 2
SLOT_GET_DEFAULT_ENDPOINT = 4  # IMMDeviceEnumerator
SLOT_ACTIVATE = 3  # IMMDevice
SLOT_SET_LEVEL_SCALAR = 7  # IAudioEndpointVolume
SLOT_SET_MUTE = 14  # IAudioEndpointVolume


def plan_volume(command: VolumeCommand) -> list[tuple[int, int, str, float | bool]]:
    """Which devices to change, and how: (data flow, role, "level" or "mute", value).

    Setting a level also unmutes, as dragging the Windows slider does. The
    microphone change goes to both the default and the default communications
    microphone, which calls use when they differ.
    """
    if command.microphone:
        roles = [(E_CAPTURE, E_CONSOLE), (E_CAPTURE, E_COMMUNICATIONS)]
        return [(flow, role, "mute", bool(command.mute)) for flow, role in roles]
    steps: list[tuple[int, int, str, float | bool]] = []
    if command.level is not None:
        steps.append((E_RENDER, E_MULTIMEDIA, "level", command.level / 100))
        steps.append((E_RENDER, E_MULTIMEDIA, "mute", False))
    if command.mute is not None:
        steps.append((E_RENDER, E_MULTIMEDIA, "mute", command.mute))
    return steps


def set_volume(command: VolumeCommand) -> None:
    """Carry out a volume piece with Windows' Core Audio."""
    if sys.platform != "win32":
        raise OSError("volume only works on Windows")
    ole32 = ctypes.oledll.ole32  # raises OSError for a failing HRESULT
    try:
        ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        initialised = True
    except OSError:  # this thread already set COM up another way; use that
        initialised = False
    try:
        for flow, role, what, value in plan_volume(command):
            _set_endpoint(flow, role, what, value)
    finally:
        if initialised:
            ole32.CoUninitialize()


def _method(pointer: ctypes.c_void_p, slot: int, *argtypes: Any) -> Callable[..., int]:
    """A COM method, called by its slot; a failing HRESULT raises OSError."""
    if sys.platform != "win32":
        raise OSError("COM only exists on Windows")
    prototype = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    function = prototype(slot, f"slot{slot}")
    return lambda *args: int(function(pointer, *args))


def _release(pointer: ctypes.c_void_p) -> None:
    if sys.platform != "win32" or not pointer.value:
        return
    prototype = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
    prototype(SLOT_RELEASE, "Release")(pointer)


def _set_endpoint(flow: int, role: int, what: str, value: float | bool) -> None:
    if sys.platform != "win32":
        raise OSError("volume only works on Windows")
    from ctypes import wintypes

    enumerator, device, volume = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        ctypes.oledll.ole32.CoCreateInstance(
            _guid(CLSID_MM_DEVICE_ENUMERATOR),
            None,
            CLSCTX_INPROC_SERVER,
            _guid(IID_IMM_DEVICE_ENUMERATOR),
            ctypes.byref(enumerator),
        )
        get_default = _method(
            enumerator, SLOT_GET_DEFAULT_ENDPOINT, ctypes.c_int, ctypes.c_int, ctypes.c_void_p
        )
        try:
            get_default(flow, role, ctypes.byref(device))
        except OSError as exc:
            kind = "microphone" if flow == E_CAPTURE else "speakers"
            raise OSError(f"there are no {kind} to change") from exc
        activate = _method(
            device, SLOT_ACTIVATE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p
        )
        activate(_guid(IID_IAUDIO_ENDPOINT_VOLUME), CLSCTX_ALL, None, ctypes.byref(volume))
        if what == "level":
            set_level = _method(volume, SLOT_SET_LEVEL_SCALAR, ctypes.c_float, ctypes.c_void_p)
            set_level(float(value), None)
        else:
            set_mute = _method(volume, SLOT_SET_MUTE, wintypes.BOOL, ctypes.c_void_p)
            set_mute(bool(value), None)
    finally:
        for pointer in (volume, device, enumerator):
            _release(pointer)
