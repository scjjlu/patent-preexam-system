# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec: 专利快速预审案卷辅助审查系统 (Windows)
#

import sys
import os
from pathlib import Path

# Project root (CWD is project root when pyinstaller is invoked)
ROOT = Path.cwd().resolve()

block_cipher = None

a = Analysis(
    [str(ROOT / "run_preexam.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "rules"),          "rules"),
        (str(ROOT / "templates"),      "templates"),
        (str(ROOT / "src"),            "src"),
        (str(ROOT / "pyproject.toml"), "."),
        (str(ROOT / "setup.cfg"),      "."),
    ],
    hiddenimports=[
        # Preexam system
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
        # Streamlit
        "streamlit",
        "streamlit.web.cli",
        "streamlit.web.bootstrap",
        "streamlit.runtime",
        "streamlit.connections",
        "streamlit.elements",
        "streamlit.proto",
        "streamlit.temporary_directory",
        "streamlit.user_info",
        # Third-party
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
        "streamlit.watcher",
        "streamlit.watcher.polling_file_watcher",
        "streamlit.watcher.local_sources_watcher",
    ],
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
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use English name for the EXE to avoid PowerShell path issues
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="preexam-review",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
