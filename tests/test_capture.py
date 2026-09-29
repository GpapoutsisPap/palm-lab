"""Tests for the two-hold gesture capture state machine."""

from palm_lab.capture import CaptureStatus, GestureCapture
from palm_lab.features import HandFeatures

THREE_UP = HandFeatures(thumb=False, index=True, middle=True, ring=True, pinky=False)
ROCK_ON = HandFeatures(thumb=False, index=True, middle=False, ring=False, pinky=True)


def hold_until_change(
    capture: GestureCapture, shape: HandFeatures, start: float, step: float = 0.05
) -> tuple[CaptureStatus, float]:
    """Feed `shape` until the stage moves past "hold". Returns (status, now)."""
    now = start
    status = capture.update(shape, now)
    steps = 0
    while status.stage == "hold" and steps < 200:
        now += step
        status = capture.update(shape, now)
        steps += 1
    return status, now


def test_a_single_hold_is_not_enough_to_finish() -> None:
    capture = GestureCapture(hold_seconds=0.3)
    status, _ = hold_until_change(capture, THREE_UP, start=0.0)
    assert status.stage == "release"
    assert status.fingers is None


def test_two_matching_holds_with_a_release_between_them_complete() -> None:
    capture = GestureCapture(hold_seconds=0.3)
    status, now = hold_until_change(capture, THREE_UP, start=0.0)
    assert status.stage == "release"

    released = capture.update(None, now + 0.1)  # hand drops
    assert released.stage == "release"

    status, _ = hold_until_change(capture, THREE_UP, start=now + 0.2)
    assert status.stage == "done"
    assert status.fingers == THREE_UP.as_tuple()


def test_progress_climbs_toward_one_during_a_hold() -> None:
    capture = GestureCapture(hold_seconds=1.0)
    early = capture.update(THREE_UP, 0.0)
    later = capture.update(THREE_UP, 0.5)
    assert early.progress < later.progress < 1.0


def test_losing_the_hand_mid_hold_resets_progress() -> None:
    capture = GestureCapture(hold_seconds=1.0)
    capture.update(THREE_UP, 0.0)
    capture.update(THREE_UP, 0.5)
    capture.update(None, 0.6)  # hand lost
    status = capture.update(THREE_UP, 0.65)
    assert status.progress < 0.1  # started over, not resumed


def test_changing_shape_mid_hold_restarts_the_timer() -> None:
    capture = GestureCapture(hold_seconds=1.0)
    capture.update(THREE_UP, 0.0)
    capture.update(THREE_UP, 0.5)
    status = capture.update(ROCK_ON, 0.6)  # different shape entirely
    assert status.progress < 0.1


def test_holding_through_the_release_stage_does_not_start_the_second_hold() -> None:
    capture = GestureCapture(hold_seconds=0.2)
    status, now = hold_until_change(capture, THREE_UP, start=0.0)
    assert status.stage == "release"
    for _ in range(5):
        now += 0.1
        status = capture.update(THREE_UP, now)
        assert status.stage == "release"


def test_a_mismatched_second_hold_reports_mismatch() -> None:
    capture = GestureCapture(hold_seconds=0.2)
    _, now = hold_until_change(capture, THREE_UP, start=0.0)
    capture.update(None, now + 0.1)  # release
    status, _ = hold_until_change(capture, ROCK_ON, start=now + 0.2)
    assert status.stage == "mismatch"
    assert status.fingers is None


def test_mismatch_display_holds_briefly_then_auto_resets() -> None:
    capture = GestureCapture(hold_seconds=0.1)
    _, now = hold_until_change(capture, THREE_UP, start=0.0)
    capture.update(None, now + 0.1)  # release
    status, now = hold_until_change(capture, ROCK_ON, start=now + 0.2)
    assert status.stage == "mismatch"

    assert capture.update(None, now + 0.1).stage == "mismatch"  # still showing it
    after = capture.update(THREE_UP, now + 2.0)  # well past the display window
    assert after.stage == "hold"
    assert after.attempt == 1


def test_reset_returns_to_the_first_attempt() -> None:
    capture = GestureCapture(hold_seconds=0.2)
    hold_until_change(capture, THREE_UP, start=0.0)
    capture.reset()
    status = capture.update(THREE_UP, 100.0)
    assert status.attempt == 1
    assert status.stage == "hold"


def test_the_first_hold_reports_the_shape_it_recorded() -> None:
    """The engine needs it to say "you already have this" before a second hold."""
    capture = GestureCapture(hold_seconds=0.3)
    status, now = hold_until_change(capture, THREE_UP, start=0.0)
    assert status.stage == "release"
    assert status.first == THREE_UP.as_tuple()
    status = capture.update(None, now + 0.1)
    assert status.first == THREE_UP.as_tuple()
