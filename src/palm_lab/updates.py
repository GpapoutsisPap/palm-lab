"""Tell people when a newer palm-lab is out.

Once a day, palm-lab asks GitHub for the project's latest release
(GET /repos/OWNER/REPO/releases/latest, which skips drafts and pre-releases)
and compares its tag with this copy's version. If it's newer, the window
shows a bar with "What's new" and "Download" until it's dismissed for that
version. Nothing is downloaded or installed by itself.

What travels: an ordinary HTTPS request to api.github.com, carrying palm-lab's
version in the User-Agent, as GitHub asks. Nothing about the person, their
gestures or their PC. GitHub sees the request like any page visit (so it
sees the IP address). Settings > Check for updates turns it off.

The answer is remembered in updates.json in the config folder: when we last
asked, what the latest release was, and which version was dismissed. So the
bar survives a restart without asking again, and a failed check (offline,
GitHub down, or its limit of 60 unauthenticated requests an hour) just waits
for the next start or the next hour.
"""

import contextlib
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from palm_lab.config import PROJECT_URL, config_dir
from palm_lab.version import __version__

REPOSITORY = PROJECT_URL.removeprefix("https://github.com/")
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"{PROJECT_URL}/releases/"
DOWNLOADS = f"{PROJECT_URL}/releases/download/"
INSTALLER_PREFIX, INSTALLER_SUFFIX = "palm-lab-setup-", ".exe"

STATE_FILENAME = "updates.json"
CHECK_EVERY = 24 * 60 * 60  # seconds between automatic checks
FIRST_CHECK_DELAY = 20.0  # after start, so it never slows opening the window
RETRY_EVERY = 60 * 60.0  # how often the background loop looks whether a check is due
TIMEOUT = 10.0

Version = tuple[int, int, int]
Fetcher = Callable[[str, float], bytes | None]


class UpdateCheckError(Exception):
    """GitHub couldn't be asked, or gave an answer that makes no sense."""


def parse_version(text: str) -> Version | None:
    """ "v0.4.0" or "0.4.0" as (0, 4, 0). Anything else (like "0.4.0-beta.1") is None."""
    parts = text.strip().removeprefix("v").split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def is_newer(candidate: str, current: str) -> bool:
    """Whether candidate is a later version than current. Unreadable versions never are."""
    new, old = parse_version(candidate), parse_version(current)
    return new is not None and old is not None and new > old


@dataclass(frozen=True)
class Release:
    version: str  # "0.4.0", without the v
    page_url: str  # the release's page on GitHub, with its notes
    installer_url: str | None  # the installer to download, if the release has one


def checked_release(tag: object, page: object, installer: object = None) -> Release | None:
    """A release, if its version reads and its links point into this project on GitHub.

    The window opens these links, so a strange answer (or a tampered
    updates.json) must never open a strange page.
    """
    if not isinstance(tag, str) or parse_version(tag) is None:
        return None
    if not isinstance(page, str) or not page.startswith(RELEASES_PAGE):
        return None
    if not (isinstance(installer, str) and installer.startswith(DOWNLOADS)):
        installer = None
    return Release(version=tag.strip().removeprefix("v"), page_url=page, installer_url=installer)


