"""Derive interpretable shape features from normalised hand landmarks."""

from dataclasses import dataclass

from palm_lab.landmarks import WRIST, Point, distance

INDEX_MCP = 5
FINGER_JOINTS = {
    "index": (6, 8),
    "middle": (10, 12),
    "ring": (14, 16),
    "pinky": (18, 20),
}
THUMB_TIP = 4
THUMB_EXTENDED_THRESHOLD = 0.45


@dataclass(frozen=True)
class HandFeatures:
    """Which fingers are extended, in a fixed order."""

    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool

    def as_tuple(self) -> tuple[bool, bool, bool, bool, bool]:
        """Return the five flags as a tuple, for matching against rules."""
        return (self.thumb, self.index, self.middle, self.ring, self.pinky)


def _is_extended(hand: list[Point], pip: int, tip: int) -> bool:
    """A finger is extended when its tip is farther from the wrist than its
    middle joint."""
    wrist = hand[WRIST]
    return distance(wrist, hand[tip]) > distance(wrist, hand[pip])


def _is_thumb_extended(hand: list[Point]) -> bool:
    """The thumb folds sideways rather than curling, so measure how far the
    tip sits from the index knuckle relative to hand size.

    Threshold derived from 42 captured fixtures; see scripts/measure_thumb.py.
    """
    return distance(hand[INDEX_MCP], hand[THUMB_TIP]) > THUMB_EXTENDED_THRESHOLD


def extract(hand: list[Point]) -> HandFeatures:
    """Reduce 21 landmarks to five booleans describing hand shape."""
    return HandFeatures(
        thumb=_is_thumb_extended(hand),
        index=_is_extended(hand, *FINGER_JOINTS["index"]),
        middle=_is_extended(hand, *FINGER_JOINTS["middle"]),
        ring=_is_extended(hand, *FINGER_JOINTS["ring"]),
        pinky=_is_extended(hand, *FINGER_JOINTS["pinky"]),
    )
