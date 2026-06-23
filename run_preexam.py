"""专利快速预审案卷辅助审查系统 — Windows Launcher

Entry point for the PyInstaller-packaged app.
Writes startup errors to run_preexam.log for debugging.
"""
import sys
import os
import traceback
import webbrowser
import threading
import time
from pathlib import Path


def _log(msg: str):
    """Append a line to the log file next to the executable."""
    try:
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
               else Path(__file__).resolve().parent
        log_path = base / "run_preexam.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass  # can't log — fail silently


def _resolve_base() -> Path:
    """Resolve the project base directory in both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent


def _open_browser(url: str, delay: float = 2.5):
    """Open browser after a short delay so the server has time to start."""
    try:
        time.sleep(delay)
        webbrowser.open(url)
    except Exception as e:
        _log(f"Browser open failed (non-fatal): {e}")


def main():
    # ── 0. Redirect stdout/stderr to file to capture all output ──
    BASE = _resolve_base()
    log_file = BASE / "run_preexam.log"
    try:
        # Clear previous log
        if log_file.exists():
            log_file.unlink()
        sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr
    except Exception:
        pass

    _log("=" * 50)
    _log("Patent Pre‑Exam Review System starting...")
    _log(f"Frozen: {getattr(sys, 'frozen', False)}")
    _log(f"Base dir: {BASE}")
    _log(f"Executable: {sys.executable if getattr(sys, 'frozen', False) else 'N/A (dev mode)'}")

    try:
        # ── 1. Set working directory to project root ────────────
        os.chdir(str(BASE))
        _log(f"Changed CWD to: {os.getcwd()}")

        # ── 2. Add src/ to Python path ───────────────────────────
        src_dir = str(BASE / "src")
        _log(f"Looking for src at: {src_dir}")
        _log(f"src exists: {os.path.isdir(src_dir)}")
        if os.path.isdir(src_dir / "preexam"):
            _log(f"preexam package found: {sorted(os.listdir(src_dir / 'preexam'))[:10]}")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
            _log(f"Added {src_dir} to sys.path")

        # ── 3. Expose base dir to modules via env var ───────────
        os.environ["PREEXAM_ROOT"] = str(BASE)
        _log(f"Set PREEXAM_ROOT={BASE}")

        # ── 4. Verify the Streamlit UI script exists ────────────
        ui_script = BASE / "src" / "preexam" / "ui_streamlit.py"
        _log(f"UI script path: {ui_script}")
        _log(f"UI script exists: {ui_script.is_file()}")
        if not ui_script.is_file():
            raise FileNotFoundError(
                f"Cannot find ui_streamlit.py at {ui_script}\n"
                f"Contents of {BASE / 'src' / 'preexam'}: "
                f"{list((BASE / 'src' / 'preexam').iterdir()) if (BASE / 'src' / 'preexam').is_dir() else 'DIR NOT FOUND'}"
            )

        # ── 5. Verify Streamlit is importable ───────────────────
        try:
            import streamlit
            _log(f"Streamlit imported: {streamlit.__version__}")
            _log(f"Streamlit file: {streamlit.__file__}")
        except ImportError as e:
            raise ImportError(f"Streamlit cannot be imported: {e}")

        # ── 6. Prepare streamlit argv ────────────────────────────
        sys.argv = [
            "streamlit", "run", str(ui_script),
            "--server.headless=false",
            "--server.port=8501",
            "--browser.serverAddress=localhost",
            "--browser.gatherUsageStats=false",
            "--server.fileWatcherType=none",
            "--server.enableCORS=false",
            "--global.developmentMode=false",
        ]
        _log(f"sys.argv set to: {sys.argv}")

        # ── 7. Open browser automatically ───────────────────────
        threading.Thread(
            target=_open_browser,
            args=("http://localhost:8501",),
            daemon=True,
        ).start()

        # ── 8. Launch Streamlit ─────────────────────────────────
        _log("Starting Streamlit via cli.main()...")
        sys.stdout.flush()

        from streamlit.web import cli as stcli
        stcli.main()

    except SystemExit as e:
        _log(f"SystemExit caught: {e}")
        # Streamlit exits with 0 on success, non-zero on failure
        if e.code != 0 and e.code is not None:
            _log(f"Streamlit exited with code {e.code}")
        raise  # Re-raise to exit

    except Exception as e:
        _log("=" * 50)
        _log("FATAL ERROR — APP CRASHED")
        _log(str(e))
        _log("=" * 50)
        _log("Traceback:")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        _log("=" * 50)
        _log("The application encountered an error and will exit.")
        _log(f"Please check the log file for details: {log_file}")
        _log("=" * 50)

        # Keep console open so user can see the error
        print("\n\nFATAL ERROR — See run_preexam.log for details.")
        print(f"Log file: {log_file}")
        print("\nPress Enter to exit...")
        try:
            input()
        except EOFError:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
