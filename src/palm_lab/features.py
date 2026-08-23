"""Derive interpretable shape features from normalised hand landmarks."""

from dataclasses import dataclass

from palm_lab.landmarks import WRIST, Point, distance

INDEX_MCP = 5
PINKY_MCP = 17
THUMB_TIP = 4
THUMB_MIN_DISTANCE = 0.45
FINGER_JOINTS = {
    "index": (6, 8),
    "middle": (10, 12),
    "ring": (14, 16),
    "pinky": (18, 20),
}


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


def _cross_sign(origin: Point, toward: Point, target: Point) -> float:
    """2D cross product of origin->toward and origin->target.

    The sign says which side of the line the target falls on.
    """
    return (toward.x - origin.x) * (target.y - origin.y) - (toward.y - origin.y) * (
        target.x - origin.x
    )


def _is_thumb_extended(hand: list[Point]) -> bool:
    """The thumb is extended when it sits outside the palm *and* far from
    the index knuckle.

    Two independent checks, because each alone is unreliable:

    - The cross-product sign says which side of the index-knuckle to
      pinky-knuckle line the thumb tip falls on. This is distance-invariant,
      but the sign is decided by noise when the tip sits near that line.
    - The distance from the index knuckle separates a clearly splayed thumb,
      but drifts upward as the hand moves away from the camera.

    Each is wrong on a different set of captures, so requiring both to agree
    is substantially better than either. See scripts/measure_thumb.py.
    """
    palm_side = _cross_sign(hand[INDEX_MCP], hand[PINKY_MCP], hand[WRIST])
    thumb_side = _cross_sign(hand[INDEX_MCP], hand[PINKY_MCP], hand[THUMB_TIP])
    outside_palm = (palm_side > 0) == (thumb_side > 0)
    far_enough = distance(hand[INDEX_MCP], hand[THUMB_TIP]) > THUMB_MIN_DISTANCE
    return outside_palm and far_enough


def extract(hand: list[Point]) -> HandFeatures:
    """Reduce 21 landmarks to five booleans describing hand shape."""
    return HandFeatures(
        thumb=_is_thumb_extended(hand),
        index=_is_extended(hand, *FINGER_JOINTS["index"]),
        middle=_is_extended(hand, *FINGER_JOINTS["middle"]),
        ring=_is_extended(hand, *FINGER_JOINTS["ring"]),
        pinky=_is_extended(hand, *FINGER_JOINTS["pinky"]),
    )
