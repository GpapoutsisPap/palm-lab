"""Live webcam preview with hand landmarks drawn on each frame."""

import json
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

MODEL_PATH = Path(__file__).parent / "assets" / "hand_landmarker.task"

WINDOW_NAME = "palm-lab preview"
DOT_COLOUR = (0, 255, 0)
DOT_RADIUS = 5
QUIT_KEY = "q"
FIXTURE_DIR = Path(__file__).parents[2] / "tests" / "fixtures"


def save_fixture(hand: list[dict[str, float]], gesture_name: str) -> Path:
    """Write one hand's landmarks to a timestamped JSON file."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = FIXTURE_DIR / f"{gesture_name}_{stamp}.json"
    path.write_text(json.dumps(hand, indent=2))
    return path


def run_preview(camera_index: int = 0, gesture_name: str = "unlabelled") -> None:
    """Show the webcam feed with hand landmarks drawn on it.

    Press 'q' to exit, 's' to save the current hand's landmarks as a fixture.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Hand landmarker model not found at {MODEL_PATH}")

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.IMAGE,
        num_hands=2,
    )

    with HandLandmarker.create_from_options(options) as landmarker:
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

                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord(QUIT_KEY):
                    break
                if key == ord("s") and result.hand_landmarks:
                    points = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in result.hand_landmarks[0]]
                    saved = save_fixture(points, gesture_name)
                    print(f"Saved {saved.name}")
        finally:
            capture.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    run_preview()
