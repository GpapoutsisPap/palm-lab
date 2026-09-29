"""palm-lab's icon in the notification area, next to the clock.

While palm-lab keeps running with its window closed, this icon is how people
find it again: clicking it opens the window, and its menu can switch tracking
on and off or quit. It is drawn by pystray on a thread of its own.
"""

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOOLTIP = "palm-lab"
TOOLTIP_TRACKING = "palm-lab: watching for gestures"
TOOLTIP_PAUSED = "palm-lab: paused"
PAUSE_CHOICES = ((15, "Pause for 15 minutes"), (60, "Pause for 1 hour"))
REFRESH_SECONDS = 1.0
# A notification sent before the icon has appeared is lost; wait this long for it.
SHOW_WAIT_SECONDS = 3.0


def load_pystray() -> Any:
    import pystray

    return pystray


def load_image(path: Path) -> Any:
    from PIL import Image

    return Image.open(path)


class Tray:
    """The notification-area icon and its menu."""

    def __init__(
        self,
        *,
        icon_file: Path,
        on_open: Callable[[], None],
        on_toggle_tracking: Callable[[], None],
        on_quit: Callable[[], None],
        is_tracking: Callable[[], bool],
        on_pause: Callable[[int], None] = lambda minutes: None,
        on_resume: Callable[[], None] = lambda: None,
        is_paused: Callable[[], bool] = lambda: False,
        backend: Callable[[], Any] = load_pystray,
        image: Callable[[Path], Any] = load_image,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._icon_file = icon_file
        self._on_open = on_open
        self._on_toggle_tracking = on_toggle_tracking
        self._on_quit = on_quit
        self._is_tracking = is_tracking
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._is_paused = is_paused
        self._backend = backend
        self._image = image
        self._sleep = sleep
        self._icon: Any = None
        self._stopped = threading.Event()
        self._shown_state: tuple[bool, bool] | None = None

    def start(self) -> None:
        """Show the icon. Never raises: palm-lab still works without it."""
        try:
            pystray = self._backend()
            menu = pystray.Menu(
                pystray.MenuItem("Open palm-lab", lambda: self._on_open(), default=True),
                pystray.MenuItem(
                    "Tracking",
                    lambda: self._on_toggle_tracking(),
                    checked=lambda _item: self._is_tracking(),
                ),
                *(
                    pystray.MenuItem(
                        text,
                        self._pause_action(minutes),
                        visible=lambda _item: self._is_tracking(),
                    )
                    for minutes, text in PAUSE_CHOICES
                ),
                pystray.MenuItem(
                    "Resume now",
                    lambda: self._on_resume(),
                    visible=lambda _item: self._is_paused(),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit palm-lab", lambda: self._on_quit()),
            )
            self._icon = pystray.Icon(TOOLTIP, self._image(self._icon_file), TOOLTIP, menu)
        except Exception as exc:
            print(f"Could not create the notification-area icon: {exc}")
            self._icon = None
            return
        threading.Thread(target=self._run, name="palm-lab-tray", daemon=True).start()
        threading.Thread(
            target=self._keep_current, name="palm-lab-tray-refresh", daemon=True
        ).start()

    def _pause_action(self, minutes: int) -> Callable[[], None]:
        return lambda: self._on_pause(minutes)

    @property
    def available(self) -> bool:
        return self._icon is not None

    def _run(self) -> None:
        try:
            self._icon.run()
        except Exception as exc:
            print(f"The notification-area icon stopped: {exc}")
            self._icon = None

    def _keep_current(self) -> None:
        """Tracking can change from the window too; keep the tick and tooltip true."""
        while not self._stopped.wait(REFRESH_SECONDS):
            self.refresh()

    def refresh(self) -> None:
        icon = self._icon
        if icon is None:
            return
        state = (self._is_tracking(), self._is_paused())
        if state == self._shown_state:
            return
        self._shown_state = state
        tracking, paused = state
        try:
            icon.title = TOOLTIP_TRACKING if tracking else TOOLTIP_PAUSED if paused else TOOLTIP
            icon.update_menu()
        except Exception as exc:
            print(f"Could not update the notification-area icon: {exc}")

    def notify(self, title: str, message: str) -> None:
        """A Windows notification from the icon, if there is one."""
        icon = self._icon
        if icon is None:
            return
        waited = 0.0
        while not getattr(icon, "visible", True) and waited < SHOW_WAIT_SECONDS:
            self._sleep(0.1)
            waited += 0.1
        try:
            icon.notify(message, title)
        except Exception as exc:
            print(f"Could not show a notification: {exc}")

    def stop(self) -> None:
        self._stopped.set()
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception as exc:
                print(f"Could not remove the notification-area icon: {exc}")
