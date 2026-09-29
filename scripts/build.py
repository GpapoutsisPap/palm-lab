"""Build the palm-lab programs with PyInstaller, and optionally the installer.

Usage:   uv run python scripts/build.py              # dist/palm-lab/
         uv run python scripts/build.py --installer  # also dist/palm-lab-setup-X.Y.Z.exe

The installer needs Inno Setup 6.3 or later:  winget install JRSoftware.InnoSetup
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "palm-lab.spec"
INSTALLER_SCRIPT = ROOT / "packaging" / "palm-lab.iss"
MODEL = ROOT / "src" / "palm_lab" / "assets" / "hand_landmarker.task"
VERSION_FILE = ROOT / "src" / "palm_lab" / "version.py"
DIST = ROOT / "dist"
WORK = ROOT / "build"
PROGRAMS = ("palm-lab", "palm-lab-cli")


def version() -> str:
    match = re.search(r'__version__ = "([^"]+)"', VERSION_FILE.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"No __version__ found in {VERSION_FILE}")
    return match.group(1)


def find_inno_setup() -> Path | None:
    """ISCC.exe on PATH, or where the Inno Setup installer and winget put it."""
    on_path = shutil.which("ISCC")
    if on_path:
        return Path(on_path)
    roots = [
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    ]
    for root in roots:
        candidate = Path(root) / "Inno Setup 6" / "ISCC.exe"
        if candidate.exists():
            return candidate
    return None


def build_programs() -> int:
    if not MODEL.exists():
        print(f"The hand model is missing at {MODEL}")
        print("Run `uv run palm-lab doctor` for the download command.")
        return 1

    try:
        import PyInstaller.__main__
    except ImportError:
        print('PyInstaller is not installed. Run: uv pip install -e ".[dev]"')
        return 1

    PyInstaller.__main__.run(
        [
            str(SPEC),
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(WORK),
        ]
    )

    app_dir = DIST / "palm-lab"
    suffix = ".exe" if sys.platform == "win32" else ""
    missing = [name for name in PROGRAMS if not (app_dir / f"{name}{suffix}").exists()]
    if missing:
        print(f"Build finished but {', '.join(missing)} was not produced.")
        return 1

    size_mb = sum(p.stat().st_size for p in app_dir.rglob("*") if p.is_file()) / 1_000_000
    print(f"\nBuilt {app_dir / f'palm-lab{suffix}'} (and palm-lab-cli{suffix})")
    print(f"Folder size: {size_mb:.0f} MB")
    return 0


def build_installer() -> int:
    iscc = find_inno_setup()
    if iscc is None:
        print("\nInno Setup was not found, so no installer was made.")
        print("Install it with:  winget install JRSoftware.InnoSetup")
        return 1
    result = subprocess.run([str(iscc), f"/DAppVersion={version()}", str(INSTALLER_SCRIPT)])
    if result.returncode != 0:
        return result.returncode
    print(f"\nBuilt {DIST / f'palm-lab-setup-{version()}.exe'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--installer", action="store_true", help="also build the Windows installer")
    args = parser.parse_args()
    code = build_programs()
    if code == 0 and args.installer:
        code = build_installer()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
