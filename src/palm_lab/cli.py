"""Command line entry point for palm-lab."""

import argparse
import sys
import time
from collections.abc import Callable

from palm_lab.actions.errors import ActionError
from palm_lab.actions.models import load_bindings
from palm_lab.config import (
    MODEL_PATH,
    bindings_path,
    config_dir,
    ensure_bindings_file,
    ui_static_dir,
)
from palm_lab.custom_css import custom_css_path
from palm_lab.custom_gestures import CustomGestureError, gestures_path, load_custom_gestures
from palm_lab.hand_profile import HandProfileError, hand_profile_path, load_hand_profile
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

    ui = subparsers.add_parser("ui", help="open the palm-lab window (the default)")
    ui.add_argument(
        "--debug", action="store_true", help="enable browser developer tools in the window"
    )
    ui.add_argument(
        "--background",
        action="store_true",
        help="start hidden in the notification area with tracking on (used at sign-in)",
    )
    ui.add_argument(
        "--no-custom-css",
        action="store_true",
        help="ignore your custom CSS for this run (if it made the window unusable)",
    )

    run = subparsers.add_parser("run", help="watch the camera in a plain preview window")
    run.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")

    capture = subparsers.add_parser("capture", help="save landmark fixtures for a gesture")
    capture.add_argument("gesture", help="label to save captures under")
    capture.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")

    popup = subparsers.add_parser(
        "popup", help="show the pop-up by the clock with a few made-up runs (Windows)"
    )
    popup.add_argument(
        "--theme", choices=["light", "dark"], help="draw it light or dark (default: as palm-lab is)"
    )

    subparsers.add_parser("config", help="show the config location and bindings")
    subparsers.add_parser("doctor", help="check that everything needed is in place")

    shortcut = subparsers.add_parser(
        "shortcut", help="put a palm-lab shortcut on the desktop (Windows)"
    )
    shortcut.add_argument(
        "--start-menu", action="store_true", help="also add palm-lab to the Start menu"
    )
    shortcut.add_argument(
        "--startup", action="store_true", help="also start palm-lab when you sign in to Windows"
    )
    shortcut.add_argument("--remove", action="store_true", help="remove all its shortcuts instead")

    # A bare `palm-lab`, which is what double-clicking the .exe runs, opens the
    # window. This must come after add_subparsers, which resets dest="command".
    parser.set_defaults(
        command="ui", debug=False, background=False, no_custom_css=False, camera=0, theme=None
    )
    return parser


def _cmd_ui(args: argparse.Namespace) -> int:
    # Imported here so config/doctor never load pywebview, OpenCV or MediaPipe.
    from palm_lab.ui.app import run_ui

    return run_ui(debug=args.debug, background=args.background, custom_css=not args.no_custom_css)


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
    print(f"Custom CSS:       {custom_css_path()}")
    try:
        tuned = "tuned to your hand" if load_hand_profile() else "standard (not tuned)"
    except HandProfileError as exc:
        tuned = f"unreadable ({exc})"
    print(f"Hand tuning:      {hand_profile_path()}  {tuned}")
    try:
        bindings = load_bindings(path)
    except ActionError as exc:
        print(f"\nBindings file has a problem: {exc.user_message()}")
        return 1
    print(f"\n{len(bindings)} binding(s):")
    for binding in bindings:
        off = "" if binding.enabled else "  (off)"
        print(f"  {binding.gesture:<12} {binding.name}{off}")
        for action in binding.actions:
            print(f"    {action.type.value:<10} {action.target}")

    try:
        custom = load_custom_gestures()
    except CustomGestureError as exc:
        print(f"\nCustom gestures file has a problem: {exc}")
        return 1
    print(f"\nGestures file:    {gestures_path()}")
    print(f"{len(custom)} custom gesture(s):")
    for gesture in custom:
        finger_names = ("thumb", "index", "middle", "ring", "pinky")
        fingers = (
            ", ".join(name for name, up in zip(finger_names, gesture.fingers, strict=True) if up)
            or "no fingers"
        )
        print(f"  {gesture.name:<20} ({fingers})")
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

    try:
        import webview  # noqa: F401
    except ImportError:
        problems += 1
        print("[FAIL] pywebview not installed; run: uv pip install -e '.[dev]'")
    else:
        print("[ok]   pywebview installed")

    from palm_lab.ui.app import load_page

    try:
        load_page(ui_static_dir())
    except (OSError, ValueError) as exc:
        problems += 1
        print(f"[FAIL] window files could not be loaded: {exc}")
    else:
        print("[ok]   window files")

    # Only worth trying once the model and libraries are known to be present.
    if not problems:
        try:
            from palm_lab.camera import self_test

            self_test()
        except Exception as exc:
            problems += 1
            print(f"[FAIL] hand detection could not start: {exc}")
        else:
            print("[ok]   hand detection runs")

    print("\nAll good." if not problems else f"\n{problems} problem(s) found.")
    return 1 if problems else 0


def _cmd_shortcut(args: argparse.Namespace) -> int:
    from palm_lab.shortcuts import ShortcutError, Shortcuts

    shortcuts = Shortcuts()
    if args.remove:
        kinds = ["desktop", "start_menu", "startup"]
    else:
        kinds = ["desktop"]
        if args.start_menu:
            kinds.append("start_menu")
        if args.startup:
            kinds.append("startup")
    try:
        for kind in kinds:
            if args.remove:
                shortcuts.remove(kind)
                print(f"Removed {shortcuts.path(kind)}")
            else:
                print(f"Created {shortcuts.create(kind)}")
    except ShortcutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_popup(args: argparse.Namespace, sleep: Callable[[float], None] = time.sleep) -> int:
    """Show the card a few times, as gesture runs would, to see how it looks."""
    from palm_lab.overlay import Overlay
    from palm_lab.run_popup import RunPopup, sample_runs
    from palm_lab.settings import SettingsError, load_settings
    from palm_lab.windows import apps_use_light_theme

    theme = args.theme
    if theme is None:
        try:
            theme = load_settings().theme
        except (SettingsError, OSError):
            theme = "system"
    dark = theme == "dark" or (theme == "system" and apps_use_light_theme() == 0)

    overlay = Overlay(dark=lambda: dark)
    overlay.start()
    if not overlay.available:
        print("The pop-up is a Windows window, so there's nothing to show here.", file=sys.stderr)
        return 1
    popup = RunPopup(
        show=overlay.show,
        mode=lambda: "all",
        window_in_front=lambda: False,  # this is a demo: always show
        user_busy=lambda: False,
        notify=lambda title, detail: None,
    )
    print(f"Showing the pop-up by the clock ({'dark' if dark else 'light'}):")
    for what, event, pause in sample_runs():
        print(f"  - {what}")
        popup.on_run(event)
        sleep(pause)
    overlay.stop()
    return 0


HANDLERS = {
    "ui": _cmd_ui,
    "run": _cmd_run,
    "capture": _cmd_capture,
    "config": _cmd_config,
    "doctor": _cmd_doctor,
    "popup": _cmd_popup,
    "shortcut": _cmd_shortcut,
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
