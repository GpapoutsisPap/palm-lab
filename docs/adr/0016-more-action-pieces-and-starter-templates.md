# 16. More action pieces, and starter templates

Date: 2026-10-22

## Status

Accepted.

## Context

palm-lab had three pieces: Open app, Open website and Press keys. Comparable
tools (Stream Deck, Touch Portal, PowerToys Keyboard Manager, Logitech Smart
Actions) share about a dozen basic actions. Of those, volume and microphone
control, typing text, waiting, and opening folders and settings come up most
often. A blank gesture also gives a new user nothing to start from.

## Decision

- **Six new pieces**, each with a plain text target so bindings.toml keeps
  the same `type` + `target` shape:

  | Piece | Target | How it works on Windows |
  |---|---|---|
  | Type text | any text | `SendInput` with `KEYEVENTF_UNICODE`, so Greek types correctly on any keyboard layout; Enter and Tab are sent as keys; batches of 40 characters |
  | Wait | seconds, 0.1 to 60 | replaces the usual gap between pieces around it |
  | Volume | 0-100, `mute`, `unmute`, `mic_mute`, `mic_unmute` | Core Audio's `IAudioEndpointVolume` through COM in plain ctypes, calling methods by their table slot (slots from pycaw's definitions); setting a level also unmutes; microphone changes reach both the default and the communications microphone |
  | Open folder | a known folder name or a path | `SHGetKnownFolderPath` finds Downloads, Documents and the rest even when OneDrive has moved them |
  | Open setting | a page name or an `ms-settings:` link | a list of Windows 11 pages from Microsoft Learn |
  | Windows | `lock`, `show_desktop`, `screenshot` | `LockWorkStation`, Win+D, and Win+Shift+S (the new Snipping Tool link needs an MSIX-packaged app) |

- **No new dependencies.** pycaw would add comtypes and psutil for a few
  calls.
- **Each piece is split** into plain planning code (which keys, which
  devices), tested everywhere, and a thin ctypes call, which is replaced in
  tests.
- **The palette is grouped**: Apps & places, Keyboard, Sound & Windows,
  Timing.
- **Ten starter templates** in three categories (`templates.py`). Each one
  is checked by the same rules as a saved binding. Picking one fills the
  gesture being edited, which the person then changes.

## Not yet

- **Run command.** Anything that can edit the bindings file already runs as
  the user, so the real risks are imported binding packs and a gesture firing
  by accident. It needs a trust step first, modelled on VS Code's Workspace
  Trust: an Advanced switch, the full command shown, and a one-time
  confirmation for each new or changed command (stored as a hash).
- **Bring to front if already open**, as an option on Open app. Windows
  restricts `SetForegroundWindow`. The safe workaround (retries, then an Alt
  tap, never `AttachThreadInput`) needs testing on real machines.
- **Sleep**, which needs a privilege switched on first and behaves differently
  on Modern Standby laptops, and **switch audio device**, which has no
  documented API.

## Consequences

The editor covers the actions people use most, with no new dependencies.
Typing can't reach apps running as administrator, and Windows doesn't report
that it was blocked. Emoji typing and the volume calls need checking by hand
on Windows, because they can't run in Linux CI.
