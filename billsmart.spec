# PyInstaller build for BillSmart desktop app (Windows, one-dir).
# Build with:  pyinstaller billsmart.spec
# Output:      dist/BillSmart/BillSmart.exe  (wrapped by installer.iss)
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)  # type: ignore  # noqa: F821
APP_VERSION = "1.0.0"

hiddenimports = [
    "waitress",
    "webview",
    "clr",
    "pythonnet",
]
hiddenimports += collect_submodules("waitress")
hiddenimports += collect_submodules("webview")

a = Analysis(  # noqa: F821
    ["desktop.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "templates"), "templates"),
        (str(ROOT / "static"), "static"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "notebook", "nbformat", "nbclient",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "gi",
        "jedi", "parso", "IPython", "prompt_toolkit", "traitlets",
        "numpy", "pandas", "scipy", "lxml", "Cython",
        "oracledb", "psycopg2", "zmq", "tornado", "black",
        "blib2to3", "pytokens", "mypy", "pytest", "_pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BillSmart",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "icon.ico"),
    version_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BillSmart",
)

app = BUNDLE(coll, name="BillSmart")  # noqa: F821 (no-op on Windows, kept for mac parity)
