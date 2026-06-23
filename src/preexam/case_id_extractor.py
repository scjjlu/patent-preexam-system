"""案卷号智能提取器 — 从上传文件中自动识别 Case ID。

优先级：
1. 从 110101.xml 提取 <内部编号>
2. 从 PDF 请求书首页提取案卷号
3. 从上传文件名正则匹配
4. 自动生成 CASE-YYYYMMDD-HHMMSS
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .cnipa_xml import _parse_xml, _safe_find_text

logger = logging.getLogger(__name__)

# ── Filename patterns (ordered by specificity) ────────────────────
# Search-based patterns (re.search anywhere in filename, no ^ anchor)
SEARCH_PATTERNS = [
    (r'([A-Z]{2}\d{12,})', "全文搜索申请号"),
    (r'(\d{8})', "全文搜索8位数字"),
    (r'(\d{3,6})\+', "全文搜索数字代码"),
]

FILENAME_PATTERNS = [
    # PY25DX39653FNPC-CN快审修改 → PY25DX39653FNPC-CN
    (r'^([A-Z]{2}\d{2}[A-Z]{2}\d{3,}[A-Z]+-[A-Z]{2})(?=\W|$)', "专利号代码"),
    # YS01220251003740+... → YS01220251003740
    (r'^([A-Z]{2}\d{12,})', "申请号"),
    # 10010315.zip → 10010315
    (r'^(\d{8})(?=\D|$)', "8位数字"),
    # 7300+快审 → 7300
    (r'^(\d{3,6})\+', "数字代码"),
    # ALPHA-BETA-123 → ALPHA-BETA-123  
    # Note: \w in Python 3 includes Chinese chars, so we use a-zA-Z0-9
    (r'^([a-zA-Z][a-zA-Z0-9]*(?:[-_][a-zA-Z0-9]+)+)', "连字符代码"),
    # 6位以上连续数字
    (r'^(\d{6,})', "数字序列"),
]


def safety_case_id(raw: str) -> str:
    """Sanitize a raw case ID for use as a directory name.

    - Replace spaces with hyphens
    - Remove illegal path characters
    - Keep Chinese, English, digits, hyphens, underscores
    - Collapse multiple hyphens
    - Truncate to 100 chars
    """
    if not raw or not raw.strip():
        return ""
    s = raw.strip()
    s = s.replace(" ", "-")
    s = re.sub(r'[\\/:*?"<>|]', "-", s)
    # Replace anything not allowed with a hyphen
    s = re.sub(r'[^\w\u4e00-\u9fff\-]', "-", s)
    s = re.sub(r'-+', "-", s)
    s = s.strip("-")
    return s[:100] or ""


# ── Priority 1: 110101.xml ───────────────────────────────────────

def _find_110101_xml(files: List[Path]) -> Optional[Path]:
    """Find the 110101.xml among the given files."""
    for f in files:
        if "110101" in f.name and f.suffix.lower() == ".xml":
            return f
    return None


def extract_from_110101_xml(file_path: Path) -> Tuple[Optional[str], str]:
    """Extract case ID from 发明专利请求书 XML.

    Looks for <内部编号>, <用户案卷号>, <案卷号> in order.
    Returns (case_id, source_description).
    """
    root = _parse_xml(file_path)
    if root is None:
        return None, "无法解析 XML"

    for tag in ["内部编号", "用户案卷号", "案卷号", "internal-number", "internal_number"]:
        text = _safe_find_text(root, f".//{tag}")
        if text and text.strip():
            case_id = safety_case_id(text)
            if case_id:
                return case_id, f"110101.xml <{tag}>"

    return None, "未找到案卷号字段"


# ── Priority 2: PDF text extraction ──────────────────────────────

def extract_from_pdf_text(file_path: Path) -> Tuple[Optional[str], str]:
    """Try to extract a case ID from a PDF file's text content.

    Uses pypdf if available; returns None gracefully if not.
    """
    try:
        import pypdf
    except ImportError:
        return None, "pypdf 未安装"

    try:
        reader = pypdf.PdfReader(str(file_path))
        text = ""
        for page in reader.pages[:5]:
            page_text = page.extract_text() or ""
            text += page_text
    except Exception:
        return None, "PDF 读取失败"

    if not text.strip():
        return None, "PDF 无文本内容（可能为扫描件）"

    # Look for case-number-related labels in Chinese
    label_patterns = [
        r'(?:用户案卷号|案卷号|内部编号)[：\s:]*(\S+)',
        r'(?:申请号|专利申请号)[：\s:]*(\S+)',
    ]
    for pat in label_patterns:
        m = re.search(pat, text)
        if m:
            case_id = safety_case_id(m.group(1))
            if case_id:
                return case_id, f"PDF 文本: {file_path.name}"

    # Fallback: look for patent-like codes in the text
    code_patterns = [
        r'([A-Z]{2}\d{2}[A-Z]{2}\d{3,}[A-Z]{2,3}-[A-Z]{2})',
        r'([A-Z]{2}\d{12,})',
    ]
    for pat in code_patterns:
        m = re.search(pat, text)
        if m:
            case_id = safety_case_id(m.group(1))
            if case_id:
                return case_id, f"PDF 文本代码: {file_path.name}"

    return None, "PDF 文本中未找到案卷号"


# ── Priority 3: Filename extraction ──────────────────────────────

def extract_from_filename(file_path: Path) -> Tuple[Optional[str], str]:
    """Extract case ID from a filename using regex patterns.

    First tries match-anchored patterns (from the start of filename),
    then falls back to search-based patterns (anywhere in filename).
    """
    stem = file_path.stem

    # Phase 1: match-anchored patterns
    for pattern, name in FILENAME_PATTERNS:
        m = re.match(pattern, stem)
        if m:
            raw = m.group(1)
            case_id = safety_case_id(raw)
            if case_id:
                return case_id, f"文件名: {file_path.name}"

    # Phase 2: search-based patterns (anywhere in filename)
    for pattern, name in SEARCH_PATTERNS:
        m = re.search(pattern, stem)
        if m:
            raw = m.group(1)
            case_id = safety_case_id(raw)
            if case_id:
                return case_id, f"文件名搜索: {file_path.name}"

    return None, "文件名无匹配"


# ── Priority 4: Auto-generate ────────────────────────────────────

def generate_case_id() -> Tuple[str, str]:
    """Generate a timestamp-based case ID as last resort."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"CASE-{ts}", "自动生成"


