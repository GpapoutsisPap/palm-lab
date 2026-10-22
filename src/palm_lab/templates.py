"""Starter templates: ready-made shortcuts to begin a gesture from.

Picking one in the editor fills the gesture with these pieces, which the
person then changes to suit them (their own apps, websites, words). Each one
is the same shape as a [[binding]] in bindings.toml, so a test checks every
template with the same rules a saved binding goes through.

To add one, add an entry here: a short name, a category, one line saying
what it does, and its pieces in order.
"""

from typing import TypedDict


class TemplateAction(TypedDict):
    type: str
    target: str


class Template(TypedDict):
    name: str
    category: str
    description: str
    action: list[TemplateAction]


def step(type_: str, target: str) -> TemplateAction:
    return {"type": type_, "target": target}


CATEGORIES = ("Everyday", "Work", "Focus")

TEMPLATES: list[Template] = [
    {
        "name": "Play or pause",
        "category": "Everyday",
        "description": "Start or stop whatever is playing.",
        "action": [step("hotkey", "media_play_pause")],
    },
    {
        "name": "Next track",
        "category": "Everyday",
        "description": "Skip to the next song or video.",
        "action": [step("hotkey", "media_next")],
    },
    {
        "name": "Quiet down",
        "category": "Everyday",
        "description": "Turn the sound down to 20%.",
        "action": [step("volume", "20")],
    },
    {
        "name": "Show the desktop",
        "category": "Everyday",
        "description": "Minimise everything; do it again to bring it all back.",
        "action": [step("system", "show_desktop")],
    },
    {
        "name": "Screenshot",
        "category": "Everyday",
        "description": "Open Windows' snipping tool to grab part of the screen.",
        "action": [step("system", "screenshot")],
    },
    {
        "name": "Start my day",
        "category": "Work",
        "description": "Open your documents, your calendar and some music.",
        "action": [
            step("open_path", "documents"),
            step("open_url", "https://calendar.google.com"),
            step("wait", "2"),
            step("launch", "spotify"),
        ],
    },
    {
        "name": "Quick note",
        "category": "Work",
        "description": "Open Notepad and start a note.",
        "action": [step("launch", "notepad"), step("wait", "1"), step("type_text", "Note: ")],
    },
    {
        "name": "Step away",
        "category": "Work",
        "description": "Mute your microphone and lock the PC.",
        "action": [step("volume", "mic_mute"), step("system", "lock")],
    },
    {
        "name": "Mic off",
        "category": "Work",
        "description": "Mute your microphone in every app at once.",
        "action": [step("volume", "mic_mute")],
    },
    {
        "name": "Focus mode",
        "category": "Focus",
        "description": "Open Focus settings and turn the sound down.",
        "action": [step("settings", "quiethours"), step("volume", "30")],
    },
]
