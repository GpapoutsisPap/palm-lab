# 18. Check how a hand is held, not just which fingers are out

Date: 2026-10-22

## Status

Accepted.

## Context

A gesture is which of the five fingers are straight (palm_lab.gestures).
Hands at rest often have the right fingers straight: a hand against the chin
with all five out read as an open palm and ran its shortcut. The hold time
helps against passing shapes, not against a hand that rests for minutes.

What differs is how the hand is *held*. In every recorded gesture
(tests/fixtures, 48 captures), the hand points up (the wrist-to-middle-knuckle
line within 51 degrees of vertical) and the palm or the back of the hand faces
the camera (the width across the knuckles is at least 0.59 of the palm's
length). The hand from the bug report pointed about 110 degrees from up and was
seen side on, where that width drops to about 0.2. A thumbs up is the
exception: side on by nature, but its thumb points up (within 37 degrees).

## Decision

- **Three checks, after the finger shape** (palm_lab.pose): palm to the
  camera, pointing up, and for the thumb alone, the thumb pointing up. A shape
  that fails is not a gesture: it doesn't hold, run or start a cooldown.
- **Measured in true proportions.** MediaPipe gives landmarks as fractions of
  the frame's width and height, so x is stretched by the frame's aspect ratio
  first; otherwise every angle on a 16:9 camera is off.
- **A setting, Strictness,** with Normal as the default (palm width 0.45,
  70 degrees, thumb 50), Strict (0.55, 55, 40) and Relaxed (no checks, the
  old behaviour). Limits leave a margin over the recorded gestures at both
  4:3 and 16:9, and a test checks every capture passes at every level.
- **Say why.** The engine keeps the shape it saw and the problem, and the live
  view reads "Open palm not counted / Point your fingers up" instead of a
  silent "Hand in view". The setup guide shows the same hint while testing.
- **Two hands:** if either is held wrong, the pair doesn't count, as with an
  unrecognised shape.

## Consequences

Accidental runs from resting hands drop sharply, and a hand that *is* meant as
a gesture gets told how to fix itself.

Gestures made deliberately sideways or downward (pointing at something, say)
can't be used at Normal or Strict. Relaxed is the way out, for everything at
once; a per-gesture setting can come later if anyone needs it.

The finger-shape code still works on unstretched landmarks. It hasn't caused
trouble, but rotating a recorded hand in a test changes its thumb reading,
which is a sign that it should get the same aspect correction one day.
