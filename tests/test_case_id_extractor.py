"""Tests for case ID extraction from multiple sources."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preexam.case_id_extractor import (
    extract_case_id,
    extract_from_110101_xml,
    extract_from_filename,
    safety_case_id,
    generate_case_id,
    resolve_case_dir,
)


class TestSafetyCaseId:
    def test_basic_safety(self):
        assert safety_case_id("  Hello World  ") == "Hello-World"

    def test_removes_illegal_chars(self):
        assert safety_case_id("a/b:c*d?e") == "a-b-c-d-e"

    def test_preserves_chinese(self):
        result = safety_case_id("7300 快审 XRC")
        assert "快审" in result
        assert result == "7300-快审-XRC"

    def test_collapses_hyphens(self):
        assert safety_case_id("a---b---c") == "a-b-c"

    def test_truncates_long(self):
        long_str = "a" * 200
        assert len(safety_case_id(long_str)) <= 100

    def test_empty_string(self):
        assert safety_case_id("") == ""
        assert safety_case_id("   ") == ""


class TestExtractFrom110101XML:
    def test_extract_internal_number(self, tmp_path):
        """从 110101.xml 提取 <内部编号>"""
        xml = tmp_path / "110101.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<发明专利请求书>"
            "  <内部编号>7300 快审 XRC</内部编号>"
            "</发明专利请求书>"
        )
        cid, src = extract_from_110101_xml(xml)
        assert cid == "7300-快审-XRC"
        assert "内部编号" in src

    def test_xml_without_number(self, tmp_path):
        """XML without internal number should return None."""
        xml = tmp_path / "110101.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<发明专利请求书><发明名称>测试</发明名称></发明专利请求书>"
        )
        cid, src = extract_from_110101_xml(xml)
        assert cid is None

    def test_unparseable_xml(self, tmp_path):
        xml = tmp_path / "110101.xml"
        xml.write_text("not xml")
        cid, _ = extract_from_110101_xml(xml)
        assert cid is None


class TestExtractFromFilename:
    def test_patent_code_with_suffix(self, tmp_path):
        """PY25DX39653FNPC-CN快审修改.zip → PY25DX39653FNPC-CN"""
        f = tmp_path / "PY25DX39653FNPC-CN快审修改.zip"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        assert cid == "PY25DX39653FNPC-CN"
        assert "文件名" in src

    def test_long_code_with_plus(self, tmp_path):
        """YS01220251003740+阻尼器.pdf → YS01220251003740"""
        f = tmp_path / "YS01220251003740+阻尼器及其工作方法+江苏容大减震科技股份有限公司.pdf"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        assert cid == "YS01220251003740"

    def test_short_code_with_plus(self, tmp_path):
        """7300+快审+XRC.zip → 7300"""
        f = tmp_path / "7300+快审+XRC.zip"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        assert cid == "7300"

    def test_eight_digit_number(self, tmp_path):
        """10010315.zip → 10010315"""
        f = tmp_path / "10010315.zip"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        assert cid == "10010315"

    def test_hyphenated_code(self, tmp_path):
        """ALPHA-BETA-123.zip → ALPHA-BETA-123"""
        f = tmp_path / "ALPHA-BETA-123.zip"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        assert cid == "ALPHA-BETA-123"

    def test_no_match(self, tmp_path):
        """No match should return None."""
        f = tmp_path / "readme.txt"
        f.write_text("dummy")
        cid, _ = extract_from_filename(f)
        assert cid is None


class TestExtractFromFilenameSearch:
    def test_chinese_prefix_ys_code(self, tmp_path):
        """申请文件YS01220251003740+... → YS01220251003740"""
        f = tmp_path / "申请文件YS01220251003740+阻尼器及其工作方法+江苏容大减震科技股份有限公司.pdf"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        assert cid == "YS01220251003740"
        assert "搜索" in src or "文件名" in src

    def test_chinese_prefix_digits(self, tmp_path):
        f = tmp_path / "附件材料20260608-001.zip"
        f.write_text("dummy")
        cid, src = extract_from_filename(f)
        # Should match 8-digit sequence
        assert cid == "20260608"


class TestExtractCaseId:
    def test_priority_1_xml_wins(self, tmp_path):
        """110101.xml should take priority over filename."""
        xml = tmp_path / "110101.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<发明专利请求书>"
            "  <内部编号>XML-CASE-001</内部编号>"
            "</发明专利请求书>"
        )
        pdf = tmp_path / "10010315.pdf"
        pdf.write_text("dummy")
        cid, src = extract_case_id([xml, pdf])
        assert cid == "XML-CASE-001"

    def test_priority_3_filename(self, tmp_path):
        """Filename extraction when no XML."""
        f = tmp_path / "PY25DX39653FNPC-CN-申请.pdf"
        f.write_text("dummy")
        cid, src = extract_case_id([f])
        assert cid == "PY25DX39653FNPC-CN"

    def test_priority_4_auto_generate(self, tmp_path):
        """Auto-generate when nothing matches."""
        f = tmp_path / "notes.txt"
        f.write_text("dummy")
        cid, src = extract_case_id([f])
        assert cid.startswith("CASE-")
        assert "自动" in src

    def test_empty_file_list(self, tmp_path):
        """Empty list should auto-generate."""
        cid, src = extract_case_id([])
        assert cid.startswith("CASE-")
        assert "自动" in src


class TestGenerateCaseId:
    def test_returns_timestamped_id(self):
        cid, src = generate_case_id()
        assert cid.startswith("CASE-")
        assert "自动" in src
        # Should have date components
        parts = cid.split("-")
        assert len(parts) >= 3  # CASE-YYYYMMDD-HHMMSS


class TestResolveCaseDir:
    def test_new_directory(self, tmp_path):
        path, cid, modified = resolve_case_dir(tmp_path, "NEW-CASE")
        assert path.name == "NEW-CASE"
        assert not modified

    def test_existing_empty_directory(self, tmp_path):
        (tmp_path / "EXISTING").mkdir()
        path, cid, modified = resolve_case_dir(tmp_path, "EXISTING")
        assert cid == "EXISTING"
        assert not modified  # Reuse existing empty dir

    def test_existing_with_input_appends_suffix(self, tmp_path):
        existing = tmp_path / "EXISTING"
        (existing / "input").mkdir(parents=True)
        (existing / "input" / "test.pdf").write_text("dummy")
        path, cid, modified = resolve_case_dir(tmp_path, "EXISTING")
        assert cid != "EXISTING"
        assert cid.startswith("EXISTING-")
        assert modified


class TestSafetyEdgeCases:
    def test_only_special_chars(self):
        assert safety_case_id("///***???") == ""

    def test_mixed_content(self):
        result = safety_case_id("Case_123-测试_File")
        assert "_" in result or "-" in result
        assert "测试" in result
        assert len(result) > 0

    def test_leading_trailing_hyphens(self):
        assert safety_case_id("-hello-") == "hello"
        assert safety_case_id("--world--") == "world"
