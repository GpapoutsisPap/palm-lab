# Changelog

All notable changes to palm-lab are listed here, newest first. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version
numbers follow [Semantic Versioning](https://semver.org/): while palm-lab is
0.x, a new feature raises the middle number and a fix raises the last one.

Each version's section becomes the notes of its GitHub Release, so write it
for the people installing the app.

## [Unreleased]

### Added

- A pop-up by the clock when a gesture runs with palm-lab's window hidden:
  "Ran Morning setup", or what went wrong. It never takes focus, lets clicks
  through, and stays away during games, presentations and Do Not Disturb.
  Settings > When a gesture runs turns it off, or limits it to failures.
- A Run button on every gesture row, and "Last ran 5 minutes ago" (or
  "Failed ...") under its name, with the exact time on hover.
- Six new action pieces: Type text (any language), Wait, Volume (set a level,
  or mute and unmute the speakers or microphone), Open folder (Downloads,
  Documents and more, wherever they really are), Open setting (a Windows
  Settings page), and Windows (lock, show the desktop, screenshot). The
  editor's pieces are now grouped.
- Starter templates: ten ready-made shortcuts, such as Step away and Quick
  note, to fill a gesture from and then make your own.
- Colour palettes in Settings > Appearance > Colours: Sunset, Neon, Ocean,
  Grape, Rose and Graphite, each in light and dark, alongside the Windows
  accent colour. Each has its own backgrounds, text and title colours, a
  gradient behind the sidebar and a glow on the page (Neon adds a grid).
  Every one is checked for readable contrast, and the puzzle pieces keep
  their colours in all of them.
- `palm-lab popup` shows the pop-up by the clock with a few made-up runs, so
  you can see it without a camera.

- Strictness in Settings > Recognition. A gesture now only counts when the
  hand is held like one: palm (or back of the hand) to the camera and
  pointing up, or, for a thumbs up, the thumb pointing up. A hand resting on
  your chin with its fingers out no longer runs anything. Normal is the
  default; Strict narrows the limits, and Relaxed counts the fingers alone,
  as before. The live view and the setup guide say how to hold a hand that
  isn't counted.

### Changed

- Activity now catches every run, including runs made while the window was
  hidden. Runs started from the window are marked as such.
- A Wait piece is its own pause, so the usual gap isn't added around it.
- On a narrow window, gesture rows drop the action chips so the name and
  "Last ran" fit.

## [0.3.0] - 2026-10-22

palm-lab now runs in the background, starts with a setup guide that tunes it
to your hand, and gives you more control over what runs and when.

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
- A Theme setting under Settings > Appearance: Light, Dark, or follow
  Windows (as before). The title bar follows it too.
- Custom CSS under Settings > Appearance: restyle palm-lab with your own CSS,
  previewed as you type. Ctrl+Shift+X turns it off if it goes wrong.
- The Gestures page shows what palm-lab is doing as you hold a gesture: a
  ring fills over the hold time, and a status line says "Holding peace sign",
  "Ran Morning setup", "Cooling down, ready again in 3 s", or that a gesture
  isn't set up yet. The gesture's row fills in step.
- Pause tracking for 15 minutes, 1 hour or 4 hours, from the Gestures page or
  the icon by the clock. The camera turns off while paused and tracking comes
  back by itself.
- On a wide window the Gestures page uses two columns: tracking, a larger
  camera preview and a "Recently ran" list on the left, your gestures on the
  right. Narrower windows keep the single column.
- Each set-up gesture has an on/off switch in its row. Switched off, the
  gesture keeps its actions but doesn't run them, and the Gestures page says
  so when you hold it. `palm-lab config` marks switched-off gestures too.
- Two-hand setups: pick two of your gestures, such as a fist and a peace
  sign, and the setup runs only when both hands show them at once, whichever
  hand makes which. A hand resting on your chin can't set one off. While both
  hands are in view, one-hand gestures don't run. In `bindings.toml` a pair is
  written `gesture = ["fist", "peace"]`.
- A setup guide, styled as a short lab experiment, that opens the first time
  palm-lab starts and from Settings > Your hand > Setup guide. It checks the
  camera, measures your hand, tests the four built-in gestures, has you build
  a first shortcut with the same drag-and-drop pieces as the Gestures page and
  run it for real, then offers Start with Windows.
- palm-lab tunes itself to your hand: the guide measures your open hand and
  your fist, and each finger counts as up by your own measurements instead of
  a one-size-fits-all rule. Settings > Your hand > Reset to standard undoes it.

### Changed

- A narrow gesture row shows fewer action chips instead of cutting one in
  half.
- palm-lab now looks for two hands in the camera instead of one.
- A custom gesture's name can't contain "+", because "+" joins the two
  shapes of a two-hand setup.

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

[Unreleased]: https://github.com/GpapoutsisPap/palm-lab/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/GpapoutsisPap/palm-lab/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/GpapoutsisPap/palm-lab/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/GpapoutsisPap/palm-lab/releases/tag/v0.1.0
