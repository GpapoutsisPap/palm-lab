# 5. Store user configuration in the user profile

Date: 2026-09-28

## Status

Accepted. Recorded after the change shipped, in the pull request that added
hotkeys.

## Context

The bindings file was read from the current working directory, so the app
only worked when launched from the repository root. An installed app has no
meaningful working directory: a shortcut, the Start menu or an autostart
entry can launch it from anywhere. The configuration also has to survive
reinstalling and updating the app, and it cannot live beside the program in
Program Files, which is not writable without administrator rights.

## Decision

User configuration lives in `%APPDATA%\palm-lab` on Windows, and under
`XDG_CONFIG_HOME` (normally `~/.config/palm-lab`) elsewhere. The
`PALM_LAB_CONFIG_DIR` environment variable overrides both.

On first run a commented default `bindings.toml` is written there, explaining
the format and the available gestures, actions and hotkeys. An existing file
is never overwritten.

All filesystem locations, including the hand landmarker model, are defined
in `config.py`. A `palm-lab` command with `run`, `capture`, `config` and
`doctor` subcommands is the entry point. The camera module, which loads
OpenCV and MediaPipe, is imported only by the subcommands that use the
camera, so `config` and `doctor` start instantly and the CLI can be tested
without the vision libraries installed.

## Consequences

The app works from any directory and keeps its configuration across updates.
The override makes the configuration code testable without touching a real
user profile, and allows a portable install later.

Because an existing file is never overwritten, users do not see improvements
to the default file. This already happened once: the hotkey documentation and
example added to the default never reach anyone who ran the app before them.
A `reset` or `migrate` command will eventually be needed.

The bindings file has no format version. Any future breaking change to the
format will need one to be added first.

The model path is currently computed relative to the source files. That will
not hold inside a PyInstaller build, where bundled files are unpacked
elsewhere, and has to change during packaging.
