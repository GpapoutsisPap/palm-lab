# PyInstaller build recipe for palm-lab.
#
# Build with:  uv run python scripts/build.py
# Output:      dist/palm-lab/palm-lab.exe  (one folder, not a single file)

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent  # noqa: F821  (SPECPATH is injected by PyInstaller)
SRC = ROOT / "src"
MODEL = SRC / "palm_lab" / "assets" / "hand_landmarker.task"

# MediaPipe ships native libraries and data files that PyInstaller's import
# scanning does not find on its own. Without this the build succeeds and the
# executable then crashes on launch.
mp_datas, mp_binaries, mp_hiddenimports = collect_all("mediapipe")

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=mp_binaries,
    datas=[(str(MODEL), "palm_lab/assets"), *mp_datas],
    hiddenimports=mp_hiddenimports,
    excludes=["pytest", "mypy", "ruff", "pre_commit", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="palm-lab",
    console=True,
    upx=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="palm-lab",
    upx=False,
)
