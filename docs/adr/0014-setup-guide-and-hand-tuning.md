# 14. A setup guide, and tuning finger detection to each hand

Date: 2026-10-08

## Status

Accepted.

## Context

A new user opens palm-lab to an empty list and has to discover the camera
switch, the editor and the gestures alone. And palm-lab reads every hand with
the same cut-offs: a finger is up when its tip is farther from the wrist than
its middle joint. Fingers that never fully curl, or never fully straighten,
sit near that line and flicker, so some gestures barely work for some people.

## Decision

- **A guided "experiment".** On first run, and from Settings > Setup guide,
  a full-window guide walks through seven steps: briefing, camera check,
  measuring the hand, testing each gesture, building a first shortcut, running
  it for real, and a lab report with a Start with Windows switch. The guide
  uses only the four built-in gestures; custom ones were checked when they
  were recorded.
- **The same editor, not a simplified one.** The first shortcut is built with
  the Gestures page's own drag-and-drop puzzle editor, drawn inside the guide
  for the chosen gesture's real row, so what someone learns in the guide is
  exactly how the app works afterwards. Gestures that already had a shortcut
  can't be picked, so the guide never changes one. The lab theme stays in a rack of test tubes that fills per
  step and a tube on each pose or gesture under test, not in illustration.
- **Shown until finished or skipped.** A `guide_done` setting, false by
  default, so it also opens once for people upgrading from an earlier version.
  Skipping puts the camera back as it was; finishing leaves tracking on.
- **Nothing runs while checking.** The engine gains a quiet mode (gestures
  are read and reported, never run) for the gesture test, and never runs
  anything while measuring. Only the trial-run step runs a shortcut, and the
  guide says so before it does.
- **Measuring, then deciding.** `features.py` now measures a hand (the
  tip-over-joint ratio per finger, and the thumb's distance and side) and
  decides separately, against a `HandProfile` of cut-offs. The standard
  profile gives exactly the old answers, which a test checks on every recorded
  hand.
- **Tuning the four fingers.** The guide measures about a second each of an
  open hand and a fist (skipping the first few frames while the hand
  settles). Each finger's cut-off goes halfway between the open hand's low
  readings and the fist's high readings (10th and 90th percentiles), kept
  between 0.8 and 1.2. A finger that barely changes keeps the standard cut-off;
  if fewer than two change, the poses are refused as probably wrong.
- **Not the thumb.** In the recorded hands a peace sign's tucked thumb
  measures 0.43 to 0.63 from the index knuckle, overlapping an open hand's
  thumb (0.46 and up). An open hand and a fist can't separate those, and
  tuning the thumb from them lowered accuracy on the recordings from 96% to
  90%, so the thumb keeps its standard two-check rule.
- **Its own file.** The tuning lives in `hand.toml`, separate from settings,
  so deleting it, or Settings > Your hand > Reset to standard, undoes it.

## Consequences

Each person gets cut-offs from their own hand, and a new user ends the first
two minutes with a working shortcut they've seen run. Tuning the thumb would
need a pose that separates a tucked thumb from an extended one (a peace sign
and a thumbs up, say); that is left for later.
