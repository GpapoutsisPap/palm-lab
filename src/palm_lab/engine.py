"""Run gesture tracking on a background thread, for the palm-lab window.

The engine owns the camera loop: read a frame, find hands, classify the
gesture, decide whether it fires, and run the matching binding. It never
imports OpenCV or MediaPipe itself. The camera, the hand detector and the
preview renderer are passed in, which keeps the engine testable with fakes.
"""

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Protocol

from palm_lab.actions.models import Binding
from palm_lab.actions.runner import ActionResult, run_binding
from palm_lab.capture import CaptureStatus, GestureCapture
from palm_lab.combos import combo_key, combo_parts
from palm_lab.custom_gestures import CustomGesture, all_rules
from palm_lab.features import (
    STANDARD_PROFILE,
    HandFeatures,
    HandMeasurement,
    HandProfile,
    extract,
    measure,
)
from palm_lab.gestures import FingerTuple, classify
from palm_lab.landmarks import Point, normalise
from palm_lab.settings import Settings
from palm_lab.state import GestureTrigger, TriggerState

Hands = list[list[Point]]

# MediaPipe sometimes loses one of two hands for a frame or two. For this long
# after seeing a two-hand gesture, one of its halves on its own still counts
# as the pair, so the hold isn't restarted by a flicker.
COMBO_GRACE_SECONDS = 0.3

# Measuring a hand for tuning: frames skipped while the hand settles into the
# pose, then frames kept. At a typical 25 fps that is about a quarter of a
# second, then a second.
MEASURE_SETTLE_FRAMES = 6
MEASURE_FRAMES = 24


class FrameSource(Protocol):
    """A camera, or anything else that produces frames."""

    def read(self) -> tuple[bool, object]: ...

    def release(self) -> None: ...


class HandDetector(Protocol):
    """Finds hands in a frame, as lists of 21 landmarks each."""

    def detect(self, frame: object) -> Hands: ...

    def close(self) -> None: ...


PreviewRenderer = Callable[[object, Hands], bytes | None]
Dispatcher = Callable[[Callable[[], None]], None]
BindingRunner = Callable[[Binding], list[ActionResult]]


def run_in_background(job: Callable[[], None]) -> None:
    """Run a binding without blocking the camera loop during step delays."""
    threading.Thread(target=job, daemon=True).start()


def classify_hand(
    points: list[Point],
    rules: Mapping[FingerTuple, str] | None = None,
    profile: HandProfile = STANDARD_PROFILE,
) -> str | None:
    """Gesture name for one hand, or None if unrecognised or degenerate."""
    try:
        return classify(extract(normalise(points), profile), rules)
    except ValueError:
        return None


def classify_hands(
    hands: Hands,
    rules: Mapping[FingerTuple, str] | None = None,
    profile: HandProfile = STANDARD_PROFILE,
) -> str | None:
    """The gesture for everything in view.

    One hand gives its own gesture. Two hands give the two-hand key for both
    shapes together, and only that: a one-hand gesture never runs while the
    other hand is also in view. If either hand's shape isn't recognised, or
    more than two hands are found, there is no gesture.
    """
    if len(hands) == 1:
        return classify_hand(hands[0], rules, profile)
    if len(hands) == 2:
        first, second = (classify_hand(hand, rules, profile) for hand in hands)
        if first is None or second is None:
            return None
        return combo_key(first, second)
    return None


def hand_features(
    points: list[Point], profile: HandProfile = STANDARD_PROFILE
) -> HandFeatures | None:
    """The raw five-finger reading for one hand, or None if degenerate."""
    try:
        return extract(normalise(points), profile)
    except ValueError:
        return None


@dataclass(frozen=True)
class MeasureStatus:
    """How far measuring a hand pose has got, for the setup guide."""

    progress: float  # 0..1
    hands: int  # hands in view on the latest frame: measuring needs exactly one
    done: bool


