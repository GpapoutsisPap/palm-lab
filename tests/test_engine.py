"""Tests for the background tracking engine, driven by recorded landmarks."""

import threading
import time
from collections.abc import Callable

import pytest
from conftest import raw_hand, three_fingers_up

from palm_lab.actions.models import Action, ActionType, Binding
from palm_lab.actions.runner import ActionResult
from palm_lab.custom_gestures import CustomGesture
from palm_lab.engine import FrameSource, HandDetector, Hands, TrackingEngine, classify_hand
from palm_lab.landmarks import Point
from palm_lab.settings import Settings

PEACE = raw_hand("peace")
FIST = raw_hand("fist")
THREE_UP = three_fingers_up()  # a shape no built-in gesture uses
PAUSE = Binding(
    gesture="peace",
    name="Pause music",
    actions=(Action(type=ActionType.HOTKEY, target="media_play_pause"),),
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class ScriptedDetector:
    """Returns whatever hands the test puts in `hands`."""

    def __init__(self, hands: Hands | None = None) -> None:
        self.hands: Hands = hands or []
        self.closed = False

    def detect(self, frame: object) -> Hands:
        return self.hands

    def close(self) -> None:
        self.closed = True


class LoopingSource:
    """A camera that delivers frames until told otherwise."""

    def __init__(self, frames: int | None = None) -> None:
        self.remaining = frames
        self.released = False
        self.reads = 0

    def read(self) -> tuple[bool, object]:
        time.sleep(0.001)
        if self.remaining is not None:
            if self.remaining == 0:
                return False, None
            self.remaining -= 1
        self.reads += 1
        return True, object()

    def release(self) -> None:
        self.released = True


def make_engine(
    *,
    bindings: tuple[Binding, ...] = (PAUSE,),
    settings: Settings | None = None,
    custom_gestures: tuple[CustomGesture, ...] = (),
    source: FrameSource | None = None,
    detector: HandDetector | None = None,
    open_camera: Callable[[int], FrameSource] | None = None,
    clock: FakeClock | None = None,
    jobs: list[Callable[[], None]] | None = None,
    ran: list[Binding] | None = None,
) -> TrackingEngine:
    def run(binding: Binding) -> list[ActionResult]:
        if ran is not None:
            ran.append(binding)
        return [ActionResult(action=a) for a in binding.actions]

    return TrackingEngine(
        open_camera=open_camera or (lambda index: source or LoopingSource()),
        make_detector=lambda: detector or ScriptedDetector(),
        render_preview=lambda frame, hands: b"jpeg:%d" % len(hands),
        bindings=bindings,
        settings=settings or Settings(dwell_seconds=0.5, cooldown_seconds=5.0),
        custom_gestures=custom_gestures,
        dispatch=(jobs.append if jobs is not None else (lambda job: job())),
        run=run,
        clock=clock or FakeClock(),
        wall_clock=lambda: 1_700_000_000.0,
    )


def wait_for(condition: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met in time")
        time.sleep(0.01)


# Classification ------------------------------------------------------------


def test_classify_hand_recognises_recorded_gestures() -> None:
    assert classify_hand(PEACE) == "peace"
    assert classify_hand(FIST) == "fist"


def test_a_degenerate_hand_is_ignored_rather_than_crashing() -> None:
    """21 identical points cannot be normalised; treat it as no gesture."""
    assert classify_hand([Point(0.5, 0.5, 0.0)] * 21) is None


# One frame at a time ---------------------------------------------------------


def test_processing_a_frame_updates_status_and_preview() -> None:
    engine = make_engine()
    engine.process_frame(object(), ScriptedDetector([PEACE]))
    status = engine.status()
    assert status.gesture == "peace"
    assert status.hands == 1
    assert engine.preview() == b"jpeg:1"


def test_no_hands_means_no_gesture() -> None:
    engine = make_engine()
    engine.process_frame(object(), ScriptedDetector([]))
    assert engine.status().gesture is None
    assert engine.status().hands == 0


def test_holding_a_gesture_fires_its_binding_once() -> None:
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran)
    detector = ScriptedDetector([PEACE])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == [PAUSE]
    fired = engine.status().last_fired
    assert fired is not None
    assert fired.gesture == "peace"
    assert fired.binding_name == "Pause music"
    assert fired.finished
    assert [r.ok for r in fired.results] == [True]


def test_an_unbound_gesture_is_reported_but_runs_nothing() -> None:
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran)
    detector = ScriptedDetector([FIST])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    fired = engine.status().last_fired
    assert fired is not None
    assert fired.gesture == "fist"
    assert fired.binding_name is None
    assert fired.finished
    assert ran == []


