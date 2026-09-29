"""Tests for keeping one palm-lab running at a time."""

import sys
import threading

import pytest

from palm_lab.single_instance import NoInstanceGuard, WindowsInstance, instance_guard


def test_off_windows_every_launch_runs() -> None:
    guard = NoInstanceGuard()
    assert guard.acquire() is True
    guard.wake_existing()
    guard.listen(lambda: None)
    guard.release()


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows fallback")
def test_the_fallback_is_chosen_off_windows() -> None:
    assert isinstance(instance_guard(), NoInstanceGuard)


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows fallback")
def test_the_windows_guard_refuses_to_run_elsewhere() -> None:
    with pytest.raises(OSError, match="only works on Windows"):
        WindowsInstance()


@pytest.mark.skipif(sys.platform != "win32", reason="uses real Windows kernel objects")
def test_a_second_copy_is_turned_away_and_wakes_the_first() -> None:
    names = {"mutex_name": "palm-lab-test-mutex", "event_name": "palm-lab-test-event"}
    first, second = WindowsInstance(**names), WindowsInstance(**names)
    try:
        assert first.acquire() is True
        woken = threading.Event()
        first.listen(woken.set)

        assert second.acquire() is False
        second.wake_existing()
        assert woken.wait(2)
    finally:
        second.release()
        first.release()


@pytest.mark.skipif(sys.platform != "win32", reason="uses real Windows kernel objects")
def test_after_the_first_copy_quits_a_new_one_can_run() -> None:
    names = {"mutex_name": "palm-lab-test-mutex-2", "event_name": "palm-lab-test-event-2"}
    first = WindowsInstance(**names)
    assert first.acquire() is True
    first.release()
    again = WindowsInstance(**names)
    try:
        assert again.acquire() is True
    finally:
        again.release()
