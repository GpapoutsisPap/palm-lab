"""Live webcam preview with hand landmarks drawn on each frame."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

from palm_lab.actions.models import Binding, load_bindings
from palm_lab.actions.runner import run_binding
from palm_lab.config import MODEL_PATH, fixture_dir
from palm_lab.features import extract
from palm_lab.gestures import classify
from palm_lab.landmarks import Point, normalise
from palm_lab.state import GestureTrigger

TEXT_COLOUR = (255, 255, 255)
TEXT_POSITION = (10, 40)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1.0
FONT_THICKNESS = 2
WINDOW_NAME = "palm-lab preview"
DOT_COLOUR = (0, 255, 0)
DOT_RADIUS = 5
QUIT_KEY = "q"
SAVE_KEY = "s"


def save_fixture(hand: list[dict[str, float]], gesture_name: str) -> Path:
    """Write one hand's landmarks to a timestamped JSON file."""
    directory = fixture_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = directory / f"{gesture_name}_{stamp}.json"
    path.write_text(json.dumps(hand, indent=2))
    return path


def classify_frame(result: object) -> str | None:
    """Run the first detected hand through the recognition pipeline."""
    hands = result.hand_landmarks  # type: ignore[attr-defined]
    if not hands:
        return None
    points = [Point(lm.x, lm.y, lm.z) for lm in hands[0]]
    return classify(extract(normalise(points)))


def _landmarker_options(num_hands: int) -> HandLandmarkerOptions:
    return HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.IMAGE,
        num_hands=num_hands,
    )


PREVIEW_WIDTH = 480
PREVIEW_JPEG_QUALITY = 70
PROBE_LIMIT = 5


class OpenCVSource:
    """A webcam opened through OpenCV, shaped for the tracking engine."""

    def __init__(self, capture: Any) -> None:
        self._capture = capture

    def read(self) -> tuple[bool, object]:
        ok, frame = self._capture.read()
        return bool(ok), frame

    def release(self) -> None:
        self._capture.release()


def open_camera(index: int) -> OpenCVSource:
    """Open a camera by number, or raise with a message a user can act on."""
    capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(
            f"Could not open camera {index}. It may be in use by another app, "
            "or your camera may have a different number. Try Scan in Settings."
        )
    return OpenCVSource(capture)


def probe_cameras(limit: int = PROBE_LIMIT) -> list[int]:
    """Camera numbers that open and deliver a frame right now."""
    # DirectShow fails fast on missing devices; the default backend can take
    # several seconds per index on Windows.
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    found = []
    for index in range(limit):
        capture = cv2.VideoCapture(index, backend)
        try:
            if capture.isOpened() and capture.read()[0]:
                found.append(index)
        finally:
            capture.release()
    return found


class MediaPipeDetector:
    """Finds hands with MediaPipe, returning plain landmark points."""

    def __init__(self, num_hands: int = 1) -> None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Hand landmarker model not found at {MODEL_PATH}")
        self._landmarker = HandLandmarker.create_from_options(
            _landmarker_options(num_hands=num_hands)
        )

    def detect(self, frame: Any) -> list[list[Point]]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        return [[Point(lm.x, lm.y, lm.z) for lm in hand] for hand in result.hand_landmarks]

    def close(self) -> None:
        self._landmarker.close()


def render_preview(frame: Any, hands: list[list[Point]]) -> bytes | None:
    """Mirror the frame like a selfie, shrink it and encode it as JPEG.

    The hand skeleton is not drawn here: the window draws it on top from the
    landmarks, so it stays sharp and matches the rest of the interface.
    """
    height, width = frame.shape[:2]
    mirrored = cv2.flip(frame, 1)
    scale = PREVIEW_WIDTH / width
    small = cv2.resize(mirrored, (PREVIEW_WIDTH, int(height * scale)))
    ok, encoded = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY])
    return encoded.tobytes() if ok else None


def self_test() -> None:
    """Load the hand model and run one detection on a blank image.

    This exercises the whole native MediaPipe stack without needing a camera,
    which is what goes wrong when a packaged build is missing files. Raises if
    anything fails.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Hand landmarker model not found at {MODEL_PATH}")
    blank = np.zeros((64, 64, 3), dtype=np.uint8)
    with HandLandmarker.create_from_options(_landmarker_options(num_hands=1)) as landmarker:
        landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=blank))


def run_preview(
    camera_index: int = 0,
    gesture_name: str = "unlabelled",
    bindings_path: Path | None = None,
) -> None:
    """Show the webcam feed with hand landmarks drawn on it.

    When bindings_path is given, held gestures run their configured actions.
    Pass None to watch and capture without triggering anything.

    Press 'q' to exit, 's' to save the current hand's landmarks as a fixture.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Hand landmarker model not found at {MODEL_PATH}")

    bindings: dict[str, Binding] = {}
    if bindings_path is not None:
        bindings = {b.gesture: b for b in load_bindings(bindings_path)}
        print(f"Loaded {len(bindings)} binding(s) from {bindings_path}")
    else:
        print("No bindings loaded; gestures will be reported but not run.")

    trigger = GestureTrigger()

    with HandLandmarker.create_from_options(_landmarker_options(num_hands=2)) as landmarker:
        capture = cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            raise RuntimeError(f"Could not open camera {camera_index}")

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                result = landmarker.detect(image)

                height, width = frame.shape[:2]
                for hand in result.hand_landmarks:
                    for landmark in hand:
                        x = int(landmark.x * width)
                        y = int(landmark.y * height)
                        cv2.circle(frame, (x, y), DOT_RADIUS, DOT_COLOUR, -1)

                gesture = classify_frame(result)
                label = gesture if gesture else "no gesture"

                fired = trigger.update(gesture, time.monotonic())
                if fired:
                    binding = bindings.get(fired)
                    if binding is None:
                        print(f"TRIGGERED: {fired} (no binding)")
                    else:
                        label = f"{fired} -> {binding.name}"
                        print(f"TRIGGERED: {fired} -> {binding.name}")
                        for outcome in run_binding(binding):
                            if outcome.error is None:
                                print(f"  {outcome.action.type.value}: ok")
                            else:
                                print(
                                    f"  {outcome.action.type.value}: {outcome.error.user_message()}"
                                )

                cv2.putText(
                    frame,
                    label,
                    TEXT_POSITION,
                    FONT,
                    FONT_SCALE,
                    TEXT_COLOUR,
                    FONT_THICKNESS,
                )
                cv2.imshow(WINDOW_NAME, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord(QUIT_KEY):
                    break
                if key == ord(SAVE_KEY) and result.hand_landmarks:
                    points = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in result.hand_landmarks[0]]
                    saved = save_fixture(points, gesture_name)
                    print(f"Saved {saved.name}")
        finally:
            capture.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    run_preview()
