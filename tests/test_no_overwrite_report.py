"""Test that prepare does NOT overwrite preexam_report.md."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preexam.cli import cmd_prepare


def test_prepare_does_not_overwrite_report(tmp_path):
    """The prepare command should never overwrite preeaxm_report.md."""
    case_dir = tmp_path / "cases" / "OVERWRITE_TEST"
    input_dir = case_dir / "input"
    output_dir = case_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Create a dummy report with a sentinel
    report_path = output_dir / "preexam_report.md"
    report_path.write_text("EXISTING_REPORT_SENTINEL")

    with patch("preexam.cli.setup_case_logger") as mock_logger:
        mock_logger.return_value = MagicMock()
        cmd_prepare(str(case_dir))

    assert report_path.exists()
    content = report_path.read_text()
    assert "EXISTING_REPORT_SENTINEL" in content, "Report was overwritten!"


def test_prepare_creates_expected_output_structure(tmp_path):
    """Test that prepare creates all expected output files."""
    case_dir = tmp_path / "cases" / "STRUCTURE_TEST"
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True)

    # Add a dummy PDF to trigger some processing
    dummy = input_dir / "document.pdf"
    dummy.write_text("dummy pdf content")

    with patch("preexam.cli.setup_case_logger") as mock_logger:
        mock_logger.return_value = MagicMock()
        cmd_prepare(str(case_dir))

    # Verify output structure (skip log file check when logger is mocked)
    assert (case_dir / "output" / "file_manifest.txt").exists()
    assert (case_dir / "output" / "file_manifest.json").exists()
    assert (case_dir / "parsed" / "case_data.json").exists()
    assert (case_dir / "parsed" / "warnings.json").exists()
    assert (case_dir / "extracted").exists()
    assert (case_dir / "prompts").exists()

    # Verify the log file exists only if the real logger was set up
    # (When mocked, it won't create the file - this is expected)


def test_prepare_with_real_logger_creates_log(tmp_path):
    """With the real logger, logs/preexam.log should be created."""
    case_dir = tmp_path / "cases" / "LOG_TEST"
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True)

    dummy = input_dir / "test.pdf"
    dummy.write_text("dummy")

    # Run without mocking the logger
    cmd_prepare(str(case_dir))

    assert (case_dir / "logs" / "preexam.log").exists()
    log_content = (case_dir / "logs" / "preexam.log").read_text()
    assert "Starting prepare for case: LOG_TEST" in log_content
