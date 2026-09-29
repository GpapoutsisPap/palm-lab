# Changelog

All notable changes to palm-lab are listed here, newest first. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version
numbers follow [Semantic Versioning](https://semver.org/): while palm-lab is
0.x, a new feature raises the middle number and a fix raises the last one.

Each version's section becomes the notes of its GitHub Release, so write it
for the people installing the app.

## [Unreleased]

### Added

- palm-lab can keep running in the background with its window closed, so your
  gestures keep working. It waits in the notification area by the clock:
  click its icon to open it, or right-click it to switch tracking or quit.
- Closing the window asks whether to keep palm-lab running in the
  background, with a "Don't show this again" box. Settings > "When I close
  the window" changes the answer later.
- Start with Windows: a switch in Settings that starts palm-lab in the
  background when you sign in, already watching for gestures.
- Opening palm-lab while it is already running brings up the running window
  instead of starting a second copy.

## [0.2.0] - 2026-09-29

The first release with a window and an installer.

### Added

- A palm-lab window with Gestures, Activity and Settings pages, in the style
  of Windows 11: light and dark themes and your accent colour.
- Actions that snap together: drag "Open app", "Open website" and "Press keys"
  pieces into a gesture, reorder them, and test them without the camera.
- Add your own gestures: hold a new hand shape twice, name it, and it gets its
  own icon. A shape you already use is recognised straight away, and
  shortcuts pause while you record.
- A live camera view showing the hand palm-lab sees and the gesture it reads.
- An Activity page listing what ran and anything that failed.
- Settings for the camera, how long to hold a gesture, the pause between
  repeats, and sounds, saved between runs.
- Desktop and Start menu shortcuts, switchable from Settings.
- A Windows installer that needs no administrator rights, with an uninstaller
  under Settings > Apps.
- The version number is shown at the bottom of Settings.

## [0.1.0] - 2026-09-28

The first working version, run from a terminal.

### Added

- Hand tracking from a webcam with MediaPipe, recognising a peace sign, fist,
  open palm and thumbs up.
- Gesture bindings in a TOML file that open apps, open websites or press keys.
- The `palm-lab` command line: `run`, `capture`, `config` and `doctor`.
- A Windows executable built with PyInstaller.

[Unreleased]: https://github.com/GpapoutsisPap/palm-lab/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/GpapoutsisPap/palm-lab/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/GpapoutsisPap/palm-lab/releases/tag/v0.1.0
