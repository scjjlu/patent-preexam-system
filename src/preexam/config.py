"""Project-wide configuration and path resolution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Project root resolution: walk up to find pyproject.toml
_PROJECT_ROOT: Optional[Path] = None


def _find_project_root() -> Path:
    """Find the project root.

    Resolution order:
    1. PREEXAM_ROOT environment variable (used by PyInstaller bundle)
    2. Walk up from cwd looking for pyproject.toml
    3. Fallback: cwd
    """
    # Priority 1: environment variable override (used by PyInstaller bundle)
    env_root = os.environ.get("PREEXAM_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "pyproject.toml").exists():
            return candidate
        # Even without pyproject.toml, trust the env var
        return candidate

    # Priority 2: walk up from cwd
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback: assume we're running from the project root
    return cwd


def get_project_root() -> Path:
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = _find_project_root()
    return _PROJECT_ROOT


def get_rules_dir() -> Path:
    return get_project_root() / "rules"


def get_templates_dir() -> Path:
    return get_project_root() / "templates"


def get_cases_dir() -> Path:
    return get_project_root() / "cases"


# Case subdirectory names
EXTRACTED = "extracted"
PARSED = "parsed"
PROMPTS = "prompts"
OUTPUT = "output"
LOGS = "logs"
INPUT = "input"
INCOMING = "_incoming"

# Supported input file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".zip", ".rar", ".xml", ".jpg", ".jpeg", ".png", ".docx", ".doc"}

# Archive file extensions
ARCHIVE_EXTENSIONS = {".zip", ".rar"}

# Image file extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
