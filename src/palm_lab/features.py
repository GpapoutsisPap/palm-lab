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
FINGERS = tuple(FINGER_JOINTS)
# A finger is up when its tip is farther from the wrist than its middle joint,
# so the standard cut-off for tip distance / joint distance is exactly 1.
STANDARD_FINGER_THRESHOLD = 1.0

FourFloats = tuple[float, float, float, float]


@dataclass(frozen=True)
class HandProfile:
    """Where the line between "up" and "down" sits, for one person's hand.

    finger_thresholds holds, for index, middle, ring and pinky, the ratio of
    tip-to-wrist over middle-joint-to-wrist distance above which that finger
    counts as up. thumb_distance is how far (in palm-size units) the thumb tip
    must be from the index knuckle. The defaults suit most hands; the setup
    guide can tune them (see palm_lab.hand_profile).
    """

    finger_thresholds: FourFloats = (STANDARD_FINGER_THRESHOLD,) * 4
    thumb_distance: float = THUMB_MIN_DISTANCE


STANDARD_PROFILE = HandProfile()


@dataclass(frozen=True)
class HandMeasurement:
    """The raw numbers behind a hand's shape, before any cut-off is applied."""

    finger_ratios: FourFloats  # tip / middle joint distance from the wrist
    thumb_distance: float  # thumb tip to index knuckle
    thumb_outside_palm: bool


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


def _extension_ratio(hand: list[Point], pip: int, tip: int) -> float:
    """How far the tip is from the wrist, relative to the middle joint.

    Above 1, the tip is farther out than the joint: the finger is straight.
    """
    wrist = hand[WRIST]
    joint = distance(wrist, hand[pip])
    return distance(wrist, hand[tip]) / joint if joint > 0 else 0.0


def _cross_sign(origin: Point, toward: Point, target: Point) -> float:
    """2D cross product of origin->toward and origin->target.

    The sign says which side of the line the target falls on.
    """
    return (toward.x - origin.x) * (target.y - origin.y) - (toward.y - origin.y) * (
        target.x - origin.x
    )


def _thumb_outside_palm(hand: list[Point]) -> bool:
    palm_side = _cross_sign(hand[INDEX_MCP], hand[PINKY_MCP], hand[WRIST])
    thumb_side = _cross_sign(hand[INDEX_MCP], hand[PINKY_MCP], hand[THUMB_TIP])
    return (palm_side > 0) == (thumb_side > 0)


def measure(hand: list[Point]) -> HandMeasurement:
    """Measure a normalised hand without deciding anything yet."""
    ratios = tuple(_extension_ratio(hand, *FINGER_JOINTS[name]) for name in FINGERS)
    return HandMeasurement(
        finger_ratios=(ratios[0], ratios[1], ratios[2], ratios[3]),
        thumb_distance=distance(hand[INDEX_MCP], hand[THUMB_TIP]),
        thumb_outside_palm=_thumb_outside_palm(hand),
    )


def features_from(
    reading: HandMeasurement, profile: HandProfile = STANDARD_PROFILE
) -> HandFeatures:
    """Decide which fingers are up, using one hand's cut-offs.

    The thumb is extended when it sits outside the palm *and* far from
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
    up = [
        ratio > threshold
        for ratio, threshold in zip(reading.finger_ratios, profile.finger_thresholds, strict=True)
    ]
    return HandFeatures(
        thumb=reading.thumb_outside_palm and reading.thumb_distance > profile.thumb_distance,
        index=up[0],
        middle=up[1],
        ring=up[2],
        pinky=up[3],
    )


def extract(hand: list[Point], profile: HandProfile = STANDARD_PROFILE) -> HandFeatures:
    """Reduce 21 landmarks to five booleans describing hand shape."""
    return features_from(measure(hand), profile)
