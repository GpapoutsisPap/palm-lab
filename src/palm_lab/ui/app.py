"""Open the palm-lab window."""

import threading
from collections.abc import Callable
from pathlib import Path

from palm_lab.config import bindings_path, ensure_bindings_file, icon_path, ui_static_dir
from palm_lab.custom_css import custom_css_path
from palm_lab.custom_gestures import gestures_path
from palm_lab.hand_profile import hand_profile_path
from palm_lab.overlay import Overlay, busy, notification_state
from palm_lab.palettes import DEFAULT_PALETTE, PALETTES
from palm_lab.palettes import background as palette_background
from palm_lab.run_popup import RunPopup
from palm_lab.settings import Settings, SettingsError, load_settings, settings_path
from palm_lab.single_instance import Instance, instance_guard
from palm_lab.ui.lifecycle import Lifecycle, WindowControls
from palm_lab.ui.tray import Tray
from palm_lab.windows import (
    apps_use_light_theme,
    foreground_window,
    set_app_id,
    set_caption_colour,
)

WINDOW_TITLE = "palm-lab"
WINDOW_SIZE = (1200, 800)
WINDOW_MIN_SIZE = (960, 640)

# Must match --mica in app.css. The window frame, the title bar and the page
# background are one colour, so the title bar reads as part of the app. Each
# colour palette has its own (palm_lab.palettes); these are the defaults.
LIGHT_BACKGROUND = PALETTES[DEFAULT_PALETTE].light_background
DARK_BACKGROUND = PALETTES[DEFAULT_PALETTE].dark_background


def resolved_theme(
    theme: str = "system", read_setting: Callable[[], int | None] = apps_use_light_theme
) -> str:
    """The theme to draw, light or dark: the setting, with "system" read from Windows."""
    if theme in ("light", "dark"):
        return theme
    return "dark" if read_setting() == 0 else "light"


def window_background(
    read_setting: Callable[[], int | None] = apps_use_light_theme,
    theme: str = "system",
    palette: str = DEFAULT_PALETTE,
) -> str:
    """The window frame is the page's background colour, in either theme and any palette."""
    return palette_background(palette, dark=resolved_theme(theme, read_setting) == "dark")


def load_page(static_dir: Path, theme: str | None = None, palette: str | None = None) -> str:
    """Build one self-contained HTML page with the CSS and JS inlined.

    Inlining avoids serving files or resolving URLs, which behaves differently
    between running from source and running from a PyInstaller build. A theme
    ("light" or "dark") and a colour palette are written onto <html> so the
    very first frame is drawn in them, with no flash of the defaults.
    """
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    css = (static_dir / "app.css").read_text(encoding="utf-8")
    js = (static_dir / "app.js").read_text(encoding="utf-8")
    style_tag = '<link rel="stylesheet" href="app.css">'
    script_tag = '<script src="app.js"></script>'
    if style_tag not in html or script_tag not in html:
        raise ValueError("index.html must reference app.css and app.js exactly once")
    if theme is not None:
        html = html.replace("<html", f'<html data-theme="{theme}"', 1)
    if palette is not None and palette in PALETTES:
        html = html.replace("<html", f'<html data-palette="{palette}"', 1)
    return html.replace(style_tag, f"<style>\n{css}\n</style>").replace(
        script_tag, f"<script>\n{js}\n</script>"
    )


def saved_settings() -> Settings:
    """The settings as last saved, or the defaults if the file can't be read."""
    try:
        return load_settings()
    except (SettingsError, OSError):
        return Settings()


def run_ui(debug: bool = False, background: bool = False, custom_css: bool = True) -> int:
    """Open the window, or wake the palm-lab that is already running."""
    guard = instance_guard()
    if not guard.acquire():
        # Already running (perhaps hidden in the notification area): bring it
        # forward instead of starting a second copy that fights over the camera.
        # A sign-in launch finding one already running has nothing to do.
        if not background:
            guard.wake_existing()
        return 0
    try:
        return _run_window(debug=debug, background=background, custom_css=custom_css, guard=guard)
    finally:
        guard.release()


