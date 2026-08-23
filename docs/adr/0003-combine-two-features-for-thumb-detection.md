# 3. Combine two features for thumb detection

Date: 2026-08-23

## Status

Accepted

## Context

The thumb folds sideways across the palm rather than curling toward the
wrist, so the test used for the other four fingers — tip farther from the
wrist than the middle joint — does not work on it. That test is correct on
all 48 captures for the other fingers and useless for the thumb.

A distance threshold was tried first: the thumb counts as extended when its
tip is more than 0.45 hand-widths from the index knuckle. Measured against
the 42 fixtures available at the time, this was 95% accurate. That figure was
misleading. Every fixture had been captured at roughly the same distance from
the camera. Adding six captures taken further back dropped accuracy to 83%,
because the measured distance drifts upward as the hand moves away and the
normalisation does not cancel it.

## Decision

The thumb counts as extended only when two independent checks agree.

The first is a sign test: the 2D cross product determines which side of the
index-knuckle to pinky-knuckle line the thumb tip falls on. This is
unaffected by hand size or camera distance, but the sign is decided by
landmark noise when the tip sits close to that line.

The second is the original distance test, with the threshold kept at 0.45.
That value was derived from the measured distribution across all fixtures
rather than chosen by hand; `scripts/measure_thumb.py` regenerates the
evidence.

Each check is wrong on a different set of captures, so requiring both raises
accuracy to 47 of 48.

An earlier attempt removed the z coordinate from the distance calculation, on
the theory that MediaPipe's depth estimate degrades with distance and was
corrupting the measurement. It made no difference to the overlap and produced
degenerate normalisation values on hands held edge-on, so it was reverted.

## Consequences

Thumb detection is now distance-invariant in a way neither check achieved
alone, and because the two failure modes are independent, requiring agreement
is substantially stronger than tuning either one further.

The cost is that this remains a hand-written rule with a constant calibrated
against one person's hand, one camera, and one set of lighting conditions. It
will generalise to other users worse than the measured figure suggests. Three
captures still fail and are recorded as `xfail` rather than removed, so that
any future change which fixes them reports XPASS.

A further distance clause would have rescued the remaining failure and reached
48 of 48. It was not added, because the threshold would have been fitted to a
single sample rather than justified by hand geometry.

This approach has a ceiling. Every gesture that depends on thumb position will
push against the same limitation, and the answer is eventually a classifier
learned over the full landmark vector rather than more hand-tuned geometry.