# ── Orchestrator ─────────────────────────────────────────────────

def extract_case_id(files: List[Path]) -> Tuple[str, str]:
    """Try all priority levels to extract a case ID.

    Args:
        files: List of uploaded file paths.

    Returns:
        Tuple of (case_id, source_description).
    """
    # Priority 1
    xml_path = _find_110101_xml(files)
    if xml_path:
        cid, src = extract_from_110101_xml(xml_path)
        if cid:
            logger.info("Case ID extracted (P1): %s — %s", cid, src)
            return cid, src

    # Priority 2
    for f in files:
        if f.suffix.lower() == ".pdf":
            cid, src = extract_from_pdf_text(f)
            if cid:
                logger.info("Case ID extracted (P2): %s — %s", cid, src)
                return cid, src

    # Priority 3
    for f in files:
        cid, src = extract_from_filename(f)
        if cid:
            logger.info("Case ID extracted (P3): %s — %s", cid, src)
            return cid, src

    # Priority 4
    cid, src = generate_case_id()
    logger.info("Case ID auto-generated (P4): %s", cid)
    return cid, src


# ── Directory conflict handling ──────────────────────────────────

def extract_all_candidates(files: List[Path]) -> List[Tuple[str, str]]:
    """Return ALL candidate case IDs from all priority levels.

    Returns list of (case_id, source) tuples, ordered by priority,
    with duplicates removed. Always includes auto-generated as fallback.
    """
    seen: set = set()
    candidates: List[Tuple[str, str]] = []

    # Priority 1: 110101.xml
    xml_path = _find_110101_xml(files)
    if xml_path:
        cid, src = extract_from_110101_xml(xml_path)
        if cid and cid not in seen:
            seen.add(cid)
            candidates.append((cid, src))

    # Priority 2: PDF text
    for f in files:
        if f.suffix.lower() == ".pdf":
            cid, src = extract_from_pdf_text(f)
            if cid and cid not in seen:
                seen.add(cid)
                candidates.append((cid, src))

    # Priority 3: Filename patterns (one per matching file)
    for f in files:
        cid, src = extract_from_filename(f)
        if cid and cid not in seen:
            seen.add(cid)
            candidates.append((cid, src))

    # Priority 4: Auto-generated (always included as fallback)
    cid, src = generate_case_id()
    if cid not in seen:
        candidates.append((cid, src))

    return candidates


def resolve_case_dir(cases_root: Path, case_id: str) -> Tuple[Path, str, bool]:
    """Resolve a case directory, handling conflicts with existing dirs.

    Returns:
        Tuple of (resolved_path, final_case_id, was_modified).
    """
    target = cases_root / case_id
    if not target.exists():
        return target, case_id, False

    # Check if target has input files
    input_dir = target / "input"
    if input_dir.exists() and any(input_dir.iterdir()):
        # Append suffix
        suffix = 1
        while True:
            alt_id = f"{case_id}-{suffix:03d}"
            alt_path = cases_root / alt_id
            if not alt_path.exists():
                return alt_path, alt_id, True
            suffix += 1

    # Empty existing directory → reuse
    return target, case_id, False
