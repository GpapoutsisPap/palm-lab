"""Tests for the pose checks: a gesture counts only when the hand is held like one."""

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import fixture_paths, gesture_of, raw_hand

from palm_lab.engine import HandReading, frame_aspect, read_hand, read_hands
from palm_lab.gestures import BUILTIN_GESTURES
from palm_lab.landmarks import MIDDLE_MCP, WRIST, Point
from palm_lab.pose import (
    DEFAULT_ASPECT,
    PALM,
    STRICTNESS_LEVELS,
    THUMB,
    UPRIGHT,
    HandPose,
    measure_pose,
    pose_problem,
)

FINGERS_OF = {name: fingers for fingers, name in BUILTIN_GESTURES.items()}


def rotate_in_view(
    hand: list[Point], degrees: float, aspect: float = DEFAULT_ASPECT
) -> list[Point]:
    """Turn a hand around its wrist, as if the person tilted it (clockwise on screen)."""
    turn = math.radians(degrees)
    cos, sin = math.cos(turn), math.sin(turn)
    wx, wy = hand[WRIST].x * aspect, hand[WRIST].y
    turned = []
    for p in hand:
        x, y = p.x * aspect - wx, p.y - wy
        turned.append(Point((wx + x * cos - y * sin) / aspect, wy + x * sin + y * cos, p.z))
    return turned


def lean_to(hand: list[Point], degrees: float, aspect: float = DEFAULT_ASPECT) -> list[Point]:
    """Turn a hand so its palm line leans exactly this far from straight up (+ is right)."""
    dx = (hand[MIDDLE_MCP].x - hand[WRIST].x) * aspect
    dy = hand[MIDDLE_MCP].y - hand[WRIST].y
    return rotate_in_view(hand, degrees - math.degrees(math.atan2(dx, -dy)), aspect)


def turn_side_on(hand: list[Point], degrees: float, aspect: float = DEFAULT_ASPECT) -> list[Point]:
    """Roll a hand around its own length (wrist to middle knuckle), toward side on."""
    ax, ay = hand[WRIST].x * aspect, hand[WRIST].y
    bx, by = hand[MIDDLE_MCP].x * aspect, hand[MIDDLE_MCP].y
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length  # along the hand
    nx, ny = -uy, ux  # across the hand, in view
    turn = math.radians(degrees)
    rolled = []
    for p in hand:
        x, y, z = p.x * aspect - ax, p.y - ay, p.z * aspect
        along, across = x * ux + y * uy, x * nx + y * ny
        across, z = (
            across * math.cos(turn) - z * math.sin(turn),
            across * math.sin(turn) + z * math.cos(turn),
        )
        rolled.append(
            Point(
                (ax + along * ux + across * nx) / aspect, ay + along * uy + across * ny, z / aspect
            )
        )
    return rolled


# Every recorded gesture passes, at every level ------------------------------------


@pytest.mark.parametrize("path", fixture_paths(), ids=lambda path: path.stem)
@pytest.mark.parametrize("aspect", [4 / 3, 16 / 9], ids=["4:3", "16:9"])
@pytest.mark.parametrize("strictness", STRICTNESS_LEVELS)
def test_every_recorded_gesture_is_held_well_enough(
    path: Path, aspect: float, strictness: str
) -> None:
    """The fixtures are people making gestures on purpose: none may be refused for pose."""
    hand = [Point(**p) for p in json.loads(path.read_text())]
    hand = [Point(p.x / aspect * DEFAULT_ASPECT, p.y, p.z) for p in hand]  # as that camera sees it
    fingers = FINGERS_OF[gesture_of(path)]
    assert pose_problem(fingers, measure_pose(hand, aspect), strictness) is None


# Hands that only look like gestures ----------------------------------------------------


def test_a_hand_pointing_down_like_on_a_chin_is_not_an_open_palm() -> None:
    """The screenshot: all five fingers out, but pointing down and sideways."""
    resting = lean_to(raw_hand("open_palm"), 110)
    assert read_hand(resting) == HandReading(None, "open_palm", UPRIGHT)
    assert read_hand(resting, strictness="relaxed").gesture == "open_palm"


def test_a_hand_seen_side_on_is_not_counted() -> None:
    side_on = turn_side_on(raw_hand("open_palm"), 75)
    assert measure_pose(side_on).palm_width < 0.45
    assert read_hand(side_on).problem == PALM
    # Turned only a little, as anyone's hand is, it still counts.
    assert read_hand(turn_side_on(raw_hand("open_palm"), 25)).gesture == "open_palm"


def test_strict_is_stricter_than_normal() -> None:
    peace, thumb = FINGERS_OF["peace"], FINGERS_OF["thumbs_up"]
    leaning = HandPose(palm_width=0.8, tilt=62, thumb_tilt=0)
    narrow = HandPose(palm_width=0.5, tilt=0, thumb_tilt=0)
    thumb_leaning = HandPose(palm_width=0.8, tilt=0, thumb_tilt=45)
    assert [pose_problem(peace, leaning, level) for level in STRICTNESS_LEVELS] == [
        None,
        None,
        UPRIGHT,
    ]
    assert pose_problem(peace, narrow, "normal") is None
    assert pose_problem(peace, narrow, "strict") == PALM
    assert pose_problem(thumb, thumb_leaning, "normal") is None
    assert pose_problem(thumb, thumb_leaning, "strict") == THUMB


def test_a_thumbs_up_is_judged_by_its_thumb() -> None:
    thumbs_up = raw_hand("thumbs_up")
    assert read_hand(thumbs_up).gesture == "thumbs_up"
    thumbs_down = rotate_in_view(thumbs_up, 180)
    assert read_hand(thumbs_down).problem == THUMB


def test_a_fist_pointing_down_is_not_counted() -> None:
    assert read_hand(lean_to(raw_hand("fist"), 150)).problem == UPRIGHT


def test_two_hands_say_what_is_wrong_with_either() -> None:
    good, resting = raw_hand("fist"), lean_to(raw_hand("open_palm"), 110)
    assert read_hands([good, resting]) == HandReading(None, None, UPRIGHT)


def test_an_unrecognised_shape_has_no_problem_to_report() -> None:
    assert read_hand(raw_hand("open_palm"), rules={}) == HandReading(None)


# Measuring ------------------------------------------------------------------------------


def test_a_wide_camera_is_measured_in_true_proportions() -> None:
    hand = raw_hand("open_palm")
    stretched = [Point(p.x * 0.75, p.y, p.z) for p in hand]  # the same hand on a 16:9 frame
    a, b = measure_pose(hand, 4 / 3), measure_pose(stretched, 16 / 9)
    assert a.palm_width == pytest.approx(b.palm_width)
    assert a.tilt == pytest.approx(b.tilt)


def test_the_frame_size_gives_the_aspect() -> None:
    assert frame_aspect(SimpleNamespace(shape=(720, 1280, 3))) == pytest.approx(16 / 9)
    assert frame_aspect(object()) == DEFAULT_ASPECT
    assert frame_aspect(SimpleNamespace(shape=(0, 0))) == DEFAULT_ASPECT


def test_a_broken_hand_is_refused() -> None:
    with pytest.raises(ValueError, match="21 landmarks"):
        measure_pose([Point(0, 0, 0)])
    with pytest.raises(ValueError, match="Degenerate"):
        measure_pose([Point(0.5, 0.5, 0)] * 21)
