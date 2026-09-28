"""Tests for the command line interface."""

from pathlib import Path

import pytest

from palm_lab import cli
from palm_lab.actions.errors import InvalidBindingError


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point palm-lab at a throwaway config directory for one test."""
    target = tmp_path / "palm-lab"
    monkeypatch.setenv("PALM_LAB_CONFIG_DIR", str(target))
    return target


def test_bare_invocation_defaults_to_run() -> None:
    """`palm-lab` with no arguments should start watching, not print help."""
    args = cli.build_parser().parse_args([])
    assert args.command == "run"
    assert args.camera == 0


def test_run_accepts_a_camera_index() -> None:
    """A non-default camera can be selected."""
    args = cli.build_parser().parse_args(["run", "--camera", "2"])
    assert args.command == "run"
    assert args.camera == 2


def test_capture_requires_a_gesture_name() -> None:
    """Fixtures are labelled, so the name is not optional."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["capture"])


def test_capture_parses_its_arguments() -> None:
    """Gesture label and camera index both reach the handler."""
    args = cli.build_parser().parse_args(["capture", "peace", "--camera", "1"])
    assert args.command == "capture"
    assert args.gesture == "peace"
    assert args.camera == 1


@pytest.mark.parametrize("command", ["run", "capture", "config", "doctor"])
def test_every_subcommand_maps_to_a_handler(command: str) -> None:
    """A subcommand with no handler would silently print help instead."""
    assert command in cli.HANDLERS


def test_config_reports_the_location(config_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`palm-lab config` prints where things live and what is configured."""
    assert cli.main(["config"]) == 0
    out = capsys.readouterr().out
    assert str(config_home) in out
    assert "binding(s)" in out


def test_config_creates_the_file_when_absent(config_home: Path) -> None:
    """Asking where the config is also gives you one to edit."""
    assert cli.main(["config"]) == 0
    assert (config_home / "bindings.toml").exists()


def test_config_reports_a_broken_file(
    config_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed config exits non-zero and explains the problem."""
    config_home.mkdir(parents=True)
    (config_home / "bindings.toml").write_text("[[binding]\n", encoding="utf-8")
    assert cli.main(["config"]) == 1
    assert "problem" in capsys.readouterr().out


def test_doctor_fails_when_the_model_is_missing(
    config_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Doctor exits non-zero and prints the download command."""
    monkeypatch.setattr(cli, "MODEL_PATH", tmp_path / "absent.task")
    assert cli.main(["doctor"]) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert cli.MODEL_URL in out


def test_doctor_passes_when_everything_is_present(
    config_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With a model and a valid config, doctor reports all clear."""
    model = tmp_path / "hand_landmarker.task"
    model.write_bytes(b"x" * 1024)
    monkeypatch.setattr(cli, "MODEL_PATH", model)
    cli.main(["config"])
    assert cli.main(["doctor"]) == 0
    assert "All good." in capsys.readouterr().out


def test_version_flag_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    """--version prints and exits zero rather than running a command."""
    with pytest.raises(SystemExit) as caught:
        cli.main(["--version"])
    assert caught.value.code == 0
    assert "palm-lab" in capsys.readouterr().out


def test_unknown_subcommand_is_rejected() -> None:
    """argparse should reject a command we do not define."""
    with pytest.raises(SystemExit):
        cli.main(["frobnicate"])


def test_action_errors_are_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A configuration problem should print a message, not a traceback."""

    def explode(_: object) -> int:
        raise InvalidBindingError("Binding 1: 'gesture' must be a non-empty string")

    monkeypatch.setitem(cli.HANDLERS, "config", explode)
    assert cli.main(["config"]) == 1
    assert "gesture" in capsys.readouterr().err


def test_interrupt_exits_quietly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ctrl+C is a normal way to stop watching, not a crash."""

    def interrupt(_: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setitem(cli.HANDLERS, "config", interrupt)
    assert cli.main(["config"]) == 130
    assert "Stopped." in capsys.readouterr().out


def test_missing_handler_prints_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A command with no handler falls back to help rather than crashing."""
    monkeypatch.delitem(cli.HANDLERS, "config")
    assert cli.main(["config"]) == 2
    assert "usage:" in capsys.readouterr().out
