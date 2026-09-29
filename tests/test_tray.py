"""Tests for the notification-area icon, with pystray faked out."""

import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from palm_lab.ui.tray import TOOLTIP, TOOLTIP_TRACKING, Tray


class FakeMenuItem:
    def __init__(
        self,
        text: str,
        action: Callable[[], None],
        *,
        default: bool = False,
        checked: Callable[[Any], bool] | None = None,
        visible: Callable[[Any], bool] | bool = True,
    ) -> None:
        self.text = text
        self.action = action
        self.default = default
        self.checked = checked
        self.visible = visible


class FakeMenu:
    SEPARATOR = "separator"

    def __init__(self, *items: Any) -> None:
        self.items = items


class FakeIcon:
    instances: list["FakeIcon"] = []

    def __init__(self, name: str, image: object, title: str, menu: FakeMenu) -> None:
        self.name = name
        self.image = image
        self.title = title
        self.menu = menu
        self.visible = True
        self.running = threading.Event()
        self.stopped = False
        self.menu_updates = 0
        self.notes: list[tuple[str, str]] = []
        FakeIcon.instances.append(self)

    def run(self) -> None:
        self.running.set()

    def update_menu(self) -> None:
        self.menu_updates += 1

    def notify(self, message: str, title: str) -> None:
        self.notes.append((title, message))

    def stop(self) -> None:
        self.stopped = True


FAKE_PYSTRAY = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)


class App:
    """What the tray drives: records calls, and has a tracking switch."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.tracking = False
        self.paused = False

    def tray(self, backend: Callable[[], Any] = lambda: FAKE_PYSTRAY) -> Tray:
        return Tray(
            icon_file=Path("palm-lab.ico"),
            on_open=lambda: self.calls.append("open"),
            on_toggle_tracking=lambda: self.calls.append("toggle"),
            on_quit=lambda: self.calls.append("quit"),
            is_tracking=lambda: self.tracking,
            on_pause=lambda minutes: self.calls.append(f"pause {minutes}"),
            on_resume=lambda: self.calls.append("resume"),
            is_paused=lambda: self.paused,
            backend=backend,
            image=lambda path: f"image of {path.name}",
            sleep=lambda seconds: None,
        )


@pytest.fixture
def app() -> App:
    FakeIcon.instances.clear()
    return App()


def item(icon: FakeIcon, text: str) -> FakeMenuItem:
    found = [i for i in icon.menu.items if isinstance(i, FakeMenuItem) and i.text == text]
    return found[0]


def shown(menu_item: FakeMenuItem) -> bool:
    visible = menu_item.visible
    return visible(menu_item) if callable(visible) else visible


def started(app: App) -> tuple[Tray, FakeIcon]:
    tray = app.tray()
    tray.start()
    icon = FakeIcon.instances[-1]
    assert icon.running.wait(2)
    return tray, icon


def test_the_icon_shows_the_app_icon_and_a_menu(app: App) -> None:
    tray, icon = started(app)
    assert tray.available
    assert icon.image == "image of palm-lab.ico"
    assert icon.title == TOOLTIP
    texts = [item if isinstance(item, str) else item.text for item in icon.menu.items]
    assert texts == [
        "Open palm-lab",
        "Tracking",
        "Pause for 15 minutes",
        "Pause for 1 hour",
        "Resume now",
        "separator",
        "Quit palm-lab",
    ]
    tray.stop()


def test_clicking_the_icon_opens_the_window(app: App) -> None:
    """The default item is what a click on the icon does."""
    tray, icon = started(app)
    default = [item for item in icon.menu.items if getattr(item, "default", False)]
    assert [item.text for item in default] == ["Open palm-lab"]
    default[0].action()
    assert app.calls == ["open"]
    tray.stop()


def test_menu_items_call_through(app: App) -> None:
    tray, icon = started(app)
    for text in ("Tracking", "Pause for 15 minutes", "Pause for 1 hour", "Resume now"):
        item(icon, text).action()
    item(icon, "Quit palm-lab").action()
    assert app.calls == ["toggle", "pause 15", "pause 60", "resume", "quit"]
    tray.stop()


def test_the_tracking_tick_follows_the_engine(app: App) -> None:
    tray, icon = started(app)
    tracking = item(icon, "Tracking")
    assert tracking.checked is not None
    assert tracking.checked(tracking) is False
    app.tracking = True
    assert tracking.checked(tracking) is True
    tray.stop()


def test_refresh_updates_the_tooltip_only_when_tracking_changes(app: App) -> None:
    tray, icon = started(app)
    tray.refresh()
    updates = icon.menu_updates
    tray.refresh()
    assert icon.menu_updates == updates
    app.tracking = True
    tray.refresh()
    assert icon.title == TOOLTIP_TRACKING
    assert icon.menu_updates == updates + 1
    tray.stop()


def test_notifications_go_through_the_icon(app: App) -> None:
    tray, icon = started(app)
    tray.notify("Title", "Message")
    assert icon.notes == [("Title", "Message")]
    tray.stop()


def test_stop_removes_the_icon(app: App) -> None:
    tray, icon = started(app)
    tray.stop()
    assert icon.stopped
    assert not tray.available
    tray.notify("ignored", "after stopping")
    assert icon.notes == []


def test_a_missing_tray_library_leaves_palm_lab_working(
    app: App, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> Any:
        raise ImportError("No module named 'pystray'")

    tray = app.tray(backend=broken)
    tray.start()
    assert not tray.available
    tray.notify("nothing", "happens")
    tray.refresh()
    tray.stop()
    assert "notification-area icon" in capsys.readouterr().out


def test_pause_items_show_while_tracking_and_resume_while_paused(app: App) -> None:
    tray, icon = started(app)
    pause, resume = item(icon, "Pause for 1 hour"), item(icon, "Resume now")
    assert not shown(pause) and not shown(resume)
    app.tracking = True
    assert shown(pause) and not shown(resume)
    app.tracking, app.paused = False, True
    assert not shown(pause) and shown(resume)
    tray.refresh()
    assert icon.title == "palm-lab: paused"
    tray.stop()
