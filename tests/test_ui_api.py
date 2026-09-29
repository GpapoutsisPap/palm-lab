"""Tests for the Python side of the window, as JavaScript would call it."""

import inspect
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import raw_hand, three_fingers_up

from palm_lab.actions.models import Binding, load_bindings
from palm_lab.actions.runner import ActionResult
from palm_lab.custom_gestures import load_custom_gestures
from palm_lab.engine import Hands, TrackingEngine
from palm_lab.landmarks import Point
from palm_lab.settings import Settings, load_settings
from palm_lab.shortcuts import ShortcutError
from palm_lab.ui.api import Api

GOOD_TOML = (
    '[[binding]]\ngesture="peace"\nname="Music"\n'
    '[[binding.action]]\ntype="hotkey"\ntarget="media_play_pause"\n'
)


PEACE = raw_hand("peace")
THREE_UP = three_fingers_up()


class ScriptedDetector:
    """Returns whatever hands the test puts in `hands`."""

    def __init__(self, hands: Hands | None = None) -> None:
        self.hands: Hands = hands or []

    def detect(self, frame: object) -> Hands:
        return self.hands

    def close(self) -> None:
        pass


class Clock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class Source:
    def __init__(self) -> None:
        self.released = False

    def read(self) -> tuple[bool, object]:
        time.sleep(0.002)
        return True, object()

    def release(self) -> None:
        self.released = True


class NoHands:
    def detect(self, frame: object) -> Hands:
        return []

    def close(self) -> None:
        pass


def build(
    tmp_path: Path,
    *,
    bindings_text: str | None = GOOD_TOML,
    settings_text: str | None = None,
    cameras: tuple[int, ...] = (0, 1),
    working_cameras: tuple[int, ...] = (0, 1),
) -> tuple[Api, TrackingEngine, Path, Path, list[Binding]]:
    bindings_file = tmp_path / "bindings.toml"
    settings_file = tmp_path / "settings.toml"
    gestures_file = tmp_path / "gestures.toml"
    if bindings_text is not None:
        bindings_file.write_text(bindings_text, encoding="utf-8")
    if settings_text is not None:
        settings_file.write_text(settings_text, encoding="utf-8")

    def open_camera(index: int) -> Source:
        if index not in working_cameras:
            raise RuntimeError(f"Could not open camera {index}")
        return Source()

    ran: list[Binding] = []

    def run(binding: Binding) -> list[ActionResult]:
        ran.append(binding)
        return [ActionResult(action=a) for a in binding.actions]

    engine = TrackingEngine(
        open_camera=open_camera,
        make_detector=NoHands,
        render_preview=lambda frame, hands: b"\xff\xd8fake-jpeg",
        run=run,
        dispatch=lambda job: job(),
    )
    api = Api(
        engine,
        bindings_file=bindings_file,
        settings_file=settings_file,
        gestures_file=gestures_file,
        probe_cameras=lambda: list(cameras),
        run=run,
    )
    return api, engine, bindings_file, settings_file, ran


