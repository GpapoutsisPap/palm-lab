"""Tests for what closing the window does."""

from collections.abc import Callable

import pytest

from palm_lab.settings import Settings
from palm_lab.ui.lifecycle import BACKGROUND_TITLE, QUIT_DELAY_SECONDS, Lifecycle, WindowControls


class Recorder:
    """Stands in for the window and tray, recording what was asked of them."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.preview: list[bool] = []
        self.notes: list[tuple[str, str]] = []
        self.slept: list[float] = []

    def controls(self) -> WindowControls:
        return WindowControls(
            show=lambda: self.calls.append("show"),
            hide=lambda: self.calls.append("hide"),
            destroy=lambda: self.calls.append("destroy"),
            ask_before_closing=lambda: self.calls.append("ask"),
            set_preview=self.preview.append,
            notify=lambda title, message: self.notes.append((title, message)),
        )


def run_now(job: Callable[[], None]) -> None:
    job()


def make(close_action: str = "ask", *, tray: bool = True) -> tuple[Lifecycle, Recorder]:
    recorder = Recorder()
    lifecycle = Lifecycle(
        settings=lambda: Settings(close_action=close_action),
        controls=recorder.controls(),
        can_run_in_background=lambda: tray,
        run_later=run_now,
        sleep=recorder.slept.append,
    )
    return lifecycle, recorder


def test_by_default_closing_asks_and_keeps_the_window() -> None:
    lifecycle, recorder = make("ask")
    assert lifecycle.close_requested() is False
    assert recorder.calls == ["ask"]
    assert not lifecycle.quitting


def test_background_hides_the_window_and_stops_the_preview() -> None:
    lifecycle, recorder = make("background")
    assert lifecycle.close_requested() is False
    assert recorder.calls == ["hide"]
    assert recorder.preview == [False]
    assert lifecycle.hidden


def test_the_first_trip_to_the_background_says_where_palm_lab_went() -> None:
    lifecycle, recorder = make("background")
    lifecycle.close_requested()
    lifecycle.show()
    lifecycle.close_requested()
    assert [title for title, _ in recorder.notes] == [BACKGROUND_TITLE]


def test_quit_lets_the_window_close() -> None:
    lifecycle, recorder = make("quit")
    assert lifecycle.close_requested() is True
    assert lifecycle.quitting
    assert recorder.calls == []


@pytest.mark.parametrize("action", ["ask", "background"])
def test_windows_shutting_down_is_never_held_up(action: str) -> None:
    """Not the person closing it: close, whatever the setting says."""
    lifecycle, recorder = make(action)
    assert lifecycle.close_requested(by_user=False) is True
    assert recorder.calls == []


@pytest.mark.parametrize("action", ["ask", "background"])
def test_without_a_tray_icon_closing_quits(action: str) -> None:
    """A hidden palm-lab with no icon could not be found or quit again."""
    lifecycle, recorder = make(action, tray=False)
    assert lifecycle.close_requested() is True
    assert recorder.calls == []


def test_answering_background_hides() -> None:
    lifecycle, recorder = make("ask")
    lifecycle.close_requested()
    lifecycle.choose("background")
    assert recorder.calls == ["ask", "hide"]


def test_answering_quit_closes_after_the_reply_is_sent() -> None:
    lifecycle, recorder = make("ask")
    lifecycle.choose("quit")
    assert recorder.slept == [QUIT_DELAY_SECONDS]
    assert recorder.calls == ["destroy"]
    # The close that destroy() triggers is then let through.
    assert lifecycle.close_requested() is True


def test_an_unknown_answer_is_refused() -> None:
    lifecycle, _ = make()
    with pytest.raises(ValueError, match="Unknown choice"):
        lifecycle.choose("maybe")


def test_showing_turns_the_preview_back_on() -> None:
    lifecycle, recorder = make("background")
    lifecycle.close_requested()
    lifecycle.show()
    assert recorder.preview == [False, True]
    assert recorder.calls == ["hide", "show"]
    assert not lifecycle.hidden


def test_starting_hidden_is_quiet() -> None:
    """At sign-in there is no notification; closing later still tells nobody twice."""
    lifecycle, recorder = make("background")
    lifecycle.start_hidden()
    assert lifecycle.hidden
    assert recorder.preview == [False]
    lifecycle.show()
    lifecycle.close_requested()
    assert recorder.notes == []


def test_quit_from_the_tray_closes_even_when_the_setting_says_background() -> None:
    lifecycle, recorder = make("background")
    lifecycle.quit()
    assert recorder.calls == ["destroy"]
    assert lifecycle.close_requested() is True