@dataclass
class _Measuring:
    """Collects one hand's measurements, frame by frame, for tuning."""

    settled: int = 0
    samples: list[HandMeasurement] = field(default_factory=list)
    hands: int = 0

    @property
    def done(self) -> bool:
        return len(self.samples) >= MEASURE_FRAMES

    def update(self, hands: Hands) -> None:
        self.hands = len(hands)
        if self.done:
            return
        if len(hands) != 1:
            self.settled = 0  # the hand left: let it settle again when it's back
            return
        try:
            reading = measure(normalise(hands[0]))
        except ValueError:
            return
        if self.settled < MEASURE_SETTLE_FRAMES:
            self.settled += 1
            return
        self.samples.append(reading)


@dataclass(frozen=True)
class FiredEvent:
    """A gesture that fired, and what its binding did."""

    gesture: str
    binding_name: str | None
    at: float
    results: tuple[ActionResult, ...] = ()
    finished: bool = False


@dataclass(frozen=True)
class EngineStatus:
    """A snapshot of the engine, safe to read from any thread."""

    running: bool
    gesture: str | None
    hands: int
    fps: float
    error: str | None
    last_fired: FiredEvent | None
    trigger: TriggerState = TriggerState()


@dataclass(frozen=True)
class PreviewFrame:
    """The latest camera picture and the hands found in that same frame."""

    image: bytes
    hands: Hands


