"""Tests for the update check: reading GitHub's answer, deciding when to ask, remembering."""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from palm_lab import updates
from palm_lab.updates import (
    CHECK_EVERY,
    LATEST_RELEASE_API,
    Release,
    UpdateChecker,
    UpdateCheckError,
    fetch_latest,
    is_newer,
    load_state,
    parse_version,
    release_from_json,
)

PAGE = "https://github.com/GpapoutsisPap/palm-lab/releases/tag/v0.4.0"
INSTALLER = (
    "https://github.com/GpapoutsisPap/palm-lab/releases/download/v0.4.0/palm-lab-setup-0.4.0.exe"
)


def github_answer(**changes: object) -> dict[str, object]:
    """The parts of GitHub's /releases/latest answer palm-lab reads."""
    answer: dict[str, object] = {
        "tag_name": "v0.4.0",
        "html_url": PAGE,
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": "palm-lab-0.4.0.zip", "browser_download_url": INSTALLER + ".zip"},
            {"name": "palm-lab-setup-0.4.0.exe", "browser_download_url": INSTALLER},
        ],
    }
    answer.update(changes)
    return answer


NEW = Release(version="0.4.0", page_url=PAGE, installer_url=INSTALLER)


# Versions ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "version"),
    [("v0.4.0", (0, 4, 0)), ("1.10.2", (1, 10, 2)), ("0.4.0-beta.1", None), ("v1.2", None)],
)
def test_versions_are_read_as_numbers(text: str, version: tuple[int, int, int] | None) -> None:
    assert parse_version(text) == version


def test_newer_compares_numbers_not_text() -> None:
    assert is_newer("0.10.0", "0.9.9")  # as text, "0.10.0" < "0.9.9"
    assert not is_newer("0.3.0", "0.3.0")
    assert not is_newer("0.2.1", "0.3.0")
    assert not is_newer("nonsense", "0.3.0")


# GitHub's answer ----------------------------------------------------------------------


def test_a_release_gives_its_version_page_and_installer() -> None:
    assert release_from_json(github_answer()) == NEW


@pytest.mark.parametrize(
    "changes",
    [
        {"draft": True},
        {"prerelease": True},
        {"tag_name": "nightly"},
        {"html_url": "https://evil.example/palm-lab/releases/tag/v0.4.0"},
        {"html_url": "https://github.com/someone-else/palm-lab/releases/tag/v0.4.0"},
    ],
)
def test_only_a_published_release_of_this_project_counts(changes: dict[str, object]) -> None:
    assert release_from_json(github_answer(**changes)) is None


def test_an_installer_elsewhere_is_ignored_but_the_release_still_counts() -> None:
    answer = github_answer(
        assets=[
            {"name": "palm-lab-setup-0.4.0.exe", "browser_download_url": "https://x.example/a.exe"}
        ]
    )
    assert release_from_json(answer) == Release("0.4.0", PAGE, None)


def test_fetch_asks_the_latest_release_api() -> None:
    asked: list[str] = []

    def get(url: str, timeout: float) -> bytes:
        asked.append(url)
        return json.dumps(github_answer()).encode()

    assert fetch_latest(get) == NEW
    assert asked == [LATEST_RELEASE_API]
    assert LATEST_RELEASE_API == (
        "https://api.github.com/repos/GpapoutsisPap/palm-lab/releases/latest"
    )


def test_no_release_yet_is_not_an_error() -> None:
    assert fetch_latest(lambda url, timeout: None) is None


