"""Case directory management and file discovery."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Union

from . import config as cfg


class CaseManager:
    """Manages a single case directory: structure, file discovery, classifications."""

    def __init__(self, case_path: Union[str, Path]):
        self.case_dir = Path(case_path).resolve()
        self.case_id = self.case_dir.name

    # ── Directory helpers ──────────────────────────────────────────────

    def input_dir(self) -> Path:
        return self.case_dir / cfg.INPUT

    def extracted_dir(self) -> Path:
        return self.case_dir / cfg.EXTRACTED

    def parsed_dir(self) -> Path:
        return self.case_dir / cfg.PARSED

    def prompts_dir(self) -> Path:
        return self.case_dir / cfg.PROMPTS

    def output_dir(self) -> Path:
        return self.case_dir / cfg.OUTPUT

    def logs_dir(self) -> Path:
        return self.case_dir / cfg.LOGS

    def ensure_dirs(self) -> None:
        """Create all required output directories under the case directory."""
        for d in [self.case_dir, self.extracted_dir(), self.parsed_dir(),
                  self.prompts_dir(), self.output_dir(), self.logs_dir()]:
            d.mkdir(parents=True, exist_ok=True)

    # ── File discovery ─────────────────────────────────────────────────

    def scan_input_files(self) -> List[Path]:
        """Recursively scan input/ for supported files."""
        return _scan_dir(self.input_dir())

    def scan_extracted_files(self) -> List[Path]:
        """Recursively scan extracted/ for supported files."""
        return _scan_dir(self.extracted_dir())

    def scan_all_files(self) -> List[Path]:
        """All discovered files from input/ and extracted/."""
        return self.scan_input_files() + self.scan_extracted_files()

    def find_archive_files(self) -> List[Path]:
        """Find ZIP/RAR files in input/."""
        result = []
        for f in self.scan_input_files():
            if f.suffix.lower() in cfg.ARCHIVE_EXTENSIONS:
                result.append(f)
        return result

    def find_xml_files(self) -> List[Path]:
        """Find XML files in input/ and extracted/."""
        result = []
        for d in [self.input_dir(), self.extracted_dir()]:
            if d.exists():
                result.extend(d.rglob("*.xml"))
        return result

    def find_images(self) -> List[Path]:
        """Find image files in input/ and extracted/."""
        result = []
        for d in [self.input_dir(), self.extracted_dir()]:
            if d.exists():
                for ext in cfg.IMAGE_EXTENSIONS:
                    result.extend(d.rglob(f"*{ext}"))
        return result

    def case_dir_exists(self) -> bool:
        return self.case_dir.exists()

    # ── Clean ──────────────────────────────────────────────────────────

    def clean_output(self, force: bool = False) -> List[str]:
        """Remove generated output, preserving input/ and preexam_report.md.

        Returns list of removed paths (relative to case_dir).
        """
        removed: List[str] = []
        protected_files = {"output/preexam_report.md"}

        dirs_to_remove = [
            ("extracted/", self.extracted_dir()),
            ("parsed/", self.parsed_dir()),
            ("prompts/", self.prompts_dir()),
            ("logs/", self.logs_dir()),
        ]

        for label, d in dirs_to_remove:
            if d.exists():
                shutil.rmtree(d)
                removed.append(label)
                d.mkdir(parents=True, exist_ok=True)

        # Clean specific output files (not preexam_report.md)
        output_dir = self.output_dir()
        if output_dir.exists():
            for f in output_dir.iterdir():
                rel = f"output/{f.name}"
                if rel in protected_files and not force:
                    continue
                if f.is_file():
                    f.unlink()
                    removed.append(rel)
                elif f.is_dir():
                    shutil.rmtree(f)
                    removed.append(rel)

        return removed


def _scan_dir(directory: Path) -> List[Path]:
    """Recursively walk a directory and return supported file paths."""
    if not directory.exists():
        return []
    results: List[Path] = []
    for f in directory.rglob("*"):
        if f.is_file() and f.suffix.lower() in cfg.SUPPORTED_EXTENSIONS:
            results.append(f)
    return sorted(results)
