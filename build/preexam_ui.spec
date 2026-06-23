# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec: 专利快速预审案卷辅助审查系统 (Windows)
#
# Build (Windows, from project root):
#     pyinstaller build/preexam_ui.spec --noconfirm
#
# Build (via GitHub Actions, automated):
#     Push to GitHub; see .github/workflows/build-windows.yml
#

import sys
import os
from pathlib import Path

# ── Project root
# NOTE: __file__ is NOT available in PyInstaller spec files.
# Path.cwd() works because pyinstaller is always run from project root.
ROOT = Path.cwd().resolve()

# ── Block cipher (disabled for speed)
block_cipher = None


# ── Analysis ─────────────────────────────────────────────────────
a = Analysis(
    # Entry point
    [str(ROOT / "run_preexam.py")],

    # Extra search paths
    pathex=[
        str(ROOT),
        str(ROOT / "src"),
    ],

    binaries=[],

    # Data files bundled alongside the .exe
    datas=[

        # ── Application data ──────────────────────────────────────
        (str(ROOT / "rules"),          "rules"),
        (str(ROOT / "templates"),      "templates"),
        (str(ROOT / "src"),            "src"),
        (str(ROOT / "pyproject.toml"), "."),
        (str(ROOT / "setup.cfg"),      "."),
    ],

    # ── Hidden imports ───────────────────────────────────────────
    # (modules that PyInstaller's static analysis might miss)
    hiddenimports=[

        # Preexam system modules
        "preexam",
        "preexam.cli",
        "preexam.config",
        "preexam.case_manager",
        "preexam.archive",
        "preexam.manifest",
        "preexam.cnipa_xml",
        "preexam.commitment",
        "preexam.prompt_builder",
        "preexam.logging_utils",
        "preexam.rules_engine",
        "preexam.report_generator",
        "preexam.case_id_extractor",

        # Streamlit internals (commonly missed)
        "streamlit",
        "streamlit.web.cli",
        "streamlit.web.bootstrap",
        "streamlit.runtime",
        "streamlit.connections",
        "streamlit.elements",
        "streamlit.proto",
        "streamlit.temporary_directory",
        "streamlit.user_info",

        # Known third-party
        "yaml",
        "lxml",
        "lxml.etree",
        "PIL",
        "PIL._imaging",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "requests",
        "jinja2",
        "markupsafe",
        "altair",
        "pandas",
        "numpy",
        "pyarrow",
        "pydeck",
        "toml",
        "watchdog",

        # Streamlit file watcher
        "streamlit.watcher",
        "streamlit.watcher.polling_file_watcher",
        "streamlit.watcher.local_sources_watcher",
    ],

    # ── Exclude unused bloat ─────────────────────────────────────
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "notebook",
        "jupyter",
        "jupyter_client",
        "jupyter_core",
        "nbformat",
        "nbconvert",
        "tensorflow",
        "torch",
        "cv2",
        "cairo",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "setuptools",
        "pip",
        "IPython",
        "sphinx",
        "bokeh",
        "plotly",
    ],

    # ── Hooks ────────────────────────────────────────────────────
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


# ── Encoded Python archives ──────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ── Executable ───────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="专利预审案卷辅助审查系统",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,        # Keep console visible for Streamlit logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
