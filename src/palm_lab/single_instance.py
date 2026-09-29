"""Keep one palm-lab running at a time, and let a second launch wake the first.

Once palm-lab can keep running in the notification area, opening it again
from the Start menu would otherwise start a second copy fighting over the
camera. Instead, the first copy holds a named Windows mutex; a later launch
sees it, signals a named event, and exits, and the first copy shows its window.

Off Windows every launch counts as the first, so running from source on
another system behaves as before.
"""

import sys
import threading
from collections.abc import Callable
from typing import Any, Protocol

# Also the installer's AppMutex, so setup can tell palm-lab is running.
MUTEX_NAME = "GpapoutsisPap.palm-lab"
EVENT_NAME = "GpapoutsisPap.palm-lab.show"

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0


class Instance(Protocol):
    """What the app needs from a single-instance guard."""

    def acquire(self) -> bool:
        """Claim being the running copy. False if another copy already is."""
        ...

    def wake_existing(self) -> None:
        """Ask the running copy to show its window."""
        ...

    def listen(self, on_wake: Callable[[], None]) -> None:
        """Call on_wake (on a background thread) each time a later launch asks."""
        ...

    def release(self) -> None: ...


class NoInstanceGuard:
    """Used off Windows: every launch runs, nothing is shared."""

    def acquire(self) -> bool:
        return True

    def wake_existing(self) -> None:
        pass

    def listen(self, on_wake: Callable[[], None]) -> None:
        pass

    def release(self) -> None:
        pass


class WindowsInstance:
    """A named mutex marks the running copy; a named event wakes it."""

    _kernel32: Any
    _get_last_error: Callable[[], int]
    _mutex_name: str
    _event_name: str
    _mutex: int | None
    _event: int | None

    def __init__(self, mutex_name: str = MUTEX_NAME, event_name: str = EVENT_NAME) -> None:
        if sys.platform != "win32":
            raise OSError("WindowsInstance only works on Windows")
        import ctypes
        from ctypes import wintypes

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._get_last_error = ctypes.get_last_error
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.CreateEventW.restype = wintypes.HANDLE
        self._kernel32.OpenEventW.restype = wintypes.HANDLE
        self._mutex_name = mutex_name
        self._event_name = event_name
        self._mutex: int | None = None
        self._event: int | None = None

    def acquire(self) -> bool:
        self._mutex = self._kernel32.CreateMutexW(None, False, self._mutex_name)
        if self._get_last_error() == ERROR_ALREADY_EXISTS:
            return False
        # Auto-reset: each SetEvent wakes the listener exactly once.
        self._event = self._kernel32.CreateEventW(None, False, False, self._event_name)
        return True

    def wake_existing(self) -> None:
        event = self._kernel32.OpenEventW(EVENT_MODIFY_STATE, False, self._event_name)
        if event:
            self._kernel32.SetEvent(event)
            self._kernel32.CloseHandle(event)

    def listen(self, on_wake: Callable[[], None]) -> None:
        event = self._event
        if not event:
            return

        def wait() -> None:
            while self._kernel32.WaitForSingleObject(event, INFINITE) == WAIT_OBJECT_0:
                on_wake()

        threading.Thread(target=wait, name="palm-lab-wake", daemon=True).start()

    def release(self) -> None:
        for handle in (self._event, self._mutex):
            if handle:
                self._kernel32.CloseHandle(handle)
        self._event = self._mutex = None


def instance_guard() -> Instance:
    return WindowsInstance() if sys.platform == "win32" else NoInstanceGuard()
