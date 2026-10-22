# 13. Two-hand setups

Date: 2026-10-08

## Status

Accepted.

## Context

One-hand gestures go off by accident: a hand resting on a chin can read as
a fist or a thumbs up, held still for long enough to run its shortcut.
Requiring both hands is a far stronger signal that someone means it. Until
now palm-lab asked MediaPipe for one hand and read only that one.

## Decision

- **A pair of shapes you already have.** A two-hand setup is two existing
  gestures, built-in or custom, held up at once. Nothing new is recorded; the
  window offers two pickers. Both hands may make the same shape.
- **Either hand.** Fist + peace sign means the same setup whichever hand does
  which. MediaPipe's left/right guess is unreliable, and flips with a mirrored
  image, so the setup doesn't depend on it.
- **One key, everything else unchanged.** A pair is stored under one gesture
  key naming both shapes in sorted order, `"fist + peace"` (`combos.py`).
  Bindings, the trigger's hold and cooldown, the on/off switch and the
  Activity list all work with gesture keys already, so they needed no
  changes. Gesture names may no longer contain `+`, which keeps the key
  unambiguous.
- **A list in the file.** `bindings.toml` writes a pair as
  `gesture = ["fist", "peace"]`, in either order, rather than the key string,
  so a hand-edited file can't depend on the joining text. A `+` inside a
  plain gesture string is refused, with a message pointing at the list form.
- **Two hands in view means two-hand setups only.** With both hands up,
  one-hand gestures don't run, so making a pair never also fires the
  one-hand shortcut of either half. Two hands where either shape isn't
  recognised read as no gesture.
- **Bridging a lost hand.** MediaPipe sometimes drops one of two hands for a
  frame. For 0.3 s after a pair was seen, one of its halves alone still counts
  as the pair, so a flicker doesn't restart the hold.

## Consequences

People who keep a hand resting in view will find their one-hand gestures
don't run until it's lowered; the dialog that creates a pair says so. Finding
two hands costs MediaPipe a little more time per frame than one. Removing a
custom gesture also removes the two-hand setups made with it, and the window
says so.
