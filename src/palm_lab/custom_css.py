"""The user's own CSS, restyling the palm-lab window.

It lives in custom.css next to palm-lab's other files, so it can be written
in the window's Settings or in any editor. The page applies it as the text of
a <style> element (never pasted into the HTML), so a stylesheet shared by
someone else can change how palm-lab looks but cannot run code.
"""

from pathlib import Path

from palm_lab.config import config_dir

CUSTOM_CSS_FILENAME = "custom.css"
# Far more than any theme needs; stops a pasted-in mistake from bogging down the page.
MAX_CUSTOM_CSS_BYTES = 256_000


class CustomCssError(ValueError):
    """Custom CSS that is too large to use."""


def custom_css_path() -> Path:
    return config_dir() / CUSTOM_CSS_FILENAME


def load_custom_css(path: Path | None = None) -> str:
    """The saved CSS, or "" before any has been written."""
    path = path or custom_css_path()
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if len(text.encode("utf-8")) > MAX_CUSTOM_CSS_BYTES:
        raise CustomCssError(
            f"{path.name} is larger than {MAX_CUSTOM_CSS_BYTES // 1000} KB, so it was not used."
        )
    return text


def save_custom_css(text: str, path: Path | None = None) -> Path:
    """Write the CSS atomically and return where it went."""
    if len(text.encode("utf-8")) > MAX_CUSTOM_CSS_BYTES:
        raise CustomCssError(f"Custom CSS can be at most {MAX_CUSTOM_CSS_BYTES // 1000} KB.")
    path = path or custom_css_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    temporary.replace(path)
    return path
