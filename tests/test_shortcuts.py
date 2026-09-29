"""Tests for desktop and Start menu shortcuts, with PowerShell faked out."""

import json
from pathlib import Path

import pytest

from palm_lab import cli
from palm_lab.shortcuts import (
    CREATE_SHORTCUT,
    FIND_FOLDERS,
    LaunchTarget,
    ShortcutError,
    Shortcuts,
    launch_target,
)


class FakePowerShell:
    """Answers the folder query and 'creates' links by writing empty files."""

    def __init__(self, root: Path) -> None:
        self.folders = {"desktop": root / "Desktop", "start_menu": root / "Start Menu" / "Programs"}
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, script: str, env: dict[str, str]) -> str:
        self.calls.append((script, env))
        if script == FIND_FOLDERS:
            return json.dumps({kind: str(path) for kind, path in self.folders.items()})
        assert script == CREATE_SHORTCUT
        Path(env["PALM_LINK"]).write_bytes(b"")
        return ""


TARGET = LaunchTarget(Path("C:/palm-lab/palm-lab.exe"), "", Path("C:/palm-lab"), Path("x.ico"))


@pytest.fixture
def powershell(tmp_path: Path) -> FakePowerShell:
    return FakePowerShell(tmp_path)


@pytest.fixture
def shortcuts(powershell: FakePowerShell) -> Shortcuts:
    return Shortcuts(powershell=powershell, target=lambda: TARGET, platform="win32")


def test_state_before_anything_is_made(shortcuts: Shortcuts) -> None:
    assert shortcuts.state() == {"supported": True, "desktop": False, "start_menu": False}


def test_create_passes_everything_through_the_environment(
    shortcuts: Shortcuts, powershell: FakePowerShell
) -> None:
    """Paths never appear inside the script, so no name can break its syntax."""
    link = shortcuts.create("desktop")
    assert link == powershell.folders["desktop"] / "palm-lab.lnk"
    assert link.exists()
    script, env = powershell.calls[-1]
    assert env["PALM_TARGET"] == str(TARGET.target)
    assert env["PALM_LINK"] == str(link)
    assert str(TARGET.target) not in script
    assert shortcuts.state()["desktop"] is True


def test_the_start_menu_folder_is_created_if_missing(
    shortcuts: Shortcuts, powershell: FakePowerShell
) -> None:
    shortcuts.set("start_menu", True)
    assert (powershell.folders["start_menu"] / "palm-lab.lnk").exists()


def test_remove_deletes_the_link_and_tolerates_absence(shortcuts: Shortcuts) -> None:
    shortcuts.set("desktop", True)
    shortcuts.set("desktop", False)
    assert shortcuts.state()["desktop"] is False
    shortcuts.remove("desktop")  # already gone: not an error


def test_folders_are_asked_for_once(shortcuts: Shortcuts, powershell: FakePowerShell) -> None:
    shortcuts.state()
    shortcuts.state()
    assert sum(1 for script, _ in powershell.calls if script == FIND_FOLDERS) == 1


def test_unknown_kind_is_refused(shortcuts: Shortcuts) -> None:
    with pytest.raises(ShortcutError, match="Unknown shortcut"):
        shortcuts.create("taskbar")


def test_a_link_windows_did_not_write_is_an_error(tmp_path: Path) -> None:
    fake = FakePowerShell(tmp_path)

    def silent(script: str, env: dict[str, str]) -> str:
        return fake(script, env) if script == FIND_FOLDERS else ""

    shortcuts = Shortcuts(powershell=silent, target=lambda: TARGET, platform="win32")
    with pytest.raises(ShortcutError, match="did not create"):
        shortcuts.create("desktop")


def test_garbled_folder_answer_is_an_error() -> None:
    shortcuts = Shortcuts(
        powershell=lambda s, e: "not json", target=lambda: TARGET, platform="win32"
    )
    with pytest.raises(ShortcutError, match="where the Desktop is"):
        shortcuts.folders()
    assert shortcuts.state()["supported"] is False


def test_other_platforms_report_unsupported() -> None:
    shortcuts = Shortcuts(powershell=lambda s, e: "", target=lambda: TARGET, platform="linux")
    assert shortcuts.state() == {"supported": False, "desktop": False, "start_menu": False}
    with pytest.raises(ShortcutError, match="only be made on Windows"):
        shortcuts.create("desktop")


def test_from_source_the_shortcut_runs_the_module() -> None:
    target = launch_target()
    assert target.arguments == "-m palm_lab"
    assert target.icon.name == "palm-lab.ico" and target.icon.exists()


def test_cli_creates_the_desktop_shortcut(
    monkeypatch: pytest.MonkeyPatch, powershell: FakePowerShell, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "palm_lab.shortcuts.Shortcuts",
        lambda: Shortcuts(powershell=powershell, target=lambda: TARGET, platform="win32"),
    )
    assert cli.main(["shortcut"]) == 0
    assert (powershell.folders["desktop"] / "palm-lab.lnk").exists()
    assert not (powershell.folders["start_menu"] / "palm-lab.lnk").exists()
    assert "Created" in capsys.readouterr().out


def test_cli_reports_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "palm_lab.shortcuts.Shortcuts",
        lambda: Shortcuts(powershell=lambda s, e: "", target=lambda: TARGET, platform="linux"),
    )
    assert cli.main(["shortcut", "--start-menu"]) == 1
    assert "only be made on Windows" in capsys.readouterr().err


def test_an_installed_shortcut_always_opens_the_windowed_app(tmp_path: Path) -> None:
    """Made from palm-lab-cli.exe, the shortcut still points at palm-lab.exe."""
    (tmp_path / "palm-lab.exe").write_bytes(b"")
    cli_exe = tmp_path / "palm-lab-cli.exe"
    cli_exe.write_bytes(b"")
    target = launch_target(executable=cli_exe, frozen=True)
    assert target.target == tmp_path / "palm-lab.exe"
    assert target.icon == target.target and target.arguments == ""


def test_from_source_pythonw_is_preferred(tmp_path: Path) -> None:
    """pythonw.exe starts the window without a console flashing up."""
    python = tmp_path / "python.exe"
    (tmp_path / "pythonw.exe").write_bytes(b"")
    target = launch_target(executable=python, frozen=False)
    assert target.target == tmp_path / "pythonw.exe"