def test_a_garbled_answer_is_an_error() -> None:
    with pytest.raises(UpdateCheckError, match="couldn't be read"):
        fetch_latest(lambda url, timeout: b"<html>")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (urllib.error.HTTPError(LATEST_RELEASE_API, 403, "rate limited", {}, None), "wait"),  # type: ignore[arg-type]
        (urllib.error.HTTPError(LATEST_RELEASE_API, 500, "oops", {}, None), "error \\(500\\)"),  # type: ignore[arg-type]
        (urllib.error.URLError("no network"), "are you online"),
        (TimeoutError(), "are you online"),
    ],
)
def test_network_problems_become_plain_words(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    def fail(request: object, timeout: float) -> None:
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(UpdateCheckError, match=message):
        updates.http_get(LATEST_RELEASE_API, 1.0)


def test_a_missing_release_page_is_a_404_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_found(request: object, timeout: float) -> None:
        raise urllib.error.HTTPError(LATEST_RELEASE_API, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", not_found)
    assert updates.http_get(LATEST_RELEASE_API, 1.0) is None


def test_the_request_says_who_is_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    class Answer:
        def __enter__(self) -> "Answer":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            return b"{}"

    def urlopen(request: urllib.request.Request, timeout: float) -> Answer:
        seen.update(request.header_items())
        return Answer()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    updates.http_get(LATEST_RELEASE_API, 1.0)
    assert seen["User-agent"].startswith("palm-lab/")
    assert seen["Accept"] == "application/vnd.github+json"


# When to ask, and remembering ---------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def checker(
    tmp_path: Path, *, answer: Release | None = NEW, enabled: bool = True, current: str = "0.3.0"
) -> tuple[UpdateChecker, Clock, list[Release], list[int]]:
    clock = Clock()
    found: list[Release] = []
    asked: list[int] = []

    def fetch() -> Release | None:
        asked.append(1)
        return answer

    made = UpdateChecker(
        enabled=lambda: enabled,
        state_file=tmp_path / "updates.json",
        current=current,
        fetch=fetch,
        clock=clock,
        on_found=found.append,
    )
    return made, clock, found, asked


def test_a_newer_release_is_offered_and_announced_once(tmp_path: Path) -> None:
    check, clock, found, _ = checker(tmp_path)
    status = check.check()
    assert status.available == NEW and not status.dismissed
    clock.now += CHECK_EVERY
    check.check()
    assert found == [NEW]  # the tray says so once, not every day


def test_the_same_version_is_not_offered(tmp_path: Path) -> None:
    check, *_ = checker(tmp_path, current="0.4.0")
    assert check.check().available is None


def test_it_asks_at_most_once_a_day(tmp_path: Path) -> None:
    check, clock, _, asked = checker(tmp_path)
    assert check.due()
    check.check_if_due()
    check.check_if_due()
    assert len(asked) == 1
    clock.now += CHECK_EVERY - 1
    assert not check.due()
    clock.now += 1
    assert check.due()


def test_a_clock_that_went_back_doesnt_stop_checks(tmp_path: Path) -> None:
    check, clock, *_ = checker(tmp_path)
    check.check()
    clock.now -= 3600
    assert check.due()


def test_switched_off_it_never_asks_and_offers_nothing(tmp_path: Path) -> None:
    check, _, _, asked = checker(tmp_path, enabled=False)
    check.check_if_due()
    assert asked == []
    assert check.status().available is None


def test_a_failed_background_check_is_quiet_and_tried_again(tmp_path: Path) -> None:
    def offline() -> Release | None:
        raise UpdateCheckError("couldn't reach GitHub (are you online?)")

    check = UpdateChecker(enabled=lambda: True, state_file=tmp_path / "u.json", fetch=offline)
    check.check_if_due()  # no exception
    assert check.status().error == "couldn't reach GitHub (are you online?)"
    assert check.due()  # nothing was learnt, so it's still due


def test_the_answer_survives_a_restart(tmp_path: Path) -> None:
    first, clock, *_ = checker(tmp_path)
    first.check()
    first.dismiss("0.4.0")
    again, _, _, asked = checker(tmp_path)
    again._clock = clock  # the same moment, after restarting
    status = again.status()
    assert status.available == NEW and status.dismissed
    assert not again.due() and asked == []


def test_a_newer_version_shows_the_bar_again_after_dismissing(tmp_path: Path) -> None:
    check, *_ = checker(tmp_path)
    check.check()
    check.dismiss("0.4.0")
    check._fetch = lambda: Release("0.5.0", PAGE.replace("0.4.0", "0.5.0"), None)
    assert check.check().dismissed is False


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"checked_at": "soon"}',
        '{"latest": {"version": "0.9.0", "page_url": "https://evil.example/"}}',
    ],
)
def test_a_damaged_or_tampered_file_counts_as_never_checked(tmp_path: Path, text: str) -> None:
    path = tmp_path / "updates.json"
    path.write_text(text, encoding="utf-8")
    state = load_state(path)
    assert state.latest is None


def test_the_background_loop_stops_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(updates, "FIRST_CHECK_DELAY", 0.0)
    check, _, _, asked = checker(tmp_path)
    stop = threading.Event()
    thread = check.run_in_background(stop)
    for _ in range(100):
        if asked:
            break
        thread.join(0.01)
    stop.set()
    thread.join(2)
    assert asked == [1] and not thread.is_alive()
