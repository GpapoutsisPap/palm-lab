"""Turn a stream of per-frame gesture readings into deliberate trigger events."""

from dataclasses import dataclass, field

DEFAULT_DWELL_SECONDS = 0.8
DEFAULT_COOLDOWN_SECONDS = 5.0


@dataclass(frozen=True)
class TriggerState:
    """Where the current hold is, for showing it in the window.

    phase is "idle" (nothing recognised), "holding" (counting towards
    firing), "fired" (this hold ran its gesture), "cooldown" (the gesture ran
    recently, so holding it now will not run it again yet), or "rearm" (this
    hold is used up; lower the hand and show the gesture again).
    """

    phase: str = "idle"
    gesture: str | None = None
    progress: float = 0.0  # 0..1 through the hold
    cooldown_remaining: float = 0.0  # seconds until this gesture can run again


@dataclass
class GestureTrigger:
    """Decides when a held gesture should fire an action.

    Feed it one reading per frame via `update()`. It returns a gesture name
    on the single frame where that gesture has been held long enough and is
    not on cooldown, and None on every other frame.
    """

    dwell_seconds: float = DEFAULT_DWELL_SECONDS
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS

    _current: str | None = field(default=None, init=False)
    _held_since: float | None = field(default=None, init=False)
    _spent: bool = field(default=False, init=False)
    _fired: bool = field(default=False, init=False)
    _last_fired: dict[str, float] = field(default_factory=dict, init=False)

    def update(self, gesture: str | None, now: float) -> str | None:
        """Record one frame's reading and return a gesture if it should fire."""
        # Nothing recognised: any dwell in progress is abandoned.
        if gesture is None:
            self.reset()
            return None

        # A different gesture than last frame: start a fresh dwell.
        if gesture != self._current:
            self._current = gesture
            self._held_since = now
            self._spent = False
            self._fired = False
            return None

        # This hold has already been resolved, or was never started.
        if self._spent or self._held_since is None:
            return None

        # Still counting.
        if now - self._held_since < self.dwell_seconds:
            return None

        # The dwell is complete either way: this hold is now resolved.
        self._spent = True

        last_fired = self._last_fired.get(gesture)
        if last_fired is not None and now - last_fired < self.cooldown_seconds:
            return None

        self._last_fired[gesture] = now
        self._fired = True
        return gesture

    def reset(self) -> None:
        """Forget the in-progress dwell without clearing cooldowns."""
        self._current = None
        self._held_since = None
        self._spent = False
        self._fired = False

    def state(self, now: float) -> TriggerState:
        """What the hold in progress looks like at `now`. Changes nothing."""
        gesture = self._current
        if gesture is None or self._held_since is None:
            return TriggerState()
        last = self._last_fired.get(gesture)
        remaining = 0.0 if last is None else max(0.0, self.cooldown_seconds - (now - last))
        if self._fired:
            return TriggerState("fired", gesture, 1.0, remaining)
        if remaining > 0:
            return TriggerState("cooldown", gesture, 0.0, remaining)
        if self._spent:
            # Held through a cooldown that has now run out: this hold is used up.
            return TriggerState("rearm", gesture, 0.0, 0.0)
        held = now - self._held_since
        progress = 1.0 if self.dwell_seconds <= 0 else min(held / self.dwell_seconds, 1.0)
        return TriggerState("holding", gesture, progress, 0.0)
