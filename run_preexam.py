"""专利快速预审案卷辅助审查系统 — Windows Launcher"""
import sys
import os
import traceback
import webbrowser
import threading
import time
from pathlib import Path


def _log(msg: str):
    try:
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
               else Path(__file__).resolve().parent
        with open(base / "run_preexam.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _resolve_base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent


def _get_exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _open_browser(url: str, delay: float = 2.5):
    try:
        time.sleep(delay)
        webbrowser.open(url)
    except Exception as e:
        _log(f"Browser open failed (non-fatal): {e}")


def main():
    BASE = _resolve_base()
    EXE_DIR = _get_exe_dir()

    # ── 0. Redirect stdout/stderr to log file ────────────────────
    log_file = EXE_DIR / "run_preexam.log"
    try:
        if log_file.exists():
            log_file.unlink()
        sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr
    except Exception:
        pass

    _log("=" * 50)
    _log("Starting...")
    _log(f"MEIPASS (data): {BASE}")
    _log(f"EXE dir: {EXE_DIR}")
    _log(f"log_file: {log_file}")

    try:
        # ── 0.5 Verify required data dirs ─────────────────────────
        required = [("src/preexam", "源代码"), ("rules", "规则文件"), ("templates", "模板")]
        missing = [f"  {d} ({r})" for r, d in required if not (BASE / r).is_dir()]
        if missing:
            msg = "\n" + "=" * 55 + "\n数据文件缺失！请完整解压整个文件夹。\n" + "\n".join(missing) + "\n" + "=" * 55
            _log(msg); print(msg); input("\n按 Enter 退出..."); sys.exit(1)

        # ── 1. Chdir to exe's directory (not temp) ───────────────
        os.chdir(str(EXE_DIR))
        _log(f"CWD → {os.getcwd()}")

        # ── 2. Add src/ to Python path ───────────────────────────
        src_dir = str(BASE / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        # ── 3. PREEXAM_ROOT = MEIPASS (data dir) ─────────────────
        os.environ["PREEXAM_ROOT"] = str(BASE)
        _log(f"PREEXAM_ROOT={BASE}")

        # ── 4. Suppress Streamlit email/telemetry prompt ─────────
        os.environ["STREAMLIT_GATHER_USAGE_STATS"] = "false"
        # Also create config file to prevent the first-run email prompt
        streamlit_conf_dir = Path.home() / ".streamlit"
        streamlit_conf_dir.mkdir(exist_ok=True)
        (streamlit_conf_dir / "config.toml").write_text(
            "[browser]\ngatherUsageStats = false\n", encoding="utf-8"
        )

        # ── 5. Verify UI script exists ──────────────────────────
        ui_script = BASE / "src" / "preexam" / "ui_streamlit.py"
        if not ui_script.is_file():
            raise FileNotFoundError(f"ui_streamlit.py not found at {ui_script}")

        # ── 6. Verify Streamlit is importable ────────────────────
        import streamlit
        _log(f"Streamlit {streamlit.__version__} OK")

        # ── 7. Prepare streamlit argv ────────────────────────────
        sys.argv = [
            "streamlit", "run", str(ui_script),
            "--server.headless=false",
            "--server.port=8501",
            "--browser.serverAddress=localhost",
            "--browser.gatherUsageStats=false",
            "--server.fileWatcherType=none",
            "--global.developmentMode=false",
        ]
        _log("Starting Streamlit...")

        # ── 8. Open browser ─────────────────────────────────────
        threading.Thread(target=_open_browser, args=("http://localhost:8501",), daemon=True).start()

        # ── 9. Go! ──────────────────────────────────────────────
        sys.stdout.flush()
        from streamlit.web import cli as stcli
        stcli.main()

    except SystemExit:
        raise
    except Exception as e:
        _log(f"FATAL: {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        print(f"\n启动失败: {e}\n日志: {log_file}\n\n按 Enter 退出...")
        try: input()
        except EOFError: pass
        sys.exit(1)


if __name__ == "__main__":
    main()
