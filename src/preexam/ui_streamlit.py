"""Streamlit 本地界面 — 专利快速预审案卷辅助审查系统。

运行: PYTHONPATH=src streamlit run src/preexam/ui_streamlit.py
"""
import sys, json, shutil, io, zipfile, os
from datetime import datetime
from pathlib import Path
import streamlit as st

_HERE = Path(__file__).resolve().parent

# Resolve project root: env var takes priority (used by PyInstaller bundle)
_env_root = os.environ.get("PREEXAM_ROOT")
if _env_root:
    _PROJECT_ROOT = Path(_env_root).resolve()
else:
    _PROJECT_ROOT = _HERE.parent.parent

_src = str(_PROJECT_ROOT / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from preexam.cli import cmd_prepare, cmd_check, cmd_report, cmd_clean
from preexam.case_id_extractor import extract_all_candidates, resolve_case_dir

CASES = _PROJECT_ROOT / "cases"

# ── Session state ────────────────────────────────────────────────
def _ss():
    return st.session_state

if "preexam" not in _ss():
    _ss()["preexam"] = {
        "session_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "candidates": [],
        "case_id": "",
        "upload_fp": None,
        "log_buf": "",
    }

def _s():
    return _ss()["preexam"]

# ── Page ─────────────────────────────────────────────────────────
st.set_page_config(page_title="专利快速预审案卷辅助审查系统", page_icon="⚖️", layout="wide")
st.markdown("<h1 style='text-align: center;'>⚖️ 专利快速预审案卷辅助审查系统</h1>",
            unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("上传案卷文件（可多选）")
    uploaded = st.file_uploader("选择文件", accept_multiple_files=True, key="fu")

    # ── Save uploaded files (only when fingerprint changes) ──────
    if uploaded:
        fp = frozenset((f.name, f.size) for f in uploaded)
        if _s()["upload_fp"] != fp:
            _s()["upload_fp"] = fp
            incoming = CASES / "_incoming" / _s()["session_id"] / "input"
            incoming.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                (incoming / f.name).write_bytes(f.getbuffer())
            _s()["candidates"] = []
            _s()["case_id"] = ""
            # Auto-detect candidates
            file_list = list(incoming.iterdir())
            if file_list:
                _s()["candidates"] = extract_all_candidates(file_list)

    # Show uploaded file list
    incoming_dir = CASES / "_incoming" / _s()["session_id"] / "input"
    if incoming_dir.exists():
        files = sorted(incoming_dir.iterdir())
        for f in files:
            st.markdown(f"📄 `{f.name}`")

    st.markdown("---")
    st.subheader("识别到的案卷号")

    # ── Case ID ─────────────────────────────────────────────────
    case_id = st.text_input("案卷号", value=_s()["case_id"],
                            label_visibility="collapsed",
                            placeholder="上传文件后点击「识别案卷号」",
                            key="ci_input")
    _s()["case_id"] = case_id

    # ── Candidate radio ─────────────────────────────────────────
    cands = _s().get("candidates", [])
    if len(cands) > 1:
        sel = st.radio("检测到多个候选案卷号，请选择：",
                       [c[0] for c in cands] + ["__custom__"],
                       format_func=lambda x: x if x != "__custom__" else "✏️ 自定义",
                       key="cr")
        if sel and sel != "__custom__":
            _s()["case_id"] = sel

    st.markdown("---")

    # ── Helpers ─────────────────────────────────────────────────
    def _ensure_case(cid):
        trg = CASES / cid / "input"
        if trg.exists() and any(trg.iterdir()):
            return
        incoming = CASES / "_incoming" / _s()["session_id"] / "input"
        if not incoming.exists():
            return
        trg.mkdir(parents=True, exist_ok=True)
        for f in incoming.iterdir():
            if f.is_file():
                shutil.copy2(f, trg / f.name)

    def _run_cmd(name, fn, cid):
        _ensure_case(cid)
        from io import StringIO
        from contextlib import redirect_stdout
        buf = StringIO()
        with redirect_stdout(buf):
            fn(str(CASES / cid))
        _s()["log_buf"] += f"\n[{name}]\n{buf.getvalue()}"
        st.success(f"{name} 完成")

    # ── Buttons (standard Streamlit pattern: no st.rerun) ───────
    def _identify():
        d = CASES / "_incoming" / _s()["session_id"] / "input"
        if d.exists():
            fl = list(d.iterdir())
            _s()["candidates"] = extract_all_candidates(fl) if fl else []
            if _s()["candidates"]:
                _s()["case_id"] = _s()["candidates"][0][0]

    st.button("🔍 识别案卷号", on_click=_identify, use_container_width=True)

    # Clean
    if st.button("🧹 清空本案输出", use_container_width=True):
        cid = _s()["case_id"]
        if cid and (CASES / cid).exists():
            cmd_clean(str(CASES / cid), force=False)
            st.info("清理完成")

    # One-click all
    if st.button("🚀 一键运行全部", use_container_width=True):
        cid = _s()["case_id"]
        if cid:
            with st.spinner("运行 prepare → check → report..."):
                _run_cmd("prepare", cmd_prepare, cid)
                _run_cmd("check", cmd_check, cid)
                _run_cmd("report", cmd_report, cid)

    col3, col4, col5 = st.columns(3)
    with col3:
        if st.button("① prepare", use_container_width=True):
            cid = _s()["case_id"]
            if cid:
                with st.spinner("运行 prepare..."):
                    _run_cmd("prepare", cmd_prepare, cid)
    with col4:
        if st.button("② check", use_container_width=True):
            cid = _s()["case_id"]
            if cid:
                with st.spinner("运行 check..."):
                    _run_cmd("check", cmd_check, cid)
    with col5:
        if st.button("③ report", use_container_width=True):
            cid = _s()["case_id"]
            if cid:
                with st.spinner("运行 report..."):
                    _run_cmd("report", cmd_report, cid)

    st.markdown("---")
    st.caption(
        "⚠️ **系统说明**: 本系统只做形式性、流程性、材料完整性辅助审查，"
        "实质性问题仍由预审员判断。最终以国家知识产权局实质审查结果为准。"
    )

# ── Main tabs ────────────────────────────────────────────────────
tab_log, tab_manifest, tab_warnings, tab_report = st.tabs([
    "📋 运行日志", "📄 文件清单", "⚠️ 警告", "📑 审查报告"
])

cid = _s()["case_id"]
cdir = CASES / cid if cid else None

with tab_log:
    st.subheader("运行日志")
    log_content = ""
    if cdir and (cdir / "logs" / "preexam.log").exists():
        log_content = (cdir / "logs" / "preexam.log").read_text(encoding="utf-8", errors="replace")
    buf = _s().get("log_buf", "")
    display = (buf + "\n--- 文件日志 ---\n" + log_content) if (buf and buf.strip()) else (log_content or "（无日志）")
    st.text_area("日志", display, height=400, key="log_area")

with tab_manifest:
    st.subheader("文件清单")
    mf = cdir / "output" / "file_manifest.txt" if cdir else None
    if mf and mf.exists():
        content = mf.read_text(encoding="utf-8", errors="replace")
        st.text(content)
        st.download_button("下载", content, file_name="file_manifest.txt")
    else:
        st.info("尚未生成 — 请先运行 prepare")

with tab_warnings:
    st.subheader("处理警告")
    wf = cdir / "parsed" / "warnings.json" if cdir else None
    if wf and wf.exists():
        st.json(json.loads(wf.read_text(encoding="utf-8", errors="replace") or "[]"))
    else:
        st.info("尚未生成 — 请先运行 prepare")

with tab_report:
    st.subheader("审查报告")
    rp = cdir / "output" / "report.md" if cdir else None
    if rp and rp.exists():
        content = rp.read_text(encoding="utf-8", errors="replace")
        st.markdown(content)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 下载 report.md", content, file_name="report.md")
        with col2:
            out_dir = cdir / "output"
            if out_dir.exists():
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in out_dir.iterdir():
                        if f.is_file(): zf.write(f, f.name)
                buf.seek(0)
                st.download_button("📦 下载 output/ 全部", buf, file_name=f"{cid}_output.zip")
    else:
        st.info("尚未生成 — 请先运行 prepare → check → report")
