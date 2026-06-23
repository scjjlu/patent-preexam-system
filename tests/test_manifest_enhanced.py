"""Tests for enhanced file role detection and multi-file input."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preexam.manifest import (
    classify_file, generate_manifest,
    _detect_role_by_filename, _inspect_zip_keywords,
)
from preexam.archive import extract_archives
from preexam.case_manager import CaseManager
from preexam.cli import cmd_clean, cmd_prepare


class TestRoleByFilename:
    def test_commitment_pdf(self, tmp_path):
        f = tmp_path / "承诺书.pdf"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "commitment"

    def test_self_check_jpg(self, tmp_path):
        f = tmp_path / "自检表.jpg"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "self_check"

    def test_filing_notice_pdf(self, tmp_path):
        f = tmp_path / "备案通知书.pdf"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "filing_notice"

    def test_identity_document_pdf(self, tmp_path):
        f = tmp_path / "身份证明.pdf"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "identity_document"

    def test_quick_exam_zip(self, tmp_path):
        f = tmp_path / "快审修改.zip"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "quick_exam_package"

    def test_application_pdf(self, tmp_path):
        f = tmp_path / "申请文件.pdf"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "application_pdf"

    def test_unknown_file(self, tmp_path):
        f = tmp_path / "random.xyz"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "unknown"

    def test_auxiliary_xml(self, tmp_path):
        f = tmp_path / "list.xml"
        f.write_text("<xml/>")
        role, desc, source = classify_file(f)
        assert role == "auxiliary_xml"

    def test_cnipa_claims_xml(self, tmp_path):
        f = tmp_path / "100001.xml"
        f.write_text("<xml/>")
        role, desc, source = classify_file(f)
        assert role == "claims"


class TestZIPContentInspection:
    def test_commitment_zip_by_content(self, tmp_path):
        """ZIP containing commitment-related files should be detected."""
        zip_path = tmp_path / "附件.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("承诺书.jpg", "fake image content")
        role, desc, source = _inspect_zip_keywords(zip_path)
        assert role == "commitment_package"

    def test_self_check_zip_by_content(self, tmp_path):
        zip_path = tmp_path / "材料.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("自检表.png", "fake image")
        role, desc, source = _inspect_zip_keywords(zip_path)
        assert role == "self_check_package"

    def test_quick_exam_zip_by_content(self, tmp_path):
        zip_path = tmp_path / "修改包.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("快审修改内容.txt", "changes")
        role, desc, source = _inspect_zip_keywords(zip_path)
        assert role == "quick_exam_package"

    def test_unreadable_zip_returns_none(self, tmp_path):
        """Corrupt ZIP should not crash."""
        zip_path = tmp_path / "bad.zip"
        zip_path.write_text("not a zip")
        result = _inspect_zip_keywords(zip_path)
        assert result is None


class TestNestedZIPExtraction:
    def test_nested_zip_is_extracted(self, tmp_path):
        """A ZIP inside another ZIP should be extracted."""
        # Create inner ZIP
        inner_path = tmp_path / "inner.zip"
        with zipfile.ZipFile(inner_path, "w") as zf:
            zf.writestr("inner_file.txt", "hello")

        # Create outer ZIP containing inner.zip
        outer_path = tmp_path / "outer.zip"
        with zipfile.ZipFile(outer_path, "w") as zf:
            zf.write(inner_path, "nested/inner.zip")

        output_dir = tmp_path / "extracted"
        logger = MagicMock()
        warnings = extract_archives([outer_path], output_dir, logger)

        # The nested inner.zip should have been extracted
        # Look for inner_file.txt anywhere in output_dir
        extracted_files = list(output_dir.rglob("*"))
        extracted_names = [str(f.relative_to(output_dir)) for f in extracted_files if f.is_file()]
        assert any("inner_file" in n for n in extracted_names), \
            f"Nested file not found in {extracted_names}"


class TestCleanCommand:
    def test_clean_removes_output_keeps_input(self, tmp_path):
        """clean should remove generated dirs but keep input/."""
        case_dir = tmp_path / "cases" / "CLEAN_TEST"
        input_dir = case_dir / "input"
        output_dir = case_dir / "output"
        parsed_dir = case_dir / "parsed"
        logs_dir = case_dir / "logs"
        input_dir.mkdir(parents=True)
        output_dir.mkdir()
        parsed_dir.mkdir()
        logs_dir.mkdir()

        # Create a dummy input file
        (input_dir / "test.pdf").write_text("dummy")
        # Create a dummy preexam_report.md
        (output_dir / "preexam_report.md").write_text("protected")
        # Create a removable output
        (output_dir / "file_manifest.txt").write_text("removable")

        logger = MagicMock()
        with patch("preexam.cli.setup_case_logger") as mock_log:
            mock_log.return_value = logger
            ret = cmd_clean(str(case_dir))

        assert ret == 0
        # input/ untouched
        assert input_dir.exists()
        assert (input_dir / "test.pdf").exists()
        # preexam_report.md preserved
        assert (output_dir / "preexam_report.md").exists()
        assert (output_dir / "preexam_report.md").read_text() == "protected"
        # removable file cleaned
        assert not (output_dir / "file_manifest.txt").exists()


class TestManifestWithMultipleInputs:
    def test_manifest_generated_with_multiple_roles(self, tmp_path):
        """Test that manifest generation works with various input types."""
        case_dir = tmp_path / "cases" / "MULTI_INPUT"
        input_dir = case_dir / "input"
        input_dir.mkdir(parents=True)

        # Create multiple input files
        (input_dir / "申请文件.pdf").write_text("app")
        (input_dir / "承诺书.jpg").write_text("commit")
        (input_dir / "快审修改.zip").write_text("quick")
        (input_dir / "100001.xml").write_text("<xml/>")

        logger = MagicMock()
        with patch("preexam.cli.setup_case_logger") as mock_log:
            mock_log.return_value = logger
            cmd_prepare(str(case_dir))

        manifest_path = case_dir / "output" / "file_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            entries = json.load(f)

        roles = {e["role"] for e in entries}
        assert "application_pdf" in roles
        assert "commitment" in roles
        assert "quick_exam_package" in roles
        assert "claims" in roles


class TestStreamlitImport:
    def test_streamlit_module_can_be_imported(self):
        """The streamlit UI module should import without errors."""
        try:
            import preexam.ui_streamlit as ui
            assert ui is not None
        except ImportError as e:
            # If streamlit is not installed, this is also acceptable
            if "streamlit" in str(e).lower():
                pytest.skip("streamlit not installed")
            else:
                raise


class TestInputReadOnly:
    def test_input_files_not_modified(self, tmp_path):
        """prepare must not modify, move, or delete input/ files."""
        case_dir = tmp_path / "cases" / "READONLY"
        input_dir = case_dir / "input"
        input_dir.mkdir(parents=True)

        original = "original content — do not touch"
        f = input_dir / "test.pdf"
        f.write_text(original)

        logger = MagicMock()
        with patch("preexam.cli.setup_case_logger") as mock_log:
            mock_log.return_value = logger
            cmd_prepare(str(case_dir))

        assert f.exists(), "input file was deleted!"
        assert f.read_text() == original, "input file was modified!"


class TestClassifyExtractedFile:
    def test_commitment_image_inside_extracted(self, tmp_path):
        from preexam.manifest import classify_extracted_file
        # Simulate a file extracted from a commitment package
        f = tmp_path / "extracted" / "承诺书" / "scan.jpg"
        f.parent.mkdir(parents=True)
        f.write_text("dummy")
        role = classify_extracted_file(f)
        assert role == "commitment"