def test_bindings_run_off_the_camera_loop() -> None:
    """The binding is handed to the dispatcher, not run inline."""
    clock = FakeClock()
    jobs: list[Callable[[], None]] = []
    engine = make_engine(clock=clock, jobs=jobs)
    detector = ScriptedDetector([PEACE])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    fired = engine.status().last_fired
    assert fired is not None and not fired.finished
    assert len(jobs) == 1
    jobs[0]()
    fired = engine.status().last_fired
    assert fired is not None and fired.finished


def test_a_slow_binding_does_not_overwrite_a_newer_event() -> None:
    clock = FakeClock()
    jobs: list[Callable[[], None]] = []
    fist = Binding(gesture="fist", name="Fist", actions=PAUSE.actions)
    engine = make_engine(clock=clock, jobs=jobs, bindings=(PAUSE, fist))
    for hand in (PEACE, FIST):
        detector = ScriptedDetector([hand])
        for _ in range(10):
            clock.now += 0.1
            engine.process_frame(object(), detector)
    assert len(jobs) == 2
    jobs[0]()  # the older peace job finishes late
    fired = engine.status().last_fired
    assert fired is not None and fired.gesture == "fist"


def test_frame_rate_is_measured() -> None:
    clock = FakeClock()
    engine = make_engine(clock=clock)
    detector = ScriptedDetector([])
    for step in range(30):
        clock.now = 100.0 + step * 0.05
        engine.process_frame(object(), detector)
    assert engine.status().fps == pytest.approx(20.0, rel=0.01)


def test_new_settings_change_the_timing() -> None:
    """A longer dwell means the same hold no longer fires."""
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran)
    engine.update_settings(Settings(dwell_seconds=5.0))
    detector = ScriptedDetector([PEACE])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == []


def test_new_bindings_apply_immediately() -> None:
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran, bindings=())
    engine.update_bindings([PAUSE])
    detector = ScriptedDetector([PEACE])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == [PAUSE]


# The background thread -----------------------------------------------------------


def test_start_and_stop_release_the_camera_and_detector() -> None:
    source = LoopingSource()
    detector = ScriptedDetector([PEACE])
    engine = make_engine(source=source, detector=detector)
    engine.start()
    wait_for(lambda: source.reads > 3)
    assert engine.status().running
    engine.stop()
    assert not engine.status().running
    assert source.released
    assert detector.closed
    assert engine.preview() is None


def test_starting_twice_is_harmless() -> None:
    opened: list[int] = []

    def open_camera(index: int) -> FrameSource:
        opened.append(index)
        return LoopingSource()

    engine = make_engine(open_camera=open_camera)
    engine.start()
    engine.start()
    engine.stop()
    assert opened == [0]


def test_a_camera_that_will_not_open_raises_and_stays_stopped() -> None:
    def refuse(index: int) -> FrameSource:
        raise RuntimeError(f"Could not open camera {index}")

    engine = make_engine(open_camera=refuse)
    with pytest.raises(RuntimeError, match="Could not open camera 0"):
        engine.start()
    assert not engine.status().running


def test_a_detector_failure_releases_the_camera() -> None:
    source = LoopingSource()

    def broken() -> HandDetector:
        raise FileNotFoundError("model missing")

    engine = TrackingEngine(
        open_camera=lambda index: source,
        make_detector=broken,
        render_preview=lambda frame, hands: None,
    )
    with pytest.raises(FileNotFoundError):
        engine.start()
    assert source.released


