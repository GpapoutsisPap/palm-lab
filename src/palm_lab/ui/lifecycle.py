"""What closing, hiding, showing and quitting the window do.

Closing the window no longer has to mean quitting: depending on the
close_action setting, palm-lab asks, hides into the notification area and
keeps watching for gestures, or quits. This class makes that decision and
carries it out through callbacks, so it can be tested without a real window.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from palm_lab.settings import Settings

BACKGROUND_TITLE = "palm-lab is still running"
BACKGROUND_MESSAGE = (
    "Your gestures keep working. Click the palm-lab icon by the clock to open it, "
    "or right-click it to quit."
)
# Lets the page's call that chose "Quit" finish before the window goes away.
QUIT_DELAY_SECONDS = 0.2


def run_in_thread(job: Callable[[], None]) -> None:
    threading.Thread(target=job, daemon=True).start()


@dataclass
class WindowControls:
    """The things Lifecycle can do to the window and the rest of the app."""

    show: Callable[[], None]
    hide: Callable[[], None]
    destroy: Callable[[], None]
    ask_before_closing: Callable[[], None]
    set_preview: Callable[[bool], None]
    notify: Callable[[str, str], None]


class Lifecycle:
    """Decides what closing the window does, and does it."""

    def __init__(
        self,
        *,
        settings: Callable[[], Settings],
        controls: WindowControls,
        can_run_in_background: Callable[[], bool],
        run_later: Callable[[Callable[[], None]], None] = run_in_thread,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._controls = controls
        self._can_run_in_background = can_run_in_background
        self._run_later = run_later
        self._sleep = sleep
        self.quitting = False
        self.hidden = False
        self._told_about_background = False

    def close_requested(self, by_user: bool = True) -> bool:
        """The window is about to close. True lets it close; False keeps it.

        Only a person closing the window (the X, Alt+F4, the taskbar) is
        asked or sent to the background. When Windows shuts down, or an
        installer closes palm-lab to update it, it closes, so it can never
        hold up a shutdown.
        """
        if self.quitting or not by_user:
            self.quitting = True
            return True
        action = self._settings().close_action
        if not self._can_run_in_background():
            # Without the notification-area icon a hidden palm-lab could not
            # be found again or quit, so closing always quits.
            action = "quit"
        if action == "quit":
            self.quitting = True
            return True
        if action == "background":
            self._run_later(self.to_background)
        else:
            self._run_later(self._controls.ask_before_closing)
        return False

    def choose(self, choice: str) -> None:
        """The answer to the close question: "background" or "quit"."""
        if choice == "background":
            self._run_later(self.to_background)
        elif choice == "quit":
            self._run_later(self._quit_after_reply)
        else:
            raise ValueError(f"Unknown choice {choice!r}")

    def to_background(self) -> None:
        self.hidden = True
        self._controls.hide()
        # Nobody is looking, so stop making preview pictures.
        self._controls.set_preview(False)
        if not self._told_about_background:
            self._told_about_background = True
            self._controls.notify(BACKGROUND_TITLE, BACKGROUND_MESSAGE)

    def show(self) -> None:
        self.hidden = False
        self._controls.set_preview(True)
        self._controls.show()

    def start_hidden(self) -> None:
        """Started at sign-in: stay in the notification area, quietly."""
        self.hidden = True
        self._told_about_background = True
        self._controls.set_preview(False)

    def quit(self) -> None:
        self.quitting = True
        self._controls.destroy()

    def _quit_after_reply(self) -> None:
        self._sleep(QUIT_DELAY_SECONDS)
        self.quit()
