"""Tests for the pop-up by the clock: what it says, and when it stays quiet."""

import sys
import time
from dataclasses import replace

import pytest

from palm_lab.actions.errors import LaunchFailedError
from palm_lab.actions.models import Action, ActionType
from palm_lab.actions.runner import ActionResult
from palm_lab.engine import FiredEvent
from palm_lab.overlay import (
    QUNS_ACCEPTS_NOTIFICATIONS,
    QUNS_BUSY,
    QUNS_PRESENTATION_MODE,
    QUNS_QUIET_TIME,
    QUNS_RUNNING_D3D_FULL_SCREEN,
    Overlay,
    busy,
    card_position,
    card_width,
    scaled,
)
from palm_lab.run_popup import (
    FAILURE_SECONDS,
    SUCCESS_SECONDS,
    PopupMessage,
    RunPopup,
    gesture_label,
    message_for,
    sample_runs,
)

ACTION = Action(type=ActionType.LAUNCH, target="spotify")
OK = ActionResult(action=ACTION)
FAILED = ActionResult(action=ACTION, error=LaunchFailedError("spotify", "it's not installed"))


def ran(results: tuple[ActionResult, ...] = (OK,), **changes: object) -> FiredEvent:
    event = FiredEvent(
        gesture="peace", binding_name="Morning setup", at=0.0, results=results, finished=True, id=1
    )
    return replace(event, **changes)  # type: ignore[arg-type]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Harness:
    def __init__(self, mode: str = "all", in_front: bool = False, busy: bool = False) -> None:
        self.shown: list[PopupMessage] = []
        self.notified: list[tuple[str, str]] = []
        self.mode, self.in_front, self.busy = mode, in_front, busy
        self.clock = Clock()
        self.popup = RunPopup(
            show=self.shown.append,
            mode=lambda: self.mode,
            window_in_front=lambda: self.in_front,
            user_busy=lambda: self.busy,
            notify=lambda title, detail: self.notified.append((title, detail)),
            clock=self.clock,
        )


# What it says -------------------------------------------------------------------------


def test_a_success_names_the_shortcut_and_the_gesture() -> None:
    message = message_for(ran())
    assert (message.title, message.detail, message.failed) == (
        "Ran Morning setup",
        "Peace sign",
        False,
    )
    assert message.seconds == SUCCESS_SECONDS


def test_a_failure_says_what_went_wrong_and_stays_longer() -> None:
    message = message_for(ran((FAILED,)))
    assert message.title == "Morning setup didn’t work"
    assert "spotify" in message.detail
    assert message.failed and message.seconds == FAILURE_SECONDS


def test_a_run_that_half_worked_says_how_much_failed() -> None:
    message = message_for(ran((OK, FAILED, OK)))
    assert message.title == "Morning setup ran, 1 of 3 steps failed"
    assert message.failed


def test_a_long_error_is_shortened() -> None:
    long = ActionResult(action=ACTION, error=LaunchFailedError("x", "word " * 60))
    assert len(message_for(ran((long,))).detail) <= 90


@pytest.mark.parametrize(
    ("gesture", "label"),
    [("peace", "Peace sign"), ("fist + peace", "Fist + Peace sign"), ("Three up", "Three up")],
)
def test_gestures_are_named_as_in_the_window(gesture: str, label: str) -> None:
    assert gesture_label(gesture) == label


# When it shows ------------------------------------------------------------------------


def test_a_run_shows_a_card() -> None:
    h = Harness()
    h.popup.on_run(ran())
    assert [m.title for m in h.shown] == ["Ran Morning setup"]


def test_nothing_shows_while_palm_labs_own_window_is_in_front() -> None:
    h = Harness(in_front=True)
    h.popup.on_run(ran((FAILED,)))
    assert h.shown == [] and h.notified == []


def test_failures_only_mode_skips_successes() -> None:
    h = Harness(mode="failures")
    h.popup.on_run(ran())
    h.popup.on_run(ran((FAILED,)))
    assert [m.failed for m in h.shown] == [True]


def test_off_means_off() -> None:
    h = Harness(mode="off")
    h.popup.on_run(ran((FAILED,)))
    assert h.shown == [] and h.notified == []


def test_runs_from_the_window_and_unset_gestures_show_nothing() -> None:
    h = Harness()
    h.popup.on_run(ran(manual=True))
    h.popup.on_run(ran(binding_name=None))
    assert h.shown == []


def test_when_busy_a_success_is_dropped_and_a_failure_becomes_a_notification() -> None:
    """Windows itself holds the notification back until the game or presentation ends."""
    h = Harness(busy=True)
    h.popup.on_run(ran())
    h.popup.on_run(ran((FAILED,)))
    assert h.shown == []
    assert [title for title, _ in h.notified] == ["Morning setup didn’t work"]


def test_a_repeat_while_showing_counts_up_instead_of_stacking() -> None:
    h = Harness()
    h.popup.on_run(ran())
    h.clock.now = 1.0
    h.popup.on_run(ran())
    assert [m.count for m in h.shown] == [1, 2]
    assert h.shown[1].detail_line == "Peace sign  ×2"
    h.clock.now = 1.0 + SUCCESS_SECONDS + 0.1  # the second card has gone
    h.popup.on_run(ran())
    assert h.shown[-1].count == 1


def test_the_sample_runs_show_a_success_a_repeat_and_a_failure() -> None:
    """`palm-lab popup` feeds these through RunPopup, so they follow the real rules."""
    h = Harness()
    for _, event, pause in sample_runs():
        h.popup.on_run(event)
        h.clock.now += pause
    assert [(m.title, m.count, m.failed) for m in h.shown] == [
        ("Ran Morning setup", 1, False),
        ("Ran Morning setup", 2, False),
        ("Start my day ran, 1 of 3 steps failed", 1, True),
    ]


# The card's maths ------------------------------------------------------------------------


def test_the_card_sits_above_the_taskbar_on_the_right() -> None:
    work_area = (0, 0, 1920, 1032)  # a 48px taskbar at the bottom
    assert card_position(work_area, (300, 60), 96) == (1920 - 300 - 12, 1032 - 60 - 12)


def test_the_card_scales_with_the_display() -> None:
    assert scaled(60, 144) == 90
    assert card_width(0, 96) == 240  # never narrower than this
    assert card_width(10_000, 96) == 420  # nor wider
    assert card_width(10_000, 192) == 840


@pytest.mark.parametrize(
    ("state", "is_busy"),
    [
        (QUNS_ACCEPTS_NOTIFICATIONS, False),
        (QUNS_QUIET_TIME, False),
        (QUNS_BUSY, True),
        (QUNS_RUNNING_D3D_FULL_SCREEN, True),
        (QUNS_PRESENTATION_MODE, True),
        (None, False),  # the check failed: a pop-up beats silence
    ],
)
def test_busy_follows_windows(state: int | None, is_busy: bool) -> None:
    assert busy(state) is is_busy


def test_the_overlay_does_nothing_off_windows() -> None:
    overlay = Overlay(dark=lambda: False)
    overlay.start()
    overlay.show(message_for(ran()))  # no window, no error
    assert overlay.available is (sys.platform == "win32")
    overlay.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="draws a real Windows window")
def test_the_card_opens_shows_and_closes_on_windows() -> None:
    """A smoke test: the real window appears for a moment and goes away cleanly."""
    overlay = Overlay(dark=lambda: True)
    overlay.start()
    assert overlay.available
    overlay.show(message_for(ran((FAILED,))))
    time.sleep(0.3)
    overlay.stop()
    time.sleep(0.1)