class TrackingEngine:
    """Owns the camera loop and everything it drives."""

    def __init__(
        self,
        *,
        open_camera: Callable[[int], FrameSource],
        make_detector: Callable[[], HandDetector],
        render_preview: PreviewRenderer,
        bindings: Iterable[Binding] = (),
        settings: Settings | None = None,
        hand_profile: HandProfile | None = None,
        custom_gestures: Iterable[CustomGesture] = (),
        dispatch: Dispatcher = run_in_background,
        run: BindingRunner = run_binding,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._open_camera = open_camera
        self._make_detector = make_detector
        self._render_preview = render_preview
        self._dispatch = dispatch
        self._run = run
        self._clock = clock
        self._wall_clock = wall_clock

        self._lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None

        self._settings = settings or Settings()
        self._bindings = {b.gesture: b for b in bindings}
        self._trigger = self._new_trigger(self._settings)
        self._rules = all_rules(list(custom_gestures))
        self._profile = hand_profile or STANDARD_PROFILE
        # The setup guide's hand checks: gestures are read but nothing runs.
        self._quiet = False
        self._measuring: _Measuring | None = None

        self._gesture: str | None = None
        self._combo_seen: tuple[str, float] | None = None  # key, when last seen
        self._hands = 0
        self._fps = 0.0
        self._last_frame_at: float | None = None
        self._preview: bytes | None = None
        self._preview_hands: Hands = []
        self._error: str | None = None
        self._last_fired: FiredEvent | None = None
        self._capture: GestureCapture | None = None
        self._capture_status: CaptureStatus | None = None
        self._preview_enabled = True

    @staticmethod
    def _new_trigger(settings: Settings) -> GestureTrigger:
        return GestureTrigger(
            dwell_seconds=settings.dwell_seconds,
            cooldown_seconds=settings.cooldown_seconds,
        )

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        """Open the camera and start tracking. Raises if the camera won't open."""
        if self.running:
            return
        with self._lock:
            camera_index = self._settings.camera_index
        source = self._open_camera(camera_index)
        try:
            detector = self._make_detector()
        except BaseException:
            source.release()
            raise

        with self._lock:
            self._error = None
            self._trigger = self._new_trigger(self._settings)
            self._last_frame_at = None
            self._fps = 0.0
        self._stop_requested.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(source, detector), name="palm-lab-tracking", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Ask the loop to finish and wait for it to release the camera."""
        self._stop_requested.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None

    def _loop(self, source: FrameSource, detector: HandDetector) -> None:
        try:
            while not self._stop_requested.is_set():
                ok, frame = source.read()
                if not ok:
                    with self._lock:
                        self._error = "The camera stopped sending frames."
                    break
                self.process_frame(frame, detector)
        except Exception as exc:
            with self._lock:
                self._error = f"Tracking stopped: {exc}"
        finally:
            source.release()
            detector.close()
            with self._lock:
                self._gesture = None
                self._hands = 0
                self._fps = 0.0
                self._preview = None
                self._preview_hands = []
                self._capture = None
                self._capture_status = None
                self._measuring = None

    def process_frame(self, frame: object, detector: HandDetector) -> None:
        """Handle one frame. Public so tests can drive it without a thread."""
        hands = detector.detect(frame)
        with self._lock:
            rules = self._rules
            profile = self._profile
            preview_enabled = self._preview_enabled
        reading = classify_hands(hands, rules, profile)
        # Encoding a picture every frame is wasted work while the window is hidden.
        preview = self._render_preview(frame, hands) if preview_enabled else None
        now = self._clock()

        with self._lock:
            if self._last_frame_at is not None and now > self._last_frame_at:
                instant = 1.0 / (now - self._last_frame_at)
                self._fps = instant if self._fps == 0 else 0.9 * self._fps + 0.1 * instant
            self._last_frame_at = now
            gesture = self._bridge_combo_flicker(reading, len(hands), now)
            self._gesture = gesture
            self._hands = len(hands)
            self._preview = preview
            self._preview_hands = hands

            # Once a capture completes, keep showing that result until the
            # API consumes it (saves or cancels it), rather than letting the
            # next frame silently overwrite it.
            capture = self._capture
            finished = self._capture_status is not None and self._capture_status.stage in (
                "done",
                "taken",
            )
            if capture is not None and not finished:
                features = hand_features(hands[0], profile) if hands else None
                status = capture.update(features, now)
                # As soon as the first hold records a shape, say if it's one
                # that already belongs to a gesture, rather than asking for a
                # second hold and a name only to refuse it on save.
                if status.first is not None and status.first in rules:
                    status = replace(
                        status,
                        stage="taken",
                        progress=0.0,
                        fingers=status.first,
                        matches=rules[status.first],
                    )
                self._capture_status = status

            if self._measuring is not None:
                self._measuring.update(hands)

            # Recording a new gesture, measuring a hand or checking gestures
            # in the setup guide: don't also run whatever the shape being
            # held happens to already be bound to.
            if capture is not None or self._measuring is not None or self._quiet:
                return

            # A gesture switched off in the window counts as no gesture at
            # all: it doesn't run, and doesn't start a cooldown either, so
            # switching it back on works straight away.
            if self._switched_off(gesture):
                gesture = None
            fired = self._trigger.update(gesture, now)
            if fired is None:
                return
            binding = self._bindings.get(fired)
            event = FiredEvent(
                gesture=fired,
                binding_name=binding.name if binding else None,
                at=self._wall_clock(),
                finished=binding is None,
            )
            self._last_fired = event

        if binding is not None:
            self._dispatch(lambda: self._run_and_record(binding, event))

    def _run_and_record(self, binding: Binding, event: FiredEvent) -> None:
        results = tuple(self._run(binding))
        with self._lock:
            # A newer gesture may have fired meanwhile; don't overwrite it.
            if self._last_fired is event:
                self._last_fired = replace(event, results=results, finished=True)

    def set_preview_enabled(self, enabled: bool) -> None:
        """Turn preview pictures off while no window is showing them."""
        with self._lock:
            self._preview_enabled = enabled
            if not enabled:
                self._preview = None
                self._preview_hands = []

    def _bridge_combo_flicker(self, reading: str | None, hands: int, now: float) -> str | None:
        """Keep a two-hand gesture going through a brief loss of one hand."""
        if reading is not None and combo_parts(reading) is not None:
            self._combo_seen = (reading, now)
            return reading
        if self._combo_seen is not None and hands == 1:
            key, seen_at = self._combo_seen
            parts = combo_parts(key)
            if parts and reading in parts and now - seen_at <= COMBO_GRACE_SECONDS:
                return key
        self._combo_seen = None
        return reading

    def _switched_off(self, gesture: str | None) -> bool:
        """True for a gesture whose binding exists but is turned off."""
        binding = self._bindings.get(gesture) if gesture is not None else None
        return binding is not None and not binding.enabled

    def update_bindings(self, bindings: Iterable[Binding]) -> None:
        with self._lock:
            self._bindings = {b.gesture: b for b in bindings}

    def update_custom_gestures(self, gestures: Iterable[CustomGesture]) -> None:
        """Recognise a new set of custom gestures from the next frame on."""
        with self._lock:
            self._rules = all_rules(list(gestures))

    def update_settings(self, settings: Settings) -> None:
        """Apply new settings. A camera change restarts tracking if running."""
        with self._lock:
            camera_changed = settings.camera_index != self._settings.camera_index
            self._settings = settings
            self._trigger = self._new_trigger(settings)
        if camera_changed and self.running:
            self.stop()
            self.start()

    def status(self) -> EngineStatus:
        with self._lock:
            running = self.running
            capturing = self._capture is not None or self._measuring is not None or self._quiet
            # While recording a new gesture nothing fires, so there is no hold to show.
            if not running or capturing:
                trigger = TriggerState()
            elif self._switched_off(self._gesture):
                trigger = TriggerState(phase="off", gesture=self._gesture)
            else:
                trigger = self._trigger.state(self._clock())
            return EngineStatus(
                running=running,
                gesture=self._gesture,
                hands=self._hands,
                fps=self._fps,
                error=self._error,
                last_fired=self._last_fired,
                trigger=trigger,
            )

    def preview(self) -> bytes | None:
        with self._lock:
            return self._preview

    def snapshot(self) -> PreviewFrame | None:
        """The latest picture together with its hands, read in one go."""
        with self._lock:
            if self._preview is None:
                return None
            return PreviewFrame(self._preview, list(self._preview_hands))

    # Gesture capture ---------------------------------------------------------

    def start_gesture_capture(self) -> None:
        """Begin (or restart) recording a new gesture from the next frame on."""
        with self._lock:
            self._capture = GestureCapture(hold_seconds=self._settings.dwell_seconds)
            self._capture_status = None
            # Otherwise a dwell that was already in progress when capture
            # started would look instantly complete the moment it ends.
            self._trigger.reset()

    # Tuning to a hand (the setup guide) -------------------------------------

    def update_hand_profile(self, profile: HandProfile | None) -> None:
        """Read hands with these cut-offs from the next frame on (None: standard)."""
        with self._lock:
            self._profile = profile or STANDARD_PROFILE

    def set_quiet(self, quiet: bool) -> None:
        """While quiet, gestures are recognised and reported but never run."""
        with self._lock:
            self._quiet = quiet
            self._trigger.reset()

    def start_measuring(self) -> None:
        """Start (or restart) collecting measurements of one held hand pose."""
        with self._lock:
            self._measuring = _Measuring()
            self._trigger.reset()

    def measure_status(self) -> MeasureStatus | None:
        with self._lock:
            measuring = self._measuring
            if measuring is None:
                return None
            return MeasureStatus(
                progress=min(len(measuring.samples) / MEASURE_FRAMES, 1.0),
                hands=measuring.hands,
                done=measuring.done,
            )

    def take_measurements(self) -> list[HandMeasurement]:
        """End measuring and hand over what was collected."""
        with self._lock:
            measuring, self._measuring = self._measuring, None
        return list(measuring.samples) if measuring else []

    def cancel_gesture_capture(self) -> None:
        with self._lock:
            self._capture = None
            self._capture_status = None

    def capture_status(self) -> CaptureStatus | None:
        """What the "Add gesture" wizard should show, or None if not capturing."""
        with self._lock:
            return self._capture_status