def test_a_camera_that_stops_is_reported() -> None:
    source = LoopingSource(frames=3)
    engine = make_engine(source=source)
    engine.start()
    wait_for(lambda: not engine.status().running)
    status = engine.status()
    assert status.error == "The camera stopped sending frames."
    assert source.released


def test_an_error_in_the_loop_is_reported_not_raised() -> None:
    class Exploding(ScriptedDetector):
        def detect(self, frame: object) -> Hands:
            raise RuntimeError("GPU fell over")

    detector = Exploding()
    engine = make_engine(detector=detector)
    engine.start()
    wait_for(lambda: not engine.status().running)
    assert engine.status().error == "Tracking stopped: GPU fell over"
    assert detector.closed


def test_a_custom_gesture_can_fire_a_binding() -> None:
    """update_custom_gestures() takes effect on the very next frame."""
    clock = FakeClock()
    ran: list[Binding] = []
    my_fist = Binding(
        gesture="my_fist",
        name="Custom fist",
        actions=(Action(type=ActionType.HOTKEY, target="media_play_pause"),),
    )
    engine = make_engine(clock=clock, ran=ran, bindings=(my_fist,))
    # Shadow the built-in "fist" shape under a custom name, so real fixture
    # data can exercise the merge-and-classify path end to end.
    engine.update_custom_gestures([CustomGesture(name="my_fist", fingers=(False,) * 5)])
    detector = ScriptedDetector([FIST])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == [my_fist]
    fired = engine.status().last_fired
    assert fired is not None
    assert fired.gesture == "my_fist"


def test_no_capture_in_progress_reports_no_status() -> None:
    engine = make_engine()
    assert engine.capture_status() is None


def test_two_matching_holds_complete_a_capture() -> None:
    clock = FakeClock()
    engine = make_engine(clock=clock)
    engine.start_gesture_capture()
    detector = ScriptedDetector([THREE_UP])

    # First hold: 0.5s dwell (the engine's settings) comfortably exceeded.
    for step in range(8):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert engine.capture_status() is not None
    assert engine.capture_status().stage == "release"  # type: ignore[union-attr]

    # Release: no hand for a moment.
    detector.hands = []
    clock.now = 101.0
    engine.process_frame(object(), detector)

    # Second hold, the same shape again.
    detector.hands = [THREE_UP]
    for step in range(8):
        clock.now = 102.0 + step * 0.1
        engine.process_frame(object(), detector)

    status = engine.capture_status()
    assert status is not None
    assert status.stage == "done"
    assert status.fingers is not None


def test_a_completed_capture_is_not_overwritten_by_later_frames() -> None:
    """The wizard gets to read "done" before the next frame resets it."""
    clock = FakeClock()
    engine = make_engine(clock=clock)
    engine.start_gesture_capture()
    detector = ScriptedDetector([THREE_UP])
    for step in range(8):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    detector.hands = []
    clock.now = 101.0
    engine.process_frame(object(), detector)
    detector.hands = [THREE_UP]
    for step in range(8):
        clock.now = 102.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert engine.capture_status().stage == "done"  # type: ignore[union-attr]

    # A few more frames pass (as they would while the UI is still polling).
    for step in range(5):
        clock.now = 110.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert engine.capture_status().stage == "done"  # type: ignore[union-attr]


def test_cancelling_a_capture_clears_its_status() -> None:
    engine = make_engine()
    engine.start_gesture_capture()
    engine.process_frame(object(), ScriptedDetector([PEACE]))
    assert engine.capture_status() is not None
    engine.cancel_gesture_capture()
    assert engine.capture_status() is None


def test_stopping_tracking_clears_an_in_progress_capture() -> None:
    engine = make_engine(source=LoopingSource(frames=3))
    engine.start_gesture_capture()
    engine.start()
    engine.stop()
    assert engine.capture_status() is None


