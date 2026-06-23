"""Tests for manifest generation."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from preexam.manifest import classify_file, generate_manifest
from preexam.case_manager import CaseManager


class TestClassifyFile:
    def test_classify_pdf(self, tmp_path):
        f = tmp_path / "document.pdf"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "pdf_document"

    def test_classify_xml(self, tmp_path):
        f = tmp_path / "100001.xml"
        f.write_text("<xml/>")
        role, desc, source = classify_file(f)
        assert role == "claims"

    def test_classify_zip(self, tmp_path):
        f = tmp_path / "archive.zip"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "zip_archive"

    def test_classify_rar(self, tmp_path):
        f = tmp_path / "archive.rar"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "rar_archive"

    def test_classify_unknown(self, tmp_path):
        f = tmp_path / "random.xyz"
        f.write_text("dummy")
        role, desc, source = classify_file(f)
        assert role == "unknown"


class TestGenerateManifest:
    def test_generate_manifest_empty(self, tmp_path):
        logger = MagicMock()
        case_dir = tmp_path / "cases" / "TEST001"
        case_dir.mkdir(parents=True)
        data = generate_manifest([], case_dir, logger)
        assert "entries" in data
        assert data["entries"] == []

        txt = case_dir / "output" / "file_manifest.txt"
        jsn = case_dir / "output" / "file_manifest.json"
        assert txt.exists()
        assert jsn.exists()

    def test_generate_manifest_with_files(self, tmp_path):
        logger = MagicMock()
        case_dir = tmp_path / "cases" / "TEST002"
        case_dir.mkdir(parents=True)

        # Create some files
        files = [
            case_dir / "input" / "100001.xml",
            case_dir / "input" / "document.pdf",
        ]
        for f in files:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("test")

        data = generate_manifest(files, case_dir, logger)
        assert len(data["entries"]) == 2

        jsn = case_dir / "output" / "file_manifest.json"
        with open(jsn) as f:
            loaded = json.load(f)
        assert len(loaded) == 2
        # One should be claims
        roles = {e["role"] for e in loaded}
        assert "claims" in roles
        assert "pdf_document" in roles
