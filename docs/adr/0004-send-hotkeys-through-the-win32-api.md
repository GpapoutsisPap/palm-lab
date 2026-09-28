# 4. Send hotkeys through the Win32 API

Date: 2026-09-28

## Status

Accepted

## Context

Bindings need to press keys: media controls such as play/pause, volume, and
combinations such as ctrl+alt+t. Python has no standard-library way to do
this, so the options were a third-party library (pynput, keyboard,
pyautogui) or calling the operating system directly.

The libraries are cross-platform, but palm-lab targets Windows only. Each
one adds a dependency that PyInstaller has to bundle into the installer.
`keyboard` also installs a global keyboard hook to support listening, which
antivirus heuristics tend to flag in unsigned executables. The app only
needs to send keys, never to listen.

## Decision

Hotkeys are sent with the Win32 `keybd_event` function, called through
`ctypes` from the standard library. There is no new dependency.

A hotkey target such as `ctrl+alt+t` is parsed into modifiers and one key,
using a hand-maintained table of named keys (media, volume, navigation),
letters, digits and F1 to F24, plus a few aliases (`play_pause`, `mute`,
`escape`). Media and navigation keys are sent with the extended-key flag,
without which Windows silently ignores them.

Targets are validated when the bindings file loads, so an unknown key is
reported by binding and action number at startup rather than failing when
the gesture fires. The function that sends keys can be replaced, and is
looked up at call time, so tests intercept it and never press real keys.

## Consequences

The installer stays smaller and there is one less third-party package to
bundle, update or audit. Nothing hooks the keyboard, so there is nothing for
antivirus software to mistake for a keylogger.

The feature is Windows-only. On other platforms the send fails and is
reported as a launch failure, which is acceptable because the app targets
Windows, but it would need revisiting if a macOS or Linux port happens.

Microsoft documents `keybd_event` as superseded by `SendInput`. It still
works, but it is the legacy call. Switching is contained in one function if
it ever misbehaves.

Only taps are supported: a hotkey cannot type a string of text or hold a key
down. Windows also blocks input from a normal-privilege process to windows
running as administrator (User Interface Privilege Isolation), so hotkeys
will not reach elevated applications such as Task Manager unless palm-lab
itself runs elevated.

Revisit if text typing or key holding is needed, if cross-platform support
becomes a goal, or if `keybd_event` stops behaving reliably.
