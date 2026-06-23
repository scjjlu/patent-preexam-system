"""Logging utilities for the preexam system.

All logs are written to the case-specific logs/ directory.
"""

import logging
import sys
from pathlib import Path


def setup_case_logger(case_dir: Path, name: str = "preexam") -> logging.Logger:
    """Set up a logger that writes to case_dir/logs/ and stdout.

    Returns:
        Configured logger instance.
    """
    log_dir = case_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "preexam.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    # File handler — detailed debug
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Console handler — info and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
