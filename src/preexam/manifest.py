"""File manifest generation (txt + json)."""

import json
from pathlib import Path
from typing import List, Dict, Optional

from . import config as cfg



# ── Enhanced role detection ─────────────────────────────────────
# Keyword patterns for filename-based role detection
# (keywords, role, description, source)
FILENAME_ROLE_MAP = [
    (["承诺书", "承诺"], "commitment", "承诺书文件", "input"),
    (["自检表", "自检", "self-check", "self_check", "selfcheck"], "self_check", "自检表文件", "input"),
    (["备案通知书", "备案通知", "备案"], "filing_notice", "备案通知书", "input"),
    (["身份证明", "身份证", "身份"], "identity_document", "身份证明文件", "input"),
    (["快审", "快审修改", "quick_exam", "quickexam", "快审修"], "quick_exam_package", "快审修改压缩包", "input"),
    (["申请文件", "申请"], "application_pdf", "申请文件", "input"),
]

# ZIP content keyword patterns
ZIP_CONTENT_MAP = [
    (["承诺书", "承诺"], "commitment_package", "承诺书压缩包"),
    (["自检表", "自检", "selfcheck"], "self_check_package", "自检表压缩包"),
    (["备案通知书", "备案通知"], "filing_notice_package", "备案通知书压缩包"),
    (["身份证明", "身份证"], "identity_document_package", "身份证明压缩包"),
    (["快审", "快审修改"], "quick_exam_package", "快审修改压缩包"),
]


def _detect_role_by_filename(name: str) -> Optional[tuple]:
    """Detect file role by matching filename keywords."""
    name_lower = name.lower()
    for keywords, role, description, source in FILENAME_ROLE_MAP:
        if any(kw in name_lower for kw in keywords):
            return role, description, source
    return None


def _inspect_zip_keywords(zip_path: Path) -> Optional[tuple]:
    """Peek inside a ZIP to determine role by its contents."""
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            all_names = " ".join(name.lower() for name in names)
        for keywords, role, description in ZIP_CONTENT_MAP:
            if any(kw in all_names for kw in keywords):
                return role, description, "input"
    except Exception:
        pass
    return None


def _detect_role_by_extension(suffix: str) -> tuple:
    """Fallback: detect role purely by file extension."""
    ext_map = {
        ".pdf": ("pdf_document", "PDF 文件", "input"),
        ".zip": ("zip_archive", "ZIP 压缩包", "input"),
        ".rar": ("rar_archive", "RAR 压缩包", "input"),
        ".xml": ("xml_document", "XML 文件", "input"),
        ".jpg": ("image", "JPEG 图片", "input"),
        ".jpeg": ("image", "JPEG 图片", "input"),
        ".png": ("image", "PNG 图片", "input"),
        ".docx": ("docx_document", "DOCX 文档", "input"),
        ".doc": ("doc_document", "DOC 文档", "input"),
    }
    return ext_map.get(suffix, ("unknown", "未知文件", "input"))


# ── ZIP content type detection for images inside archives ──────────
def classify_extracted_file(path: Path) -> str:
    """Classify a file inside extracted/ based on parent dir and name."""
    name = path.stem.lower()
    rel = str(path.relative_to(path.anchor) if path.is_absolute() else path)
    rel_lower = rel.lower()
    for keywords, role, _desc, _src in FILENAME_ROLE_MAP:
        if any(kw in name for kw in keywords) or any(kw in rel_lower for kw in keywords):
            return role
    return "extracted_attachment"


def _load_cnipa_mapping() -> dict:
    import yaml
    mapping_path = cfg.get_rules_dir() / "cnipa_file_mapping.yaml"
    if mapping_path.exists():
        with open(mapping_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("file_types", {})
    return {}


def classify_file(path: Path) -> tuple:
    """Classify a file by CNIPA XML code, filename keywords, ZIP content,
    and extension — in that order.

    Returns:
        Tuple of (role, description, source).
    """
    name = path.name
    suffix = path.suffix.lower()

    # 1. CNIPA XML code check
    mapping = _load_cnipa_mapping()
    for code, info in mapping.items():
        if code in name and suffix == ".xml":
            return info["role"], info["description"], "cnipa_xml"

    # 2. Unknown XML → auxiliary XML
    if suffix == ".xml":
        return ("auxiliary_xml", "辅助 XML 文件", "input")

    # 3. Keyword-based role detection from filename
    role_result = _detect_role_by_filename(name)
    if role_result:
        return role_result

    # 4. ZIP content inspection
    if suffix in (".zip", ".rar"):
        zip_result = _inspect_zip_keywords(path) if suffix == ".zip" else None
        if zip_result:
            return zip_result

    # 5. Extension-based fallback
    return _detect_role_by_extension(suffix)


def generate_manifest(all_files: List[Path], case_dir: Path, logger) -> Dict:
    """Generate file manifest and write to output/.

    Returns:
        The manifest data dict (for reuse in prompt generation).
    """
    output_dir = case_dir / cfg.OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for f in all_files:
        rel_path = f.relative_to(case_dir)
        role, description, source = classify_file(f)
        entries.append({
            "path": str(rel_path),
            "file_type": f.suffix.lower().lstrip(".") if f.suffix else "unknown",
            "role": role,
            "description": description,
            "source": source,
        })

    # Write TXT
    txt_path = output_dir / "file_manifest.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"File Manifest — {case_dir.name}\n")
        f.write(f"{'=' * 60}\n\n")
        for e in entries:
            f.write(f"{e['path']}\n")
            f.write(f"  Type: {e['file_type']}  Role: {e['role']}\n")
            f.write(f"  {e['description']}\n\n")

    # Write JSON
    json_path = output_dir / "file_manifest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    logger.info("Manifest written: %d entries", len(entries))
    return {"entries": entries}
