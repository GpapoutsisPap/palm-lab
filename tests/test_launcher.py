"""Tests for the packaged executable's entry point."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / "packaging" / "launcher.py"


@pytest.fixture
def launcher() -> ModuleType:
    """Load packaging/launcher.py, which is not part of the installed package."""
    spec = importlib.util.spec_from_file_location("palm_lab_launcher", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def double_clicked(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Simulate a frozen app started with no arguments, recording any pause."""
    prompts: list[str] = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["palm-lab.exe"])
    monkeypatch.setattr("builtins.input", prompts.append)
    return prompts


def test_success_closes_without_pausing(
    launcher: ModuleType, double_clicked: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean exit, such as pressing q, should not leave a window waiting."""
    monkeypatch.setattr(launcher, "main", lambda: 0)
    assert launcher.run() == 0
    assert double_clicked == []


def test_failure_pauses_after_a_double_click(
    launcher: ModuleType, double_clicked: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An error exit keeps the window open so the message can be read."""
    monkeypatch.setattr(launcher, "main", lambda: 1)
    assert launcher.run() == 1
    assert len(double_clicked) == 1


def test_crash_is_printed_and_reported(
    launcher: ModuleType,
    double_clicked: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unexpected exception shows its traceback instead of vanishing."""

    def crash() -> int:
        raise FileNotFoundError("Hand landmarker model not found")

    monkeypatch.setattr(launcher, "main", crash)
    assert launcher.run() == 1
    assert "Hand landmarker model not found" in capsys.readouterr().err
    assert len(double_clicked) == 1


def test_no_pause_when_run_from_a_terminal(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From a terminal the output stays visible, so waiting would just annoy."""
    prompts: list[str] = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["palm-lab.exe", "doctor"])
    monkeypatch.setattr("builtins.input", prompts.append)
    monkeypatch.setattr(launcher, "main", lambda: 1)
    assert launcher.run() == 1
    assert prompts == []


@pytest.fixture
def windowed(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> list[tuple[str, str]]:
    """Simulate palm-lab.exe, which has no console, recording any dialog."""
    dialogs: list[tuple[str, str]] = []
    monkeypatch.setenv("PALM_LAB_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "_has_console", lambda: False)
    monkeypatch.setattr(launcher, "show_error", lambda title, text: dialogs.append((title, text)))
    # run() swaps the streams for the log file; put the real ones back afterwards.
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    return dialogs


def test_windowed_crash_is_logged_and_shown_in_a_dialog(
    launcher: ModuleType,
    windowed: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With no console, the traceback goes to a log file the dialog points at."""

    def crash() -> int:
        raise FileNotFoundError("Hand landmarker model not found")

    monkeypatch.setattr(launcher, "main", crash)
    assert launcher.run() == 1
    sys.stderr.flush()
    log = tmp_path / "logs" / "palm-lab.log"
    assert "Hand landmarker model not found" in log.read_text(encoding="utf-8")
    assert len(windowed) == 1 and str(log) in windowed[0][1]


def test_windowed_success_is_silent(
    launcher: ModuleType, windowed: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "main", lambda: 0)
    assert launcher.run() == 0
    assert windowed == []


def test_a_large_log_starts_afresh(
    launcher: ModuleType,
    windowed: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The log never grows without limit."""
    log = tmp_path / "logs" / "palm-lab.log"
    log.parent.mkdir()
    log.write_text("x" * (launcher.LOG_LIMIT_BYTES + 1), encoding="utf-8")
    monkeypatch.setattr(launcher, "main", lambda: 0)
    launcher.run()
    assert log.stat().st_size < 200
