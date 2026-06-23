"""专利快速预审案卷辅助审查系统 — Windows Launcher

This is the entry point for the PyInstaller-packaged app.
It starts the Streamlit server and opens the user's browser.

Usage (development):
    python run_preexam.py

Usage (packaged):
    Double-click 专利预审案卷辅助审查系统.exe
"""
import sys
import os
import webbrowser
import threading
import time
from pathlib import Path


def _resolve_base() -> Path:
    """Resolve the project base directory in both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle — base is where the .exe sits
        return Path(sys.executable).resolve().parent
    else:
        # Development mode — base is this script's parent directory
        return Path(__file__).resolve().parent


def _open_browser(url: str, delay: float = 2.0):
    """Open browser after a short delay so the server has time to start."""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    BASE = _resolve_base()

    # ── 1. Set working directory to project root
    os.chdir(str(BASE))

    # ── 2. Add src/ to Python path
    src_dir = str(BASE / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # ── 3. Expose base dir to modules via env var
    os.environ["PREEXAM_ROOT"] = str(BASE)

    # ── 4. Prepare streamlit argv
    ui_script = str(BASE / "src" / "preexam" / "ui_streamlit.py")

    sys.argv = [
        "streamlit", "run", ui_script,
        "--server.headless=false",
        "--server.port=8501",
        "--browser.serverAddress=localhost",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]

    # ── 5. Open browser automatically after a short delay
    threading.Thread(
        target=_open_browser,
        args=("http://localhost:8501",),
        daemon=True,
    ).start()

    # ── 6. Launch Streamlit
    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
