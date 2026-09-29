"""Tests for the dwell and cooldown state machine."""

import pytest

from palm_lab.state import GestureTrigger, TriggerState


def test_does_not_fire_before_dwell_completes() -> None:
    """A gesture held for less than the dwell time does not fire."""
    trigger = GestureTrigger(dwell_seconds=1.0)
    assert trigger.update("peace", 0.0) is None
    assert trigger.update("peace", 0.5) is None
    assert trigger.update("peace", 0.9) is None


def test_fires_once_dwell_completes() -> None:
    """A gesture held for the full dwell time fires."""
    trigger = GestureTrigger(dwell_seconds=1.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"


def test_does_not_fire_twice_while_held() -> None:
    """Continuing to hold a fired gesture produces no further events."""
    trigger = GestureTrigger(dwell_seconds=1.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"
    assert trigger.update("peace", 1.1) is None
    assert trigger.update("peace", 5.0) is None
    assert trigger.update("peace", 60.0) is None


def test_different_gesture_fires_during_another_cooldown() -> None:
    """Cooldowns are tracked per gesture, not globally."""
    trigger = GestureTrigger(dwell_seconds=1.0, cooldown_seconds=5.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"
    trigger.update("fist", 2.0)
    assert trigger.update("fist", 3.0) == "fist"


def test_same_gesture_blocked_during_cooldown() -> None:
    """Repeating a gesture within its cooldown window does not fire."""
    trigger = GestureTrigger(dwell_seconds=1.0, cooldown_seconds=5.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"
    trigger.update(None, 2.0)
    trigger.update("peace", 3.0)
    assert trigger.update("peace", 4.0) is None


def test_same_gesture_fires_after_cooldown_expires() -> None:
    """Once the cooldown has elapsed the gesture can fire again."""
    trigger = GestureTrigger(dwell_seconds=1.0, cooldown_seconds=5.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"
    trigger.update(None, 2.0)
    trigger.update("peace", 10.0)
    assert trigger.update("peace", 11.0) == "peace"


def test_losing_the_hand_cancels_an_in_progress_dwell() -> None:
    """Dropping the hand mid-dwell resets progress rather than resuming."""
    trigger = GestureTrigger(dwell_seconds=1.0)
    trigger.update("peace", 0.0)
    trigger.update("peace", 0.9)
    trigger.update(None, 0.95)
    trigger.update("peace", 1.0)
    assert trigger.update("peace", 1.5) is None
    assert trigger.update("peace", 2.0) == "peace"


def test_switching_gestures_restarts_the_dwell() -> None:
    """Time held on one gesture does not count toward another."""
    trigger = GestureTrigger(dwell_seconds=1.0)
    trigger.update("peace", 0.0)
    trigger.update("peace", 0.9)
    trigger.update("fist", 1.0)
    assert trigger.update("fist", 1.5) is None
    assert trigger.update("fist", 2.0) == "fist"


def test_reset_does_not_clear_cooldowns() -> None:
    """Dropping the hand is not a way to bypass a cooldown."""
    trigger = GestureTrigger(dwell_seconds=1.0, cooldown_seconds=5.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"
    trigger.reset()
    trigger.update("peace", 2.0)
    assert trigger.update("peace", 3.0) is None


def test_never_fired_gesture_is_not_on_cooldown_at_low_timestamps() -> None:
    """A gesture that has never fired is never treated as cooling down."""
    trigger = GestureTrigger(dwell_seconds=0.5, cooldown_seconds=100.0)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", 1.0) == "peace"


@pytest.mark.parametrize("dwell", [0.1, 0.5, 1.0, 2.0])
def test_dwell_is_configurable(dwell: float) -> None:
    """The dwell threshold is honoured at any configured value."""
    trigger = GestureTrigger(dwell_seconds=dwell)
    trigger.update("peace", 0.0)
    assert trigger.update("peace", dwell - 0.01) is None
    assert trigger.update("peace", dwell) == "peace"


# What the window shows about the hold in progress ---------------------------


def test_nothing_recognised_is_idle() -> None:
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    assert trigger.state(0.0) == TriggerState()
    trigger.update(None, 0.0)
    assert trigger.state(0.1).phase == "idle"


def test_a_hold_fills_towards_firing() -> None:
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    trigger.update("peace", 10.0)
    trigger.update("peace", 10.4)
    state = trigger.state(10.4)
    assert state.phase == "holding"
    assert state.gesture == "peace"
    assert state.progress == pytest.approx(0.5)


def test_after_firing_it_says_fired_and_counts_down_the_cooldown() -> None:
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    trigger.update("peace", 10.0)
    assert trigger.update("peace", 10.8) == "peace"
    state = trigger.state(11.8)
    assert state.phase == "fired"
    assert state.progress == 1.0
    assert state.cooldown_remaining == pytest.approx(4.0)


def test_showing_it_again_too_soon_says_cooling_down() -> None:
    """The commonest reason a correct gesture seems to do nothing."""
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    trigger.update("peace", 10.0)
    trigger.update("peace", 10.8)
    trigger.update(None, 11.0)
    trigger.update("peace", 12.0)
    state = trigger.state(12.5)
    assert state.phase == "cooldown"
    assert state.cooldown_remaining == pytest.approx(3.3)


def test_a_hold_that_outlasts_its_cooldown_asks_for_a_fresh_start() -> None:
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    trigger.update("peace", 10.0)
    trigger.update("peace", 10.8)  # fires
    trigger.update(None, 11.0)
    trigger.update("peace", 11.1)
    trigger.update("peace", 12.0)  # dwell complete, blocked by the cooldown
    assert trigger.state(16.0).phase == "rearm"


def test_another_gesture_is_not_held_back_by_the_first_ones_cooldown() -> None:
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    trigger.update("peace", 10.0)
    trigger.update("peace", 10.8)
    trigger.update("fist", 11.0)
    assert trigger.state(11.2).phase == "holding"


def test_reading_the_state_changes_nothing() -> None:
    trigger = GestureTrigger(dwell_seconds=0.8, cooldown_seconds=5.0)
    trigger.update("peace", 10.0)
    trigger.state(10.5)
    trigger.state(10.9)
    assert trigger.update("peace", 10.8) == "peace"
