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
