"""Two-stage capture of a new gesture shape, for the "Add gesture" flow.

Recording a gesture is just reading the same five-finger tuple that
classify() already works with (see palm_lab.gestures), held steady twice in
a row with the hand dropped in between, so a shaky single reading never gets
saved by accident. Turning an accepted capture into a saved one is
palm_lab.custom_gestures' job; this module only decides when a capture is
accepted.
"""

from dataclasses import dataclass, field

from palm_lab.features import HandFeatures
from palm_lab.gestures import FingerTuple

DEFAULT_HOLD_SECONDS = 0.8
MISMATCH_DISPLAY_SECONDS = 1.5


@dataclass(frozen=True)
class CaptureStatus:
    """What the "Add gesture" wizard should show right now."""

    stage: str  # "hold", "release", "done", "mismatch", or "taken" (set by the engine)
    attempt: int  # 1 or 2
    progress: float  # 0..1 fraction of the current hold's dwell
    fingers: FingerTuple | None = None  # set once stage == "done" (or "taken")
    first: FingerTuple | None = None  # the shape the first hold recorded, once it has
    matches: str | None = None  # the existing gesture that shape belongs to ("taken")


@dataclass
class GestureCapture:
    """Feed it one reading per frame via `update()`.

    Two holds of `hold_seconds`, of the identical shape, with the hand
    dropped in between, are required before a capture is accepted. A
    mismatched second hold shows "mismatch" briefly, then restarts from the
    first hold.
    """

    hold_seconds: float = DEFAULT_HOLD_SECONDS

    _attempt: int = field(default=1, init=False)
    _first: FingerTuple | None = field(default=None, init=False)
    _current: FingerTuple | None = field(default=None, init=False)
    _held_since: float | None = field(default=None, init=False)
    _awaiting_release: bool = field(default=False, init=False)
    _mismatch_until: float | None = field(default=None, init=False)

    def reset(self) -> None:
        """Start over from the first hold."""
        self._attempt = 1
        self._first = None
        self._current = None
        self._held_since = None
        self._awaiting_release = False
        self._mismatch_until = None

    def update(self, features: HandFeatures | None, now: float) -> CaptureStatus:
        """Record one frame's reading and say what the wizard should show."""
        if self._mismatch_until is not None:
            if now < self._mismatch_until:
                return CaptureStatus(stage="mismatch", attempt=1, progress=0.0)
            self.reset()

        shape = features.as_tuple() if features is not None else None

        if self._awaiting_release:
            if shape is None or shape != self._first:
                self._awaiting_release = False
                self._current = None
                self._held_since = None
            return CaptureStatus(stage="release", attempt=2, progress=0.0, first=self._first)

        if shape is None:
            self._current = None
            self._held_since = None
            return CaptureStatus(
                stage="hold", attempt=self._attempt, progress=0.0, first=self._first
            )

        if shape != self._current:
            self._current = shape
            self._held_since = now

        assert self._held_since is not None
        elapsed = now - self._held_since
        if elapsed < self.hold_seconds:
            progress = 0.0 if self.hold_seconds <= 0 else min(elapsed / self.hold_seconds, 1.0)
            return CaptureStatus(
                stage="hold", attempt=self._attempt, progress=progress, first=self._first
            )

        # This hold just completed.
        if self._attempt == 1:
            self._first = shape
            self._attempt = 2
            self._awaiting_release = True
            self._current = None
            self._held_since = None
            return CaptureStatus(stage="release", attempt=2, progress=0.0, first=shape)

        if shape == self._first:
            fingers = shape
            self.reset()
            return CaptureStatus(
                stage="done", attempt=2, progress=1.0, fingers=fingers, first=fingers
            )

        self._mismatch_until = now + MISMATCH_DISPLAY_SECONDS
        self._first = None
        self._current = None
        self._held_since = None
        return CaptureStatus(stage="mismatch", attempt=1, progress=0.0)