@pytest.fixture(autouse=True)
def stop_engines(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make sure no test leaves a tracking thread running."""
    started: list[TrackingEngine] = []
    original = TrackingEngine.start

    def tracking_start(self: TrackingEngine) -> None:
        started.append(self)
        original(self)

    monkeypatch.setattr(TrackingEngine, "start", tracking_start)
    yield
    for engine in started:
        engine.stop()


# Surface -----------------------------------------------------------------------


def test_only_the_intended_methods_are_exposed_to_javascript() -> None:
    """pywebview exposes every public attribute; keep the surface deliberate."""
    public = {name for name, _ in inspect.getmembers(Api) if not name.startswith("_")}
    assert public == {
        "get_state",
        "save_bindings",
        "test_binding",
        "save_settings",
        "list_cameras",
        "start",
        "stop",
        "status",
        "preview",
        "shortcut_state",
        "set_shortcut",
        "open_config_folder",
        "open_project_page",
        "theme_changed",
        "close_choice",
        "save_custom_css",
        "start_gesture_capture",
        "cancel_gesture_capture",
        "capture_status",
        "save_captured_gesture",
        "remove_custom_gesture",
    }


def test_startup_state_is_complete_and_json_safe(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    state = api.get_state()
    json.dumps(state)
    assert state["gestures"] == ["peace", "fist", "open_palm", "thumbs_up"]
    assert state["custom_gestures"] == []
    assert state["action_types"] == ["launch", "open_url", "hotkey"]
    assert "spotify" in state["known_apps"]
    assert "media_play_pause" in state["hotkey_presets"]
    assert state["bindings"][0]["action"] == [{"type": "hotkey", "target": "media_play_pause"}]
    assert state["settings"] == Settings().as_dict()
    assert state["problems"] == []
    assert state["status"]["running"] is False


# Loading problems ------------------------------------------------------------------


def test_an_unreadable_bindings_file_is_reported_and_backed_up_before_saving(
    tmp_path: Path,
) -> None:
    broken = "[[binding]\nthis is not toml"
    api, _, bindings_file, _, _ = build(tmp_path, bindings_text=broken)
    state = api.get_state()
    assert state["bindings"] == []
    assert "could not be read" in state["problems"][0]

    assert api.save_bindings({"binding": []})["ok"]
    backup = bindings_file.with_suffix(".toml.bak")
    assert backup.read_text(encoding="utf-8") == broken

    # A second save must not replace the backup with the new, good file.
    api.save_bindings({"binding": []})
    assert backup.read_text(encoding="utf-8") == broken


def test_an_unreadable_settings_file_falls_back_to_defaults(tmp_path: Path) -> None:
    api, *_ = build(tmp_path, settings_text="camera_index = [")
    state = api.get_state()
    assert state["settings"] == Settings().as_dict()
    assert "settings file could not be read" in state["problems"][0]


# Saving bindings -------------------------------------------------------------------


def test_saving_bindings_writes_the_file_and_applies_them(tmp_path: Path) -> None:
    api, _, bindings_file, _, _ = build(tmp_path, bindings_text=None)
    payload = {
        "binding": [
            {
                "gesture": "fist",
                "name": "Browser",
                "action": [{"type": "open_url", "target": "https://example.com"}],
            }
        ]
    }
    result = api.save_bindings(payload)
    assert result["ok"]
    (saved,) = load_bindings(bindings_file)
    assert saved.gesture == "fist"
    assert api.get_state()["bindings"][0]["name"] == "Browser"


def test_invalid_bindings_are_refused_and_the_file_is_untouched(tmp_path: Path) -> None:
    api, _, bindings_file, _, _ = build(tmp_path)
    before = bindings_file.read_text(encoding="utf-8")
    result = api.save_bindings(
        {
            "binding": [
                {
                    "gesture": "peace",
                    "name": "X",
                    "action": [{"type": "hotkey", "target": "ctrl+?"}],
                }
            ]
        }
    )
    assert not result["ok"]
    assert "Binding 1, action 1" in result["error"]
    assert bindings_file.read_text(encoding="utf-8") == before


def test_test_button_runs_a_bindings_actions_now(tmp_path: Path) -> None:
    api, _, _, _, ran = build(tmp_path)
    result = api.test_binding("peace")
    assert result["ok"]
    assert [r["target"] for r in result["results"]] == ["media_play_pause"]
    assert [b.name for b in ran] == ["Music"]


def test_test_button_on_an_unbound_gesture_explains(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    result = api.test_binding("thumbs_up")
    assert not result["ok"]
    assert "Nothing is bound" in result["error"]


# Settings --------------------------------------------------------------------------


def test_saving_settings_persists_them(tmp_path: Path) -> None:
    api, _, _, settings_file, _ = build(tmp_path)
    result = api.save_settings({"camera_index": 1, "dwell_seconds": 1.5, "cooldown_seconds": 2})
    assert result["ok"]
    assert load_settings(settings_file) == Settings(1, 1.5, 2.0)


def test_the_sounds_switch_is_saved(tmp_path: Path) -> None:
    api, _, _, settings_file, _ = build(tmp_path)
    result = api.save_settings({"camera_index": 0, "sounds": False})
    assert result["ok"]
    assert result["settings"]["sounds"] is False
    assert load_settings(settings_file).sounds is False
    assert api.get_state()["settings"]["sounds"] is False


def test_invalid_settings_are_refused(tmp_path: Path) -> None:
    api, _, _, settings_file, _ = build(tmp_path)
    result = api.save_settings({"dwell_seconds": 0})
    assert not result["ok"]
    assert "dwell_seconds" in result["error"]
    assert not settings_file.exists()


def test_switching_to_a_broken_camera_saves_but_reports(tmp_path: Path) -> None:
    api, *_ = build(tmp_path, working_cameras=(0,))
    assert api.start()["ok"]
    result = api.save_settings({"camera_index": 3})
    assert not result["ok"]
    assert "Could not open camera 3" in result["error"]
    assert api.get_state()["settings"]["camera_index"] == 3


def test_camera_scan_is_refused_while_tracking(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    assert api.list_cameras() == {"ok": True, "cameras": [0, 1]}
    api.start()
    assert not api.list_cameras()["ok"]
    api.stop()


# Tracking --------------------------------------------------------------------------


def test_start_preview_and_stop(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    assert api.preview() is None
    result = api.start()
    assert result["ok"]
    assert result["status"]["running"]

    deadline = time.monotonic() + 3
    while api.preview() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    preview = api.preview()
    assert preview is not None and preview["image"].startswith("data:image/jpeg;base64,")
    assert preview["hands"] == []

    assert api.stop()["status"]["running"] is False
    assert api.preview() is None


def test_start_with_a_missing_camera_explains(tmp_path: Path) -> None:
    api, *_ = build(tmp_path, working_cameras=())
    result = api.start()
    assert not result["ok"]
    assert "Could not open camera 0" in result["error"]
    assert result["status"]["running"] is False


def test_app_suggestions_merge_installed_apps_with_built_ins(tmp_path: Path) -> None:
    """Typing in an Open app block suggests what is actually installed."""
    api, engine, bindings_file, settings_file, _ = build(tmp_path)
    api = Api(
        engine,
        bindings_file=bindings_file,
        settings_file=settings_file,
        gestures_file=tmp_path / "gestures.toml",
        probe_cameras=lambda: [],
        list_apps=lambda: ["Steam", "Discord", "Counter-Strike 2"],
    )
    apps = api.get_state()["known_apps"]
    assert {"Steam", "Discord", "Counter-Strike 2", "spotify", "notepad"} <= set(apps)
    assert "steam" not in apps  # the built-in is not listed twice in another case
    assert apps == sorted(apps, key=str.lower)


def test_a_broken_start_menu_does_not_break_the_window(tmp_path: Path) -> None:
    api, engine, bindings_file, settings_file, _ = build(tmp_path)

    def unreadable() -> list[str]:
        raise PermissionError("access denied")

    api = Api(
        engine,
        bindings_file=bindings_file,
        settings_file=settings_file,
        gestures_file=tmp_path / "gestures.toml",
        probe_cameras=lambda: [],
        list_apps=unreadable,
    )
    assert "spotify" in api.get_state()["known_apps"]


def test_preview_hands_are_mirrored_like_the_picture(tmp_path: Path) -> None:
    """The picture is flipped like a selfie, so the landmarks must be too."""
    api, engine, *_ = build(tmp_path)

    class OneHand:
        def detect(self, frame: object) -> Hands:
            return [[Point(0.25, 0.5, 0.0)] * 21]

        def close(self) -> None:
            pass

    engine.process_frame(object(), OneHand())
    preview = api.preview()
    assert preview is not None
    assert preview["hands"][0][0] == [0.75, 0.5]
    assert len(preview["hands"][0]) == 21


# Custom gestures -------------------------------------------------------------------


def capture_api(tmp_path: Path) -> tuple[Api, TrackingEngine, Clock, Path]:
    """An Api/engine pair with a controllable clock, for driving a capture by hand."""
    clock = Clock()
    engine = TrackingEngine(
        open_camera=lambda index: Source(),
        make_detector=NoHands,
        render_preview=lambda frame, hands: b"\xff\xd8fake-jpeg",
        clock=clock,
    )
    gestures_file = tmp_path / "gestures.toml"
    api = Api(
        engine,
        bindings_file=tmp_path / "bindings.toml",
        settings_file=tmp_path / "settings.toml",
        gestures_file=gestures_file,
        probe_cameras=lambda: [0],
    )
    return api, engine, clock, gestures_file


def complete_a_capture(engine: TrackingEngine, clock: Clock, shape: list[Point] = THREE_UP) -> None:
    """Drive two matching, released holds of `shape` through process_frame."""
    engine.start_gesture_capture()
    detector = ScriptedDetector([shape])
    for step in range(10):
        clock.now = 100.0 + step * 0.1
        engine.process_frame(object(), detector)
    detector.hands = []
    clock.now += 0.2
    engine.process_frame(object(), detector)
    detector.hands = [shape]
    for _ in range(10):
        clock.now += 0.1
        engine.process_frame(object(), detector)


def test_capture_status_is_none_before_starting(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    assert api.capture_status() is None


def test_starting_a_capture_starts_tracking_if_it_is_not_running(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    result = api.start_gesture_capture()
    assert result["ok"]
    assert result["status"]["running"] is True
    api.cancel_gesture_capture()


def test_starting_a_capture_reports_a_camera_failure(tmp_path: Path) -> None:
    api, *_ = build(tmp_path, working_cameras=())
    result = api.start_gesture_capture()
    assert not result["ok"]
    assert "Could not open camera" in result["error"]


def test_a_completed_capture_can_be_named_and_saved(tmp_path: Path) -> None:
    api, engine, clock, gestures_file = capture_api(tmp_path)
    complete_a_capture(engine, clock)
    status = api.capture_status()
    assert status is not None
    assert status["stage"] == "done"

    result = api.save_captured_gesture("Three up")
    assert result["ok"]
    assert result["custom_gestures"] == [{"name": "Three up", "fingers": status["fingers"]}]
    assert [g.name for g in load_custom_gestures(gestures_file)] == ["Three up"]
    # Saving clears the capture, so the wizard can close.
    assert api.capture_status() is None


def test_saving_without_a_completed_capture_is_refused(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    result = api.save_captured_gesture("Anything")
    assert not result["ok"]
    assert "No completed gesture capture" in result["error"]


def test_capturing_an_existing_shape_reports_which_gesture_it_is(tmp_path: Path) -> None:
    """PEACE is already "peace": the wizard hears so, and nothing can be saved."""
    api, engine, clock, gestures_file = capture_api(tmp_path)
    complete_a_capture(engine, clock, shape=PEACE)
    status = api.capture_status()
    assert status is not None
    assert status["stage"] == "taken"
    assert status["matches"] == "peace"
    assert status["fingers"] == [False, True, True, False, False]

    result = api.save_captured_gesture("My peace sign")
    assert not result["ok"]
    assert load_custom_gestures(gestures_file) == []


def test_cancelling_a_capture_clears_its_status(tmp_path: Path) -> None:
    api, engine, clock, _ = capture_api(tmp_path)
    engine.start_gesture_capture()
    engine.process_frame(object(), ScriptedDetector([PEACE]))
    assert api.capture_status() is not None
    api.cancel_gesture_capture()
    assert api.capture_status() is None


def test_a_saved_custom_gesture_can_be_removed(tmp_path: Path) -> None:
    api, engine, clock, gestures_file = capture_api(tmp_path)
    complete_a_capture(engine, clock)
    api.save_captured_gesture("Three up")

    result = api.remove_custom_gesture("three up")  # case-insensitive
    assert result["ok"]
    assert result["custom_gestures"] == []
    assert load_custom_gestures(gestures_file) == []


def test_removing_an_unknown_custom_gesture_is_refused(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    result = api.remove_custom_gesture("Nope")
    assert not result["ok"]
    assert "No custom gesture" in result["error"]


# Window, shortcuts and links ---------------------------------------------------


class FakeShortcuts:
    def __init__(self, fail: bool = False) -> None:
        self.made: set[str] = set()
        self.fail = fail

    def state(self) -> dict[str, bool]:
        return {"supported": True, **{k: k in self.made for k in ("desktop", "start_menu")}}

    def set(self, kind: str, enabled: bool) -> None:
        if self.fail:
            raise ShortcutError("Access is denied.")
        (self.made.add if enabled else self.made.discard)(kind)


def bare_api(tmp_path: Path, **extra: object) -> Api:
    engine = TrackingEngine(
        open_camera=lambda index: Source(),
        make_detector=NoHands,
        render_preview=lambda frame, hands: None,
    )
    return Api(
        engine,
        bindings_file=tmp_path / "config" / "bindings.toml",
        settings_file=tmp_path / "config" / "settings.toml",
        gestures_file=tmp_path / "config" / "gestures.toml",
        probe_cameras=lambda: [0],
        list_apps=lambda: [],
        **extra,  # type: ignore[arg-type]
    )


def test_state_carries_version_accent_and_project(tmp_path: Path) -> None:
    api = bare_api(tmp_path, accent=lambda: ("#111111",) * 7)
    state = api.get_state()
    assert state["accent"] == ["#111111"] * 7
    assert state["version"].count(".") == 2
    assert state["project_url"].startswith("https://github.com/")


def test_shortcuts_can_be_switched_on_and_off(tmp_path: Path) -> None:
    shortcuts = FakeShortcuts()
    api = bare_api(tmp_path, shortcuts=shortcuts)
    assert api.shortcut_state() == {"supported": True, "desktop": False, "start_menu": False}
    assert api.set_shortcut("desktop", True) == {
        "ok": True,
        "shortcuts": {"supported": True, "desktop": True, "start_menu": False},
    }
    assert api.set_shortcut("desktop", False)["shortcuts"]["desktop"] is False


def test_a_shortcut_failure_is_reported(tmp_path: Path) -> None:
    api = bare_api(tmp_path, shortcuts=FakeShortcuts(fail=True))
    result = api.set_shortcut("start_menu", True)
    assert result["ok"] is False
    assert result["error"] == "Access is denied."
    assert result["shortcuts"]["start_menu"] is False


def test_open_config_folder_creates_and_shows_it(tmp_path: Path) -> None:
    opened: list[Path] = []
    api = bare_api(tmp_path, open_path=opened.append)
    assert api.open_config_folder() == {"ok": True}
    assert opened == [tmp_path / "config"] and opened[0].is_dir()


def test_open_config_folder_reports_failure(tmp_path: Path) -> None:
    def refuse(path: Path) -> None:
        raise OSError("no file manager")

    result = bare_api(tmp_path, open_path=refuse).open_config_folder()
    assert result["ok"] is False and "no file manager" in result["error"]


def test_open_project_page(tmp_path: Path) -> None:
    urls: list[str] = []
    assert bare_api(tmp_path, open_url=urls.append).open_project_page() == {"ok": True}
    assert urls[0].startswith("https://github.com/")


def test_theme_change_reaches_python(tmp_path: Path) -> None:
    calls: list[str] = []
    api = bare_api(tmp_path, on_theme_change=lambda: calls.append("changed"))
    assert api.theme_changed() == {"ok": True}
    assert calls == ["changed"]


def close_api(tmp_path: Path) -> tuple[Api, list[str], Path]:
    chosen: list[str] = []
    settings_file = tmp_path / "settings.toml"
    api = Api(
        TrackingEngine(
            open_camera=lambda index: Source(),
            make_detector=NoHands,
            render_preview=lambda frame, hands: b"jpeg",
        ),
        bindings_file=tmp_path / "bindings.toml",
        settings_file=settings_file,
        gestures_file=tmp_path / "gestures.toml",
        probe_cameras=lambda: [0],
        on_close_choice=chosen.append,
    )
    return api, chosen, settings_file


@pytest.mark.parametrize("choice", ["background", "quit"])
def test_a_close_answer_is_passed_on_without_being_remembered(tmp_path: Path, choice: str) -> None:
    api, chosen, settings_file = close_api(tmp_path)
    result = api.close_choice(choice, False)
    assert result["ok"]
    assert chosen == [choice]
    assert result["settings"]["close_action"] == "ask"
    assert not settings_file.exists()


def test_dont_show_again_saves_the_answer(tmp_path: Path) -> None:
    api, chosen, settings_file = close_api(tmp_path)
    api.save_settings({"camera_index": 2, "sounds": False})
    result = api.close_choice("background", True)
    assert result["ok"]
    assert chosen == ["background"]
    saved = load_settings(settings_file)
    assert saved.close_action == "background"
    # Remembering the answer leaves every other setting as it was.
    assert saved.camera_index == 2 and saved.sounds is False
    assert api.get_state()["settings"]["close_action"] == "background"


def test_an_unknown_close_answer_is_refused(tmp_path: Path) -> None:
    api, chosen, _ = close_api(tmp_path)
    result = api.close_choice("minimize", True)
    assert not result["ok"]
    assert chosen == []


def test_the_close_setting_can_be_changed_from_settings(tmp_path: Path) -> None:
    api, _, settings_file = close_api(tmp_path)
    result = api.save_settings({"close_action": "quit"})
    assert result["ok"]
    assert load_settings(settings_file).close_action == "quit"


def css_api(tmp_path: Path, *, allowed: bool = True, css: str | None = None) -> tuple[Api, Path]:
    css_file = tmp_path / "custom.css"
    if css is not None:
        css_file.write_text(css, encoding="utf-8")
    api = Api(
        TrackingEngine(
            open_camera=lambda index: Source(),
            make_detector=NoHands,
            render_preview=lambda frame, hands: b"jpeg",
        ),
        bindings_file=tmp_path / "bindings.toml",
        settings_file=tmp_path / "settings.toml",
        gestures_file=tmp_path / "gestures.toml",
        probe_cameras=lambda: [0],
        custom_css_file=css_file,
        custom_css_allowed=allowed,
    )
    return api, css_file


def test_the_page_gets_the_saved_css(tmp_path: Path) -> None:
    api, css_file = css_api(tmp_path, css=":root { --accent: red; }")
    state = api.get_state()["custom_css"]
    assert state == {
        "text": ":root { --accent: red; }",
        "file": str(css_file),
        "allowed": True,
        "error": None,
    }


def test_css_typed_in_settings_is_saved(tmp_path: Path) -> None:
    api, css_file = css_api(tmp_path)
    assert api.save_custom_css(".gesture { border-radius: 16px; }") == {"ok": True}
    assert css_file.read_text(encoding="utf-8") == ".gesture { border-radius: 16px; }"
    assert api.get_state()["custom_css"]["text"] == ".gesture { border-radius: 16px; }"


def test_no_custom_css_flag_is_passed_to_the_page(tmp_path: Path) -> None:
    """The CSS is still loaded, so it can be fixed in the editor, but not applied."""
    api, _ = css_api(tmp_path, allowed=False, css="* { display: none; }")
    state = api.get_state()["custom_css"]
    assert state["allowed"] is False
    assert state["text"] == "* { display: none; }"


def test_an_oversized_css_file_is_reported_not_used(tmp_path: Path) -> None:
    api, _ = css_api(tmp_path, css="a" * 300_000)
    state = api.get_state()["custom_css"]
    assert state["text"] == ""
    assert "not used" in state["error"]


@pytest.mark.parametrize("bad", ["a" * 300_000, 42])
def test_bad_css_is_refused(tmp_path: Path, bad: object) -> None:
    api, css_file = css_api(tmp_path)
    result = api.save_custom_css(bad)  # type: ignore[arg-type]
    assert not result["ok"]
    assert not css_file.exists()


def test_without_a_css_file_the_feature_is_off(tmp_path: Path) -> None:
    api, *_ = build(tmp_path)
    assert api.get_state()["custom_css"]["file"] is None
    assert not api.save_custom_css("x")["ok"]
