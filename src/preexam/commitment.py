"""Commitment letter processing (Phase 1: placeholder / identification).

Phase 1 does not perform OCR or deep analysis. This module identifies
commitment-related files and marks them with conservative status labels.
"""

from pathlib import Path
from typing import List, Optional, Dict


COMMITMENT_KEYWORDS = ["承诺书", "commitment", "保证书", "声明书"]


def identify_commitment_files(all_files: List[Path]) -> List[Path]:
    """Find files that look like commitment letters based on filename keywords."""
    matches = []
    for f in all_files:
        name = f.stem.lower()
        for kw in COMMITMENT_KEYWORDS:
            if kw in name:
                matches.append(f)
                break
    return matches


def assess_commitment(file_path: Optional[Path], logger) -> dict:
    """Assess a commitment file.

    Phase 1: conservative assessment — never concludes '未盖章'.
    Returns a dict with path, status, and confidence.
    """
    if file_path is None:
        return {
            "path": None,
            "status": "未检测到承诺书文件",
            "confidence": "n/a",
        }

    suffix = file_path.suffix.lower()
    is_image = suffix in {".jpg", ".jpeg", ".png"}
    is_pdf = suffix == ".pdf"

    if is_image:
        # Images require OCR; Phase 1 cannot process them reliably
        logger.info("Commitment is an image file — requires OCR confirmation")
        return {
            "path": str(file_path),
            "status": "需人工确认",
            "confidence": "low",
            "reason": "图片型承诺书，无法自动判断签章状态",
        }
    elif is_pdf:
        # PDF may be text-based or scanned; Phase 1 marks conservatively
        logger.info("Commitment is a PDF — conservative assessment")
        return {
            "path": str(file_path),
            "status": "需人工确认",
            "confidence": "low",
            "reason": "PDF 承诺书，未执行 OCR 签章检测，需人工确认",
        }
    else:
        return {
            "path": str(file_path),
            "status": "需人工确认",
            "confidence": "low",
            "reason": f"非标准承诺书格式 ({suffix})，需人工确认",
        }
