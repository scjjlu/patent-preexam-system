"""专利快速预审案卷辅助审查系统 — Windows Launcher

Entry point for the PyInstaller-packaged app.
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
        pass


def _resolve_base() -> Path:
    """In PyInstaller one-file mode, data files (src/, rules/, templates/)
    are extracted to sys._MEIPASS, NOT next to the .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent


def _open_browser(url: str, delay: float = 2.5):
    try:
        time.sleep(delay)
        webbrowser.open(url)
    except Exception as e:
        _log(f"Browser open failed (non-fatal): {e}")


def main():
    # ── 0. Redirect stdout/stderr to log file ────────────────────
    BASE = _resolve_base()
    log_file = Path(sys.executable).resolve().parent / "run_preexam.log" if getattr(sys, "frozen", False) \
               else Path(__file__).resolve().parent / "run_preexam.log"
    try:
        if log_file.exists():
            log_file.unlink()
        sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr
    except Exception:
        pass

    _log("=" * 50)
    _log("Patent Pre‑Exam Review System starting...")
    _log(f"Frozen: {getattr(sys, 'frozen', False)}")
    _log(f"MEIPASS (data dir): {BASE}")
    _log(f"Executable dir: {Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else 'N/A'}")

    try:
        # ── 0.5 Ensure required data dirs exist in MEIPASS ──────
        required = [
            ("src/preexam", "源代码"),
            ("rules", "规则文件"),
            ("templates", "模板"),
        ]
        missing = []
        for rel, desc in required:
            if not (BASE / rel).is_dir():
                missing.append(f"  {desc} ({rel})")
        if missing:
            msg = (
                "\n" + "=" * 55 + "\n"
                "程序数据文件缺失！\n\n"
                "压缩包里的数据文件应该随 .exe 自动解压，但似乎出了问题。\n"
                "请到以下路径检查文件是否存在：\n"
                f"  {BASE}\n\n"
                "缺少:\n" + "\n".join(missing) + "\n"
                "=" * 55
            )
            _log(msg)
            print(msg)
            print("\nPress Enter to exit...")
            try: input()
            except EOFError: pass
            sys.exit(1)

        # ── 1. Chdir to MEIPASS so relative paths resolve ────────
        os.chdir(str(BASE))
        _log(f"CWD → {BASE}")

        # ── 2. Add src/ to Python path ───────────────────────────
        src_dir = str(BASE / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        _log(f"sys.path +{src_dir}")

        # ── 3. PREEXAM_ROOT = MEIPASS (data dir) ─────────────────
        os.environ["PREEXAM_ROOT"] = str(BASE)
        _log(f"PREEXAM_ROOT={BASE}")

        # ── 4. Verify the UI script exists ───────────────────────
        ui_script = BASE / "src" / "preexam" / "ui_streamlit.py"
        _log(f"UI script: {ui_script}  exists={ui_script.is_file()}")
        if not ui_script.is_file():
            raise FileNotFoundError(f"ui_streamlit.py not found at {ui_script}")

        # ── 5. Verify Streamlit importable ──────────────────────
        import streamlit
        _log(f"Streamlit {streamlit.__version__} OK")

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
        _log("Starting Streamlit...")

        # ── 7. Open browser ─────────────────────────────────────
        threading.Thread(target=_open_browser, args=("http://localhost:8501",), daemon=True).start()

        # ── 8. Go! ──────────────────────────────────────────────
        sys.stdout.flush()
        from streamlit.web import cli as stcli
        stcli.main()

    except SystemExit as e:
        _log(f"SystemExit: {e.code}")
        raise

    except Exception as e:
        _log("=" * 50)
        _log(f"FATAL: {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        _log("=" * 50)

        print(f"\n{'='*50}")
        print(f"启动失败: {e}")
        print(f"日志文件: {log_file}")
        print(f"{'='*50}")
        print("\n按 Enter 退出...")
        try: input()
        except EOFError: pass
        sys.exit(1)


if __name__ == "__main__":
    main()
