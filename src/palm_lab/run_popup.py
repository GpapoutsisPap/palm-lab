"""Decide what the pop-up by the clock says when a gesture runs, and when to stay quiet.

With palm-lab's window closed there's no other sign a gesture worked, so a
small card appears near the clock: "Ran Morning setup", or what failed. It
never takes focus and lets clicks through (see palm_lab.overlay, which draws
it). This module holds the decisions, so they can be tested anywhere:

- Every gesture run gets a card, not a Windows notification. Notifications
  pile up in Notification Center, and Microsoft's guidance warns that too
  many make people switch an app's notifications off.
- Nothing shows while palm-lab's own window is in front: the window already
  says what ran.
- Nothing shows while Windows says the user is busy (a full-screen game, a
  presentation, Do Not Disturb). A failure then goes to Windows'
  notifications instead, which Windows holds back until the user is free.
- A repeat of the card still showing updates it ("x2") instead of stacking.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from palm_lab.combos import combo_parts
from palm_lab.engine import FiredEvent

# Long enough to read a short line; a failure stays longer, to be read twice.
SUCCESS_SECONDS = 2.5
FAILURE_SECONDS = 7.0
MAX_DETAIL_CHARS = 90

BUILTIN_LABELS = {
    "peace": "Peace sign",
    "fist": "Fist",
    "open_palm": "Open palm",
    "thumbs_up": "Thumbs up",
}


def gesture_label(gesture: str) -> str:
    """The name the window shows for a gesture: "Peace sign", "Fist + Peace sign"."""
    parts = combo_parts(gesture)
    if parts is not None:
        return " + ".join(gesture_label(part) for part in parts)
    return BUILTIN_LABELS.get(gesture, gesture)


@dataclass(frozen=True)
class PopupMessage:
    """One card: a title line, a detail line, and whether something failed."""

    title: str
    detail: str
    failed: bool
    seconds: float
    count: int = 1  # how many times in a row this same card has been shown

    @property
    def detail_line(self) -> str:
        return f"{self.detail}  ×{self.count}" if self.count > 1 else self.detail


def _shorten(text: str, limit: int = MAX_DETAIL_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def message_for(event: FiredEvent) -> PopupMessage:
    """What the card says about one finished run."""
    name = event.binding_name or gesture_label(event.gesture)
    errors = [r.error.user_message() for r in event.results if r.error is not None]
    total = len(event.results)
    if errors and len(errors) < total:
        # The runner carries on past a failed step, so a run can half-work: say so.
        return PopupMessage(
            title=f"{name} ran, {len(errors)} of {total} steps failed",
            detail=_shorten(errors[0]),
            failed=True,
            seconds=FAILURE_SECONDS,
        )
    if errors:
        return PopupMessage(
            title=f"{name} didn’t work",
            detail=_shorten(errors[0]),
            failed=True,
            seconds=FAILURE_SECONDS,
        )
    return PopupMessage(
        title=f"Ran {name}",
        detail=gesture_label(event.gesture),
        failed=False,
        seconds=SUCCESS_SECONDS,
    )


class RunPopup:
    """Listens for finished gesture runs and shows, or skips, the card."""

    def __init__(
        self,
        *,
        show: Callable[[PopupMessage], None],
        mode: Callable[[], str],
        window_in_front: Callable[[], bool],
        user_busy: Callable[[], bool],
        notify: Callable[[str, str], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._show = show
        self._mode = mode
        self._window_in_front = window_in_front
        self._user_busy = user_busy
        self._notify = notify
        self._clock = clock
        self._showing: PopupMessage | None = None
        self._showing_until = 0.0

    def on_run(self, event: FiredEvent) -> None:
        """Called by the engine each time a gesture's shortcut finishes."""
        mode = self._mode()
        if mode == "off" or event.manual or not event.finished or event.binding_name is None:
            return
        if mode == "failures" and not event.failed:
            return
        if self._window_in_front():
            return
        message = message_for(event)
        if self._user_busy():
            if message.failed:
                self._notify(message.title, message.detail)
            return
        now = self._clock()
        current = self._showing
        if current is not None and now < self._showing_until and _same_card(current, message):
            message = replace(message, count=current.count + 1)
        self._showing = message
        self._showing_until = now + message.seconds
        self._show(message)


def _same_card(a: PopupMessage, b: PopupMessage) -> bool:
    return (a.title, a.detail, a.failed) == (b.title, b.detail, b.failed)
