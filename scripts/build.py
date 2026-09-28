"""Build the palm-lab executable with PyInstaller.

Usage:   uv run python scripts/build.py
Output:  dist/palm-lab/palm-lab.exe
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "palm-lab.spec"
MODEL = ROOT / "src" / "palm_lab" / "assets" / "hand_landmarker.task"
DIST = ROOT / "dist"
WORK = ROOT / "build"


def main() -> int:
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
    exe = app_dir / ("palm-lab.exe" if sys.platform == "win32" else "palm-lab")
    if not exe.exists():
        print(f"Build finished but {exe} was not produced.")
        return 1

    size_mb = sum(p.stat().st_size for p in app_dir.rglob("*") if p.is_file()) / 1_000_000
    print(f"\nBuilt {exe}")
    print(f"Folder size: {size_mb:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
