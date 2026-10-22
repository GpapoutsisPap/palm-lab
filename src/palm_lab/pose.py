"""Is the hand held up like a gesture, or just resting with the right fingers out?

palm_lab.gestures only asks which fingers are straight. A hand resting
against your chin, or hanging by the keyboard, can have all five straight
and so look like an open palm. Real gestures differ in how the hand is
*held*, so before a gesture counts, three things are checked:

- **Palm to the camera.** Seen from the side, the four knuckles bunch
  together. The width across the knuckles (index to pinky), against the
  palm's length (wrist to middle knuckle), drops from about 0.6 and up when
  the palm or the back of the hand faces the camera to about 0.2 side on.
- **Pointing up.** The palm's line (wrist to middle knuckle) must point within
  some angle of straight up. A resting hand points sideways or down.
- **Thumb up, for thumbs up.** A thumbs up is side on by nature, so it skips
  the palm check; instead the thumb itself (base to tip) must point up.

Every shape except the thumb alone gets the first two checks. Relaxed skips
all of it, as palm-lab did before.

Measured on the recorded gestures in tests/fixtures (every one passes Strict):
palm width 0.59 and up, palm line within 51 degrees of up, thumb within 37
degrees of up. Your hand on your chin pointed about 110 degrees from up.

Landmarks arrive as fractions of the frame's width and height, so x is first
stretched by the frame's aspect ratio; otherwise a wide camera would make
every angle and width wrong.
"""

import math
from dataclasses import dataclass

from palm_lab.landmarks import MIDDLE_MCP, WRIST, Point

INDEX_MCP = 5
PINKY_MCP = 17
THUMB_MCP = 2
THUMB_TIP = 4
DEFAULT_ASPECT = 4 / 3  # most webcams, when the frame size isn't known

FingerTuple = tuple[bool, bool, bool, bool, bool]

STRICTNESS_LEVELS = ("relaxed", "normal", "strict")
DEFAULT_STRICTNESS = "normal"


@dataclass(frozen=True)
class PoseLimits:
    """How far from the ideal a hand may be held and still count."""

    min_palm_width: float  # knuckle width / palm length
    max_tilt: float  # degrees the palm may lean from straight up
    max_thumb_tilt: float  # degrees the thumb may lean from straight up, for thumbs up


LIMITS: dict[str, PoseLimits] = {
    "normal": PoseLimits(min_palm_width=0.45, max_tilt=70.0, max_thumb_tilt=50.0),
    "strict": PoseLimits(min_palm_width=0.55, max_tilt=55.0, max_thumb_tilt=40.0),
}

# What went wrong, as the window words it (see app.js, TEXT.pose).
PALM = "palm"  # not facing the camera
UPRIGHT = "upright"  # not pointing up
THUMB = "thumb"  # a thumbs up whose thumb isn't up


@dataclass(frozen=True)
class HandPose:
    """How a hand is held, separate from which fingers are out."""

    palm_width: float
    tilt: float  # degrees of the palm line from straight up, 0..180
    thumb_tilt: float  # degrees of the thumb from straight up, 0..180


def _tilt(dx: float, dy: float) -> float:
    """Degrees from straight up (screen y grows downward), 0 to 180."""
    return abs(math.degrees(math.atan2(dx, -dy)))


def measure_pose(hand: list[Point], aspect: float = DEFAULT_ASPECT) -> HandPose:
    """Measure how a hand is held, from MediaPipe's landmarks (fractions of the frame)."""
    if len(hand) != 21:
        raise ValueError(f"Expected 21 landmarks, got {len(hand)}")
    points = [(p.x * aspect, p.y) for p in hand]
    wrist, middle = points[WRIST], points[MIDDLE_MCP]
    length = math.dist(wrist, middle)
    if length == 0:
        raise ValueError("Degenerate hand: wrist and middle knuckle coincide")
    thumb_base, thumb_tip = points[THUMB_MCP], points[THUMB_TIP]
    return HandPose(
        palm_width=math.dist(points[INDEX_MCP], points[PINKY_MCP]) / length,
        tilt=_tilt(middle[0] - wrist[0], middle[1] - wrist[1]),
        thumb_tilt=_tilt(thumb_tip[0] - thumb_base[0], thumb_tip[1] - thumb_base[1]),
    )


def pose_problem(fingers: FingerTuple, pose: HandPose, strictness: str) -> str | None:
    """Why this hand isn't held like a gesture (PALM, UPRIGHT or THUMB), or None if it is."""
    limits = LIMITS.get(strictness)
    if limits is None:  # relaxed: the fingers alone decide
        return None
    if fingers == (True, False, False, False, False):  # the thumb alone: thumbs up
        return THUMB if pose.thumb_tilt > limits.max_thumb_tilt else None
    if pose.palm_width < limits.min_palm_width:
        return PALM
    if pose.tilt > limits.max_tilt:
        return UPRIGHT
    return None
