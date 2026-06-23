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
        pass


def _resolve_base() -> Path:
    """Resolve the project base directory in both frozen and dev modes."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
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
    log_file = BASE / "run_preexam.log"
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
    _log(f"Base dir: {BASE}")
    _log(f"Executable: {sys.executable if getattr(sys, 'frozen', False) else 'N/A'}")

    try:
        # ── 0.5 Check that all required data dirs exist ──────────
        required_dirs = [
            ("src/preexam", "程序源代码"),
            ("rules", "业务规则文件"),
            ("templates", "Prompt 模板"),
        ]
        missing = []
        for rel_path, desc in required_dirs:
            if not (BASE / rel_path).is_dir():
                missing.append(f"  {desc} ({rel_path})")
        if missing:
            msg = (
                "\n"
                "=" * 50 + "\n"
                "未找到必需的数据文件！\n\n"
                f"程序运行在: {BASE}\n\n"
                "缺少以下目录:\n" + "\n".join(missing) + "\n\n"
                "请确保您解压的是整个 zip 包，而不是只把 .exe 文件拖出来。\n"
                "正确的目录结构应该是:\n"
                f"  {BASE.name}/ ← 把这个文件夹解压出来\n"
                f"  {BASE.name}/preexam-review.exe\n"
                f"  {BASE.name}/src/...\n"
                f"  {BASE.name}/rules/...\n"
                f"  {BASE.name}/templates/...\n"
                "=" * 50
            )
            _log(msg)
            print(msg)
            print("\nPress Enter to exit...")
            try:
                input()
            except EOFError:
                pass
            sys.exit(1)

        # ── 1. Set working directory to project root ────────────
        os.chdir(str(BASE))
        _log(f"Changed CWD to: {os.getcwd()}")

        # ── 2. Add src/ to Python path ───────────────────────────
        src_dir = str(BASE / "src")
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
            raise FileNotFoundError(f"Cannot find ui_streamlit.py at {ui_script}")

        # ── 5. Verify Streamlit is importable ───────────────────
        try:
            import streamlit
            _log(f"Streamlit {streamlit.__version__} OK")
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
        _log(f"sys.argv set — starting Streamlit...")

        # ── 7. Open browser automatically ───────────────────────
        threading.Thread(
            target=_open_browser,
            args=("http://localhost:8501",),
            daemon=True,
        ).start()

        # ── 8. Launch Streamlit ─────────────────────────────────
        sys.stdout.flush()
        from streamlit.web import cli as stcli
        stcli.main()

    except SystemExit as e:
        _log(f"SystemExit: {e.code}")
        raise

    except Exception as e:
        _log("=" * 50)
        _log("FATAL ERROR — APP CRASHED")
        _log(f"{type(e).__name__}: {e}")
        _log("=" * 50)
        _log("Traceback:")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        _log("=" * 50)

        print(f"\n\n{'='*50}")
        print(f"程序启动失败: {e}")
        print(f"错误日志: {log_file}")
        print(f"{'='*50}")
        print("\n按 Enter 键退出...")
        try:
            input()
        except EOFError:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