def _run_window(*, debug: bool, background: bool, custom_css: bool, guard: Instance) -> int:
    """Create the engine, bridge, tray icon and window, and block until quit."""
    import webview

    from palm_lab.camera import MediaPipeDetector, open_camera, probe_cameras, render_preview
    from palm_lab.engine import TrackingEngine
    from palm_lab.ui.api import Api
    from palm_lab.updates import UpdateChecker

    ensure_bindings_file()
    set_app_id()
    engine = TrackingEngine(
        open_camera=open_camera,
        # Two hands, so two-hand setups can be recognised.
        make_detector=lambda: MediaPipeDetector(num_hands=2),
        render_preview=render_preview,
    )
    # Once a day, ask GitHub whether a newer palm-lab is out (palm_lab.updates).
    updates = UpdateChecker(
        enabled=lambda: saved_settings().check_updates,
        # tray is defined below; this only runs once the window is up.
        on_found=lambda release: tray.notify(
            f"palm-lab {release.version} is out",
            "Open palm-lab to see what’s new and download it.",
        ),
    )
    api = Api(
        engine,
        bindings_file=bindings_path(),
        settings_file=settings_path(),
        gestures_file=gestures_path(),
        probe_cameras=probe_cameras,
        # These refer to names defined below; they are only called once the
        # window is running.
        on_theme_change=lambda: colour_title_bar(),
        on_close_choice=lambda choice: lifecycle.choose(choice),
        custom_css_file=custom_css_path(),
        custom_css_allowed=custom_css,
        hand_profile_file=hand_profile_path(),
        updates=updates,
    )
    starting = saved_settings()
    theme, palette = starting.theme, starting.palette
    window = webview.create_window(
        WINDOW_TITLE,
        html=load_page(ui_static_dir(), theme=resolved_theme(theme), palette=palette),
        js_api=api,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
        background_color=window_background(theme=theme, palette=palette),
        hidden=background,
    )
    if window is None:
        return 1

    # Whether the window was minimized when someone closed it from the taskbar,
    # so the close question (or the window, later) comes back into view.
    minimized = False

    def show_window() -> None:
        nonlocal minimized
        window.show()
        if minimized:
            window.restore()
            minimized = False

    def ask_before_closing() -> None:
        nonlocal minimized
        if minimized:
            window.restore()
            minimized = False
        window.evaluate_js("askBeforeClosing()")

    def toggle_tracking() -> None:
        result = api.stop() if engine.running else api.start()
        if not result["ok"]:
            tray.notify("palm-lab could not start tracking", str(result["error"]))
        tray.refresh()

    def pause_tracking(minutes: int) -> None:
        api.pause(minutes)
        tray.refresh()

    def resume_tracking() -> None:
        result = api.resume()
        if not result["ok"]:
            tray.notify("palm-lab could not start tracking", str(result["error"]))
        tray.refresh()

    tray = Tray(
        icon_file=icon_path(),
        on_open=lambda: lifecycle.show(),
        on_toggle_tracking=toggle_tracking,
        on_quit=lambda: lifecycle.quit(),
        is_tracking=lambda: engine.running,
        on_pause=pause_tracking,
        on_resume=resume_tracking,
        is_paused=lambda: api.status()["paused_until"] is not None,
    )
    lifecycle = Lifecycle(
        settings=saved_settings,
        controls=WindowControls(
            show=show_window,
            hide=window.hide,
            destroy=window.destroy,
            ask_before_closing=ask_before_closing,
            set_preview=engine.set_preview_enabled,
            notify=tray.notify,
        ),
        can_run_in_background=lambda: tray.available,
    )

    def window_in_front() -> bool:
        """Whether palm-lab's own window is the one in use: it then says what ran itself."""
        if lifecycle.hidden:
            return False
        handle = getattr(getattr(window, "native", None), "Handle", None)
        try:
            return handle is not None and foreground_window() == int(handle.ToInt64())
        except Exception:  # noqa: BLE001 - when unsure, show the pop-up
            return False

    # The pop-up by the clock when a gesture runs (see run_popup and overlay).
    overlay = Overlay(dark=lambda: resolved_theme(saved_settings().theme) == "dark")
    popup = RunPopup(
        show=overlay.show,
        mode=lambda: saved_settings().run_popup,
        window_in_front=window_in_front,
        user_busy=lambda: busy(notification_state()),
        notify=tray.notify,
    )
    engine.add_run_listener(popup.on_run)

    def colour_title_bar() -> None:
        # window.native is the Windows Forms window; other platforms have no Handle.
        # This runs on a pywebview event thread: cosmetic, so it must never raise.
        # Called at start, when Windows switches theme, and when the setting changes.
        try:
            handle = getattr(getattr(window, "native", None), "Handle", None)
            if handle is not None:
                theme = resolved_theme(saved_settings().theme)
                set_caption_colour(
                    int(handle.ToInt32()),
                    window_background(theme=theme, palette=saved_settings().palette),
                    dark=theme == "dark",
                )
        except Exception as exc:  # the window works without it
            print(f"Could not colour the title bar: {exc}")

    def watch_closing() -> None:
        """Route closing through Lifecycle, knowing why the window is closing.

        Hooked on the Windows Forms window itself, because only it says
        whether a person closed the window or Windows is shutting down.
        """
        form = getattr(window, "native", None)
        if form is None or not hasattr(form, "FormClosing"):
            window.events.closing += lambda: lifecycle.close_requested()
            return

        def on_form_closing(sender: object, args: object) -> None:
            nonlocal minimized
            by_user = str(getattr(args, "CloseReason", "")) == "UserClosing"
            minimized = str(getattr(sender, "WindowState", "")) == "Minimized"
            if not lifecycle.close_requested(by_user=by_user):
                args.Cancel = True  # type: ignore[attr-defined]

        form.FormClosing += on_form_closing

    def on_started() -> None:
        """Runs once the window exists (on its own thread)."""
        guard.listen(lifecycle.show)
        if background:
            if tray.available:
                lifecycle.start_hidden()
            else:
                # No icon to find it by: a hidden palm-lab could not be opened
                # or quit, so show the window after all.
                lifecycle.show()
            result = api.start()
            if not result["ok"]:
                tray.notify("palm-lab could not start tracking", str(result["error"]))

    window.events.shown += colour_title_bar
    window.events.shown += watch_closing
    tray.start()
    overlay.start()
    stop_updates = threading.Event()
    updates.run_in_background(stop_updates)
    try:
        webview.start(on_started, debug=debug, icon=str(icon_path()))
    finally:
        stop_updates.set()
        overlay.stop()
        tray.stop()
        engine.stop()
    return 0