def test_holding_a_bound_shape_does_not_fire_it_while_capturing() -> None:
    """Recording a new gesture must not also run whatever it happens to match."""
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran)
    engine.start_gesture_capture()
    detector = ScriptedDetector([PEACE])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == []
    assert engine.status().last_fired is None


def test_normal_firing_resumes_once_a_capture_ends() -> None:
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran)
    engine.start_gesture_capture()
    detector = ScriptedDetector([PEACE])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == []
    engine.cancel_gesture_capture()

    for step in range(10):
        clock.now = 200.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == [PAUSE]


def test_a_dwell_in_progress_when_capture_starts_does_not_fire_instantly_after() -> None:
    """A stale dwell timer must not look complete the moment capture ends."""
    clock = FakeClock()
    ran: list[Binding] = []
    engine = make_engine(clock=clock, ran=ran)
    detector = ScriptedDetector([PEACE])
    # Held just short of the 0.5s dwell when the wizard opens.
    for step in range(3):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    assert ran == []

    engine.start_gesture_capture()
    clock.now = 130.0  # the wizard sits open for a while
    engine.process_frame(object(), detector)
    engine.cancel_gesture_capture()

    # The very next frame, still holding the same shape, must not fire yet.
    clock.now = 130.1
    engine.process_frame(object(), detector)
    assert ran == []


def test_changing_camera_while_running_restarts_on_the_new_one() -> None:
    opened: list[int] = []
    lock = threading.Lock()

    def open_camera(index: int) -> FrameSource:
        with lock:
            opened.append(index)
        return LoopingSource()

    engine = make_engine(open_camera=open_camera)
    engine.start()
    engine.update_settings(Settings(camera_index=1))
    assert engine.status().running
    engine.stop()
    assert opened == [0, 1]


def hold_first_shape(engine: TrackingEngine, clock: FakeClock, hand: list[Point]) -> None:
    """Hold one shape long enough for the capture's first hold to complete."""
    detector = ScriptedDetector([hand])
    for step in range(8):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)


def test_capturing_a_built_in_shape_is_flagged_after_the_first_hold() -> None:
    """Holding a peace sign says "that's Peace sign" without a second hold."""
    clock = FakeClock()
    engine = make_engine(clock=clock)
    engine.start_gesture_capture()
    hold_first_shape(engine, clock, PEACE)
    status = engine.capture_status()
    assert status is not None
    assert status.stage == "taken"
    assert status.matches == "peace"
    assert status.fingers == (False, True, True, False, False)


def test_capturing_a_saved_custom_shape_is_flagged_too() -> None:
    clock = FakeClock()
    engine = make_engine(clock=clock)
    engine.update_custom_gestures(
        [CustomGesture(name="Three up", fingers=(False, True, True, True, False))]
    )
    engine.start_gesture_capture()
    hold_first_shape(engine, clock, THREE_UP)
    status = engine.capture_status()
    assert status is not None
    assert status.stage == "taken"
    assert status.matches == "Three up"


def test_a_taken_result_stays_until_the_wizard_retries() -> None:
    """Later frames (hand dropped, a new shape) must not wipe the message."""
    clock = FakeClock()
    engine = make_engine(clock=clock)
    engine.start_gesture_capture()
    hold_first_shape(engine, clock, PEACE)
    for hands in ([], [THREE_UP], [THREE_UP]):
        clock.now += 0.5
        engine.process_frame(object(), ScriptedDetector(hands))
    assert engine.capture_status().stage == "taken"  # type: ignore[union-attr]

    engine.start_gesture_capture()  # "Try again"
    assert engine.capture_status() is None


def test_a_new_shape_still_gets_through_to_the_second_hold() -> None:
    clock = FakeClock()
    engine = make_engine(clock=clock)
    engine.start_gesture_capture()
    hold_first_shape(engine, clock, THREE_UP)
    status = engine.capture_status()
    assert status is not None
    assert status.stage == "release"
    assert status.matches is None
