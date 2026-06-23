"""Tests for the Phase 2 report generator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from preexam.report_generator import ReportGenerator


@pytest.fixture
def mock_logger():
    return MagicMock()


def _write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _setup_basic_case(case_dir: Path) -> None:
    """Set up a minimal case with all required data files."""
    _write_json(case_dir / "parsed" / "case_data.json", {
        "title": "测试发明",
        "applicant": "测试公司",
        "inventor": "张三",
        "agent_company": "测试代理所",
        "agent": "李四",
        "claim_count": 3,
        "independent_claims": [{"number": 1, "text": "c1", "is_independent": True}],
        "abstract": "摘要",
        "specification_paragraph_count": 10,
        "early_publication": "是",
        "substantive_examination": True,
    })
    _write_json(case_dir / "output" / "file_manifest.json", [
        {"path": "input/100001.xml", "file_type": "xml", "role": "claims",
         "description": "Claims", "source": "cnipa_xml"},
        {"path": "input/100002.xml", "file_type": "xml", "role": "specification",
         "description": "Spec", "source": "cnipa_xml"},
        {"path": "input/100003.xml", "file_type": "xml", "role": "drawings",
         "description": "Drawings", "source": "cnipa_xml"},
        {"path": "input/100004.xml", "file_type": "xml", "role": "abstract",
         "description": "Abstract", "source": "cnipa_xml"},
    ])
    _write_json(case_dir / "parsed" / "rule_findings.json", [
        {"rule_id": "R001", "rule_name": "早日公布", "category": "请求书检查",
         "severity": "medium", "passed": True, "message": "已勾选", "details": ""},
        {"rule_id": "C001", "rule_name": "承诺书存在", "category": "承诺书检查",
         "severity": "high", "passed": False, "message": "未找到", "details": ""},
    ])
    _write_json(case_dir / "parsed" / "manual_review_items.json", [
        {"rule_id": "C002", "item": "签章确认", "reason": "需人工确认",
         "file": "test.pdf", "details": "确认盖章"},
    ])


class TestReportGeneratorInit:
    def test_loads_data(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        result = rg.load_data()
        assert result is True
        assert rg._case_data["title"] == "测试发明"
        assert len(rg._manifest_entries) == 4
        assert len(rg._findings) == 2
        assert len(rg._manual_items) == 1

    def test_missing_data_returns_false(self, tmp_path, mock_logger):
        rg = ReportGenerator(tmp_path, mock_logger)
        result = rg.load_data()
        assert result is False

    def test_optional_data_missing_still_loads(self, tmp_path, mock_logger):
        """rule_findings.json and manual_review_items.json are optional."""
        _write_json(tmp_path / "parsed" / "case_data.json", {"title": "T"})
        _write_json(tmp_path / "output" / "file_manifest.json", [])
        rg = ReportGenerator(tmp_path, mock_logger)
        result = rg.load_data()
        assert result is True
        assert rg._findings == []
        assert rg._manual_items == []


class TestReportContent:
    def test_contains_required_sections(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        report = rg.generate()

        required_sections = [
            "快速预审内部审查报告",
            "案卷基本信息",
            "文件完整性审查",
            "规则审查结果",
            "需人工确认事项",
            "预审员填写区",
            "文件完整性审查意见",
            "形式审查意见",
            "三性初步判断",
            "审查意见",
            "备注",
            "不构成最终审查结论",
            "国家知识产权局实质审查结果",
        ]
        for section in required_sections:
            assert section in report, f"Missing section: {section}"

    def test_metadata_table_populated(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        report = rg.generate()
        assert "测试发明" in report
        assert "测试公司" in report
        assert "张三" in report
        assert "3" in report or "3" in report

    def test_manual_items_displayed(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        report = rg.generate()
        assert "需人工确认" in report
        assert "C002" in report or "签章" in report

    def test_no_manual_items_shows_none(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        # Clear manual items
        _write_json(tmp_path / "parsed" / "manual_review_items.json", [])
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        report = rg.generate()
        assert "（无）" in report


class TestReportOutput:
    def test_writes_to_output_report_md(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        path = rg.write_output()
        assert path.name == "report.md"
        assert path.exists()
        content = path.read_text()
        assert "快速预审内部审查报告" in content
        assert len(content) > 500

    def test_does_not_overwrite_preexam_report(self, tmp_path, mock_logger):
        """report command must not create or overwrite preexam_report.md."""
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        rg.write_output()
        preexam = tmp_path / "output" / "preexam_report.md"
        assert not preexam.exists()


class TestFileCompleteness:
    def test_table_lists_required_documents(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        report = rg.generate()
        # Should contain CNIPA document code rows
        assert "100001" in report or "权利要求书" in report
        assert "承诺书" in report or "文件类型" in report

    def test_placeholder_sections_exist(self, tmp_path, mock_logger):
        _setup_basic_case(tmp_path)
        rg = ReportGenerator(tmp_path, mock_logger)
        rg.load_data()
        report = rg.generate()
        assert "（请在此处填写" in report
        # Count placeholder sections
        placeholders = report.count("（请在此处填写")
        assert placeholders >= 4  # 4 main review sections


class TestIntegration:
    def test_with_real_10010315(self, mock_logger):
        """Integration test using real prepared case data."""
        p = Path.home() / "Projects" / "patent-preexam-system" / "cases" / "10010315"
        if not (p / "parsed" / "case_data.json").exists():
            pytest.skip("10010315 case not prepared — run prepare first")
        rg = ReportGenerator(p, mock_logger)
        rg.load_data()
        report = rg.generate()
        assert "阻尼器" in report
        assert "江苏容大" in report
        assert "预审员填写区" in report
        assert "不构成最终审查结论" in report
        assert "三性初步判断" in report
