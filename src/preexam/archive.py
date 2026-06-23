"""ZIP / RAR extraction with nested archive support and crash tolerance."""

import zipfile
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional

from . import config as cfg

MAX_NESTED_DEPTH = 3


def extract_archives(
    archive_paths: List[Path],
    output_dir: Path,
    logger,
) -> List[dict]:
    """Extract all archive files into output_dir, including nested archives.

    Extraction of nested archives is recursive up to MAX_NESTED_DEPTH levels.
    Per-file failures (e.g. Chinese-encoding filenames) are recorded in the
    returned warning list rather than interrupting the whole process.

    Returns:
        List of warning dicts with keys: file, message.
    """
    warnings: List[dict] = []

    # Phase 1: extract top-level archives
    for archive in archive_paths:
        ext = archive.suffix.lower()
        if ext == ".zip":
            warns = _extract_zip(archive, output_dir, logger)
            warnings.extend(warns)
        elif ext == ".rar":
            warns = _extract_rar(archive, output_dir, logger)
            warnings.extend(warns)

    # Phase 2: scan extracted/ for nested archives and extract recursively
    nested_warnings = _extract_nested(output_dir, output_dir, logger, depth=1)
    warnings.extend(nested_warnings)

    return warnings


def _extract_nested(root_dir: Path, output_dir: Path, logger,
                    depth: int = 1) -> List[dict]:
    """Recursively find and extract archives inside extracted/.

    Stops at MAX_NESTED_DEPTH to avoid infinite loops.
    """
    warnings: List[dict] = []
    if depth > MAX_NESTED_DEPTH:
        return warnings

    for archive_path in sorted(root_dir.rglob("*.zip")):
        # Skip archives that are hidden or in system dirs
        if any(p.startswith(".") for p in archive_path.parts):
            continue
        warns = _extract_zip(archive_path, output_dir, logger)
        warnings.extend(warns)
        # Remove the nested archive after extraction to avoid re-extraction
        try:
            archive_path.unlink()
        except Exception:
            pass

    for archive_path in sorted(root_dir.rglob("*.rar")):
        if any(p.startswith(".") for p in archive_path.parts):
            continue
        warns = _extract_rar(archive_path, output_dir, logger)
        warnings.extend(warns)
        try:
            archive_path.unlink()
        except Exception:
            pass

    # Recurse if there might be further nesting
    if depth < MAX_NESTED_DEPTH:
        more_warns = _extract_nested(root_dir, output_dir, logger, depth + 1)
        warnings.extend(more_warns)

    return warnings


def _extract_zip(zip_path: Path, output_dir: Path, logger) -> List[dict]:
    """Extract a ZIP file, tolerating per-file failures."""
    warnings: List[dict] = []
    target = output_dir / zip_path.stem
    target.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                try:
                    name = _decode_filename(info.filename)
                    out_path = (target / name).resolve()
                    # Prevent path traversal
                    if not str(out_path).startswith(str(target.resolve())):
                        warnings.append({
                            "file": str(zip_path),
                            "message": f"路径穿越已阻止: {info.filename}",
                        })
                        continue
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    if info.is_dir():
                        out_path.mkdir(parents=True, exist_ok=True)
                    else:
                        with zf.open(info) as src, open(out_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                except Exception as e:
                    warnings.append({
                        "file": str(zip_path),
                        "message": f"解压失败 '{info.filename}': {e}",
                    })
                    logger.warning("Extraction failed for %s in %s: %s",
                                   info.filename, zip_path.name, e)
    except Exception as e:
        warnings.append({
            "file": str(zip_path),
            "message": f"无法打开压缩包: {e}",
        })
        logger.warning("Failed to open archive %s: %s", zip_path.name, e)

    return warnings


def _decode_filename(raw_name: str) -> str:
    """Try to decode a ZIP filename; fall back to raw latin-1 if needed."""
    try:
        return raw_name.encode("cp437").decode("gbk")
    except Exception:
        try:
            return raw_name.encode("cp437").decode("utf-8")
        except Exception:
            return raw_name


def _extract_rar(rar_path: Path, output_dir: Path, logger) -> List[dict]:
    """Extract a RAR file using the `unrar` command-line tool."""
    warnings: List[dict] = []
    target = output_dir / rar_path.stem
    target.mkdir(parents=True, exist_ok=True)

    unrar_path = shutil.which("unrar")
    if not unrar_path:
        warnings.append({
            "file": str(rar_path),
            "message": "未找到 unrar 命令，无法解压 RAR 压缩包",
        })
        logger.warning("unrar not found, skipping extraction of %s", rar_path.name)
        return warnings

    try:
        result = subprocess.run(
            [unrar_path, "x", "-y", str(rar_path), str(target)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            warnings.append({
                "file": str(rar_path),
                "message": f"unrar 退出码 {result.returncode}: {result.stderr.strip()}",
            })
            logger.warning("unrar extraction failed for %s", rar_path.name)
    except Exception as e:
        warnings.append({
            "file": str(rar_path),
            "message": f"RAR 解压异常: {e}",
        })
        logger.warning("Exception extracting RAR %s: %s", rar_path.name, e)

    return warnings