def release_from_json(data: object) -> Release | None:
    """Read GitHub's answer. Only a published, normal release of this project counts."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    installer = None
    assets = data.get("assets")
    for asset in assets if isinstance(assets, list) else []:
        name = asset.get("name") if isinstance(asset, dict) else None
        if (
            isinstance(name, str)
            and name.startswith(INSTALLER_PREFIX)
            and name.endswith(INSTALLER_SUFFIX)
        ):
            installer = asset.get("browser_download_url")
            break
    return checked_release(data.get("tag_name"), data.get("html_url"), installer)


def http_get(url: str, timeout: float) -> bytes | None:
    """GET url and return the body; None for 404 (no release published yet)."""
    request = urllib.request.Request(  # noqa: S310 - always an https:// URL of our own
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"palm-lab/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body: bytes = response.read(1_000_000)
            return body
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (403, 429):
            raise UpdateCheckError("GitHub asked palm-lab to wait; try again later") from exc
        raise UpdateCheckError(f"GitHub answered with an error ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError("couldn't reach GitHub (are you online?)") from exc


def fetch_latest(get: Fetcher = http_get, timeout: float = TIMEOUT) -> Release | None:
    """The latest published release, or None if there is none to offer."""
    body = get(LATEST_RELEASE_API, timeout)
    if body is None:
        return None
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise UpdateCheckError("GitHub's answer couldn't be read") from exc
    return release_from_json(data)


# Remembering ------------------------------------------------------------------------


@dataclass
class UpdateState:
    checked_at: float | None = None  # wall-clock time of the last successful check
    latest: Release | None = None
    dismissed: str | None = None  # the version whose bar was closed


def state_path() -> Path:
    return config_dir() / STATE_FILENAME


def load_state(path: Path) -> UpdateState:
    """What we last learnt. A missing or damaged file just means "never checked"."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        latest = data.get("latest")
        checked_at = data.get("checked_at")
        dismissed = data.get("dismissed")
        return UpdateState(
            checked_at=float(checked_at) if checked_at is not None else None,
            latest=checked_release(
                latest.get("version"), latest.get("page_url"), latest.get("installer_url")
            )
            if isinstance(latest, dict)
            else None,
            dismissed=dismissed if isinstance(dismissed, str) else None,
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return UpdateState()


def save_state(state: UpdateState, path: Path) -> None:
    data = {
        "checked_at": state.checked_at,
        "latest": asdict(state.latest) if state.latest else None,
        "dismissed": state.dismissed,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


# Checking ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpdateStatus:
    """What the window shows about updates."""

    enabled: bool
    current: str
    checked_at: float | None
    available: Release | None  # a newer release, if there is one
    dismissed: bool  # its bar was closed (Settings still mentions it)
    error: str | None = None  # why the last check asked for in the window failed


class UpdateChecker:
    """Decides when to ask GitHub, and remembers the answer. Safe to use from any thread."""

    def __init__(
        self,
        *,
        enabled: Callable[[], bool],
        state_file: Path | None = None,
        current: str = __version__,
        fetch: Callable[[], Release | None] = fetch_latest,
        clock: Callable[[], float] = time.time,
        on_found: Callable[[Release], None] = lambda release: None,
    ) -> None:
        self._enabled = enabled
        self._state_file = state_file or state_path()
        self._current = current
        self._fetch = fetch
        self._clock = clock
        self._on_found = on_found
        self._lock = threading.Lock()
        self._state = load_state(self._state_file)
        self._error: str | None = None

    def _available(self) -> Release | None:
        latest = self._state.latest
        return latest if latest and is_newer(latest.version, self._current) else None

    def status(self) -> UpdateStatus:
        with self._lock:
            available = self._available()
            return UpdateStatus(
                enabled=self._enabled(),
                current=self._current,
                checked_at=self._state.checked_at,
                available=available if self._enabled() else None,
                dismissed=bool(available and self._state.dismissed == available.version),
                error=self._error,
            )

    def due(self) -> bool:
        """Switched on, and a day has passed since the last check (or the clock went back)."""
        if not self._enabled():
            return False
        with self._lock:
            last = self._state.checked_at
        now = self._clock()
        return last is None or now - last >= CHECK_EVERY or now < last

    def check(self) -> UpdateStatus:
        """Ask GitHub now. A failure is kept in status().error and raised again."""
        try:
            release = self._fetch()
        except UpdateCheckError as exc:
            with self._lock:
                self._error = str(exc)
            raise
        with self._lock:
            known = self._available()
            self._state.checked_at = self._clock()
            self._state.latest = release
            self._error = None
            found = self._available()
            with contextlib.suppress(OSError):  # remembered for this run; asked again next time
                save_state(self._state, self._state_file)
        if found is not None and (known is None or known.version != found.version):
            self._on_found(found)
        return self.status()

    def check_if_due(self) -> None:
        """The background check: quietly does nothing when not due or when it fails."""
        if self.due():
            with contextlib.suppress(UpdateCheckError):
                self.check()

    def dismiss(self, version: str) -> None:
        """Hide the bar for this version. A newer one shows it again."""
        with self._lock:
            self._state.dismissed = version
            with contextlib.suppress(OSError):
                save_state(self._state, self._state_file)

    def run_in_background(self, stop: threading.Event) -> threading.Thread:
        """Check soon after start, then look every hour whether a day has passed."""

        def loop() -> None:
            if stop.wait(FIRST_CHECK_DELAY):
                return
            while True:
                self.check_if_due()
                if stop.wait(RETRY_EVERY):
                    return

        thread = threading.Thread(target=loop, name="palm-lab-updates", daemon=True)
        thread.start()
        return thread
