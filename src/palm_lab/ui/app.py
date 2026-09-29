"""Open the palm-lab window."""

from collections.abc import Callable
from pathlib import Path

from palm_lab.config import bindings_path, ensure_bindings_file, icon_path, ui_static_dir
from palm_lab.custom_gestures import gestures_path
from palm_lab.settings import settings_path
from palm_lab.windows import apps_use_light_theme, set_app_id, set_caption_colour

WINDOW_TITLE = "palm-lab"
WINDOW_SIZE = (1200, 800)
WINDOW_MIN_SIZE = (960, 640)

# Must match --mica in app.css. The window frame, the title bar and the page
# background are one colour, so the title bar reads as part of the app.
LIGHT_BACKGROUND = "#F3F3F3"
DARK_BACKGROUND = "#202020"


def window_background(read_setting: Callable[[], int | None] = apps_use_light_theme) -> str:
    """The page follows the Windows theme through CSS; the window frame must too."""
    return DARK_BACKGROUND if read_setting() == 0 else LIGHT_BACKGROUND


def load_page(static_dir: Path) -> str:
    """Build one self-contained HTML page with the CSS and JS inlined.

    Inlining avoids serving files or resolving URLs, which behaves differently
    between running from source and running from a PyInstaller build.
    """
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    css = (static_dir / "app.css").read_text(encoding="utf-8")
    js = (static_dir / "app.js").read_text(encoding="utf-8")
    style_tag = '<link rel="stylesheet" href="app.css">'
    script_tag = '<script src="app.js"></script>'
    if style_tag not in html or script_tag not in html:
        raise ValueError("index.html must reference app.css and app.js exactly once")
    return html.replace(style_tag, f"<style>\n{css}\n</style>").replace(
        script_tag, f"<script>\n{js}\n</script>"
    )


def run_ui(debug: bool = False) -> int:
    """Create the engine and bridge, open the window, and block until closed."""
    import webview

    from palm_lab.camera import MediaPipeDetector, open_camera, probe_cameras, render_preview
    from palm_lab.engine import TrackingEngine
    from palm_lab.ui.api import Api

    ensure_bindings_file()
    set_app_id()
    engine = TrackingEngine(
        open_camera=open_camera,
        make_detector=MediaPipeDetector,
        render_preview=render_preview,
    )
    api = Api(
        engine,
        bindings_file=bindings_path(),
        settings_file=settings_path(),
        gestures_file=gestures_path(),
        probe_cameras=probe_cameras,
        # Called when Windows switches theme; colour_title_bar is defined below.
        on_theme_change=lambda: colour_title_bar(),
    )
    window = webview.create_window(
        WINDOW_TITLE,
        html=load_page(ui_static_dir()),
        js_api=api,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
        background_color=window_background(),
    )

    def colour_title_bar() -> None:
        # window.native is the Windows Forms window; other platforms have no Handle.
        # This runs on a pywebview event thread: cosmetic, so it must never raise.
        try:
            handle = getattr(getattr(window, "native", None), "Handle", None)
            if handle is not None:
                set_caption_colour(int(handle.ToInt32()), window_background())
        except Exception as exc:  # the window works without it
            print(f"Could not colour the title bar: {exc}")

    if window is not None:
        window.events.shown += colour_title_bar
    try:
        webview.start(debug=debug, icon=str(icon_path()))
    finally:
        engine.stop()
    return 0
