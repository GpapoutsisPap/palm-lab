"""Command line entry point for palm-lab."""

import argparse
import sys

from palm_lab.actions.errors import ActionError
from palm_lab.actions.models import load_bindings
from palm_lab.config import (
    MODEL_PATH,
    bindings_path,
    config_dir,
    ensure_bindings_file,
)
from palm_lab.version import __version__

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker"
    "/hand_landmarker/float16/1/hand_landmarker.task"
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Public so tests can exercise it directly."""
    parser = argparse.ArgumentParser(
        prog="palm-lab",
        description="Trigger shortcuts with hand gestures seen by your webcam.",
    )
    parser.add_argument("--version", action="version", version=f"palm-lab {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="watch the camera and run bindings")
    run.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")

    capture = subparsers.add_parser("capture", help="save landmark fixtures for a gesture")
    capture.add_argument("gesture", help="label to save captures under")
    capture.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")

    subparsers.add_parser("config", help="show the config location and bindings")
    subparsers.add_parser("doctor", help="check that everything needed is in place")

    # A bare `palm-lab` runs no subparser, so supply what _cmd_run needs.
    # This must come after add_subparsers, which resets dest="command" to None.
    parser.set_defaults(command="run", camera=0)
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    # Imported here so config/doctor never load OpenCV and MediaPipe.
    from palm_lab.camera import run_preview

    path, created = ensure_bindings_file()
    if created:
        print(f"Created a default bindings file at {path}")
    run_preview(camera_index=args.camera, bindings_path=path)
    return 0


def _cmd_capture(args: argparse.Namespace) -> int:
    from palm_lab.camera import run_preview

    run_preview(
        camera_index=args.camera,
        gesture_name=args.gesture,
        bindings_path=None,
    )
    return 0


def _cmd_config(_: argparse.Namespace) -> int:
    path, created = ensure_bindings_file()
    print(f"Config directory: {config_dir()}")
    print(f"Bindings file:    {path}{'  (just created)' if created else ''}")
    try:
        bindings = load_bindings(path)
    except ActionError as exc:
        print(f"\nBindings file has a problem: {exc.user_message()}")
        return 1
    print(f"\n{len(bindings)} binding(s):")
    for binding in bindings:
        print(f"  {binding.gesture:<12} {binding.name}")
        for action in binding.actions:
            print(f"    {action.type.value:<10} {action.target}")
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    problems = 0

    if MODEL_PATH.exists():
        size_mb = MODEL_PATH.stat().st_size / 1_000_000
        print(f"[ok]   hand landmarker model ({size_mb:.1f} MB)")
    else:
        problems += 1
        print(f"[FAIL] hand landmarker model missing at {MODEL_PATH}")
        print("       Download it with:")
        print(f'         curl.exe -o "{MODEL_PATH}" {MODEL_URL}')

    path = bindings_path()
    if not path.exists():
        print(f"[ok]   no bindings file yet; one will be written to {path}")
    else:
        try:
            bindings = load_bindings(path)
        except ActionError as exc:
            problems += 1
            print(f"[FAIL] bindings file: {exc.user_message()}")
        else:
            print(f"[ok]   bindings file: {len(bindings)} binding(s) at {path}")

    try:
        import cv2
    except ImportError:
        problems += 1
        print("[FAIL] opencv not installed; run: uv pip install -e '.[dev]'")
    else:
        print(f"[ok]   opencv {cv2.__version__}")

    try:
        import mediapipe
    except ImportError:
        problems += 1
        print("[FAIL] mediapipe not installed; run: uv pip install -e '.[dev]'")
    else:
        print(f"[ok]   mediapipe {mediapipe.__version__}")

    print("\nAll good." if not problems else f"\n{problems} problem(s) found.")
    return 1 if problems else 0


HANDLERS = {
    "run": _cmd_run,
    "capture": _cmd_capture,
    "config": _cmd_config,
    "doctor": _cmd_doctor,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return handler(args)
    except ActionError as exc:
        print(f"Error: {exc.user_message()}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
