"""Tests for the Phase 2 rule-based check engine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from preexam.rules_engine import RuleEngine


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_logger():
    return MagicMock()


def _write_case_data(case_dir: Path, data: dict) -> Path:
    p = case_dir / "parsed" / "case_data.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def _write_manifest(case_dir: Path, entries: list) -> Path:
    p = case_dir / "output" / "file_manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return p


def _make_engine(case_dir: Path, logger, case_data: dict = None,
                 manifest_entries: list = None) -> RuleEngine:
    """Create a properly initialized RuleEngine with loaded data."""
    if case_data is None:
        case_data = {
            "title": "测试专利", "early_publication": "是",
            "substantive_examination": True, "claim_count": 3,
            "independent_claims": [{"number": 1, "text": "测试", "is_independent": True}],
        }
    if manifest_entries is None:
        manifest_entries = [
            {"path": "input/100001.xml", "file_type": "xml", "role": "claims"},
            {"path": "input/110101.xml", "file_type": "xml", "role": "request_form"},
        ]

    _write_case_data(case_dir, case_data)
    _write_manifest(case_dir, manifest_entries)

    engine = RuleEngine(case_dir, logger)
    engine.load_data()
    return engine


# ── Tests ───────────────────────────────────────────────────────────

class TestRuleEngineInit:
    def test_loads_rule_defs(self, tmp_path, mock_logger):
        """RuleEngine loads check_rules.yaml at init."""
        engine = RuleEngine(tmp_path, mock_logger)
        assert len(engine.rule_defs) >= 10  # All 10 rules present
        assert "R001" in engine.rule_defs
        assert "D002" in engine.rule_defs

    def test_loads_data(self, tmp_path, mock_logger):
        """load_data reads case_data.json and file_manifest.json."""
        engine = _make_engine(tmp_path, mock_logger)
        assert engine._case_data["title"] == "测试专利"
        assert len(engine._manifest_entries) == 2


class TestR001:
    def test_early_publication_yes(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              case_data={"early_publication": "是"})
        engine.run_all()
        r001 = [f for f in engine.findings if f["rule_id"] == "R001"]
        assert len(r001) == 1
        assert r001[0]["passed"] is True

    def test_early_publication_missing(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              case_data={})
        engine.run_all()
        r001 = [f for f in engine.findings if f["rule_id"] == "R001"]
        assert len(r001) == 1
        assert r001[0]["passed"] is False


class TestR002:
    def test_substantive_examination_present(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              case_data={"substantive_examination": True},
                              manifest_entries=[{"path": "input/110401.xml"}])
        engine.run_all()
        r002 = [f for f in engine.findings if f["rule_id"] == "R002"]
        assert len(r002) == 1
        assert r002[0]["passed"] is True

    def test_no_110401_no_field(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              case_data={},
                              manifest_entries=[])
        engine.run_all()
        r002 = [f for f in engine.findings if f["rule_id"] == "R002"]
        assert len(r002) == 1
        assert r002[0]["passed"] is False


class TestR003:
    def test_no_same_day(self, tmp_path, mock_logger):
        """No 110101.xml should result in a pass (skip)."""
        engine = _make_engine(tmp_path, mock_logger)
        engine.run_all()
        r003 = [f for f in engine.findings if f["rule_id"] == "R003"]
        assert len(r003) == 0 or r003[0]["passed"] is True


class TestC001:
    def test_commitment_exists(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              manifest_entries=[{"path": "input/承诺书.pdf"}])
        engine.run_all()
        c001 = [f for f in engine.findings if f["rule_id"] == "C001"]
        assert len(c001) == 1
        assert c001[0]["passed"] is True

    def test_commitment_missing(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              manifest_entries=[])
        engine.run_all()
        c001 = [f for f in engine.findings if f["rule_id"] == "C001"]
        assert len(c001) == 1
        assert c001[0]["passed"] is False


class TestC002:
    def test_commitment_image_triggers_manual(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              manifest_entries=[{"path": "input/承诺书.jpg",
                                                  "file_type": "jpg"}])
        engine.run_all()
        c002 = [f for f in engine.findings if f["rule_id"] == "C002"]
        assert len(c002) >= 1
        assert not c002[0]["passed"]
        # Should also create a manual review item
        assert any(item["rule_id"] == "C002" for item in engine.manual_items)

    def test_commitment_pdf_triggers_manual(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              manifest_entries=[{"path": "input/承诺书.pdf",
                                                  "file_type": "pdf"}])
        engine.run_all()
        c002 = [f for f in engine.findings if f["rule_id"] == "C002"]
        assert len(c002) >= 1
        assert not c002[0]["passed"]


class TestX001:
    def test_all_xml_known(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              manifest_entries=[
                                  {"path": "input/100001.xml", "file_type": "xml"},
                                  {"path": "input/100002.xml", "file_type": "xml"},
                              ])
        engine.run_all()
        x001 = [f for f in engine.findings if f["rule_id"] == "X001"]
        assert len(x001) == 1
        assert x001[0]["passed"] is True

    def test_unknown_xml_code(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              manifest_entries=[
                                  {"path": "input/999999.xml", "file_type": "xml"},
                              ])
        engine.run_all()
        x001 = [f for f in engine.findings if f["rule_id"] == "X001"]
        assert len(x001) == 1
        assert x001[0]["passed"] is False


class TestQ001:
    def test_continuous_claims(self, tmp_path, mock_logger):
        """Without a real 100001.xml, it falls back to independent_claims from case_data."""
        engine = _make_engine(tmp_path, mock_logger,
                              case_data={"independent_claims": [
                                  {"number": 1, "text": "c1", "is_independent": True},
                              ]})
        engine.run_all()
        q001 = [f for f in engine.findings if f["rule_id"] == "Q001"]
        assert len(q001) == 1


class TestQ002:
    def test_no_claims(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger,
                              case_data={"independent_claims": []})
        engine.run_all()
        q002 = [f for f in engine.findings if f["rule_id"] == "Q002"]
        assert len(q002) == 1


class TestD001:
    def test_no_spec(self, tmp_path, mock_logger):
        """No 100002.xml should pass gracefully."""
        engine = _make_engine(tmp_path, mock_logger)
        engine.run_all()
        d001 = [f for f in engine.findings if f["rule_id"] == "D001"]
        assert len(d001) == 0 or d001[0]["passed"] is True


class TestD002:
    def test_no_paragraphs(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger)
        engine.run_all()
        d002 = [f for f in engine.findings if f["rule_id"] == "D002"]
        assert len(d002) == 0 or d002[0]["passed"] is True


class TestOutput:
    def test_writes_all_output_files(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger)
        engine.run_all()
        engine.write_output()

        assert (tmp_path / "parsed" / "rule_findings.json").exists()
        assert (tmp_path / "parsed" / "manual_review_items.json").exists()
        assert (tmp_path / "output" / "rule_check_report.md").exists()

        # Verify JSON content
        with open(tmp_path / "parsed" / "rule_findings.json") as f:
            findings = json.load(f)
        assert len(findings) >= 10

        with open(tmp_path / "parsed" / "manual_review_items.json") as f:
            manuals = json.load(f)
        assert isinstance(manuals, list)

        # Verify report is not empty
        report = (tmp_path / "output" / "rule_check_report.md").read_text()
        assert len(report) > 100
        assert "规则审查报告" in report

    def test_report_contains_pass_fail_counts(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger)
        engine.run_all()
        engine.write_output()
        report = (tmp_path / "output" / "rule_check_report.md").read_text()
        assert "通过" in report
        assert "未通过" in report
        assert "需人工确认" in report


class TestManualReviewItems:
    def test_manual_review_creates_finding_and_item(self, tmp_path, mock_logger):
        engine = _make_engine(tmp_path, mock_logger)
        engine._add_manual("C002", item="签章确认",
                           reason="需人工确认", file="test.jpg", details="")
        assert len(engine.manual_items) == 1
        manual_item = engine.manual_items[0]
        assert manual_item["item"] == "签章确认"

        # Should also create a failed finding
        manual_findings = [f for f in engine.findings
                           if f["rule_id"] == "C002" and not f["passed"]]
        assert len(manual_findings) >= 1


class TestIntegrationScenarios:
    def test_complete_case_10010315(self, real_10010315_dir, mock_logger):
        """Integration test with real case data."""
        engine = RuleEngine(real_10010315_dir, mock_logger)
        engine.load_data()
        findings, manuals = engine.run_all()

        # At minimum 10 rules should have run
        assert len(findings) >= 10

        # R001 should pass (早期公开始终有值)
        r001 = [f for f in findings if f["rule_id"] == "R001"]
        assert r001[0]["passed"] is True

        # R002 should pass (有实质审查请求书)
        r002 = [f for f in findings if f["rule_id"] == "R002"]
        assert r002[0]["passed"] is True

    def test_engine_handles_missing_data_gracefully(self, tmp_path, mock_logger):
        """Engine should not crash when case_data.json has missing fields."""
        engine = _make_engine(tmp_path, mock_logger, case_data={})
        try:
            findings, manuals = engine.run_all()
            assert len(findings) >= 10
        except Exception as e:
            pytest.fail(f"Engine raised exception with empty data: {e}")


# ── Fixture for real case ───────────────────────────────────────────

@pytest.fixture
def real_10010315_dir():
    """Point to the real 10010315 case, assumed to have been prepared already."""
    p = Path.home() / "Projects" / "patent-preexam-system" / "cases" / "10010315"
    if not (p / "parsed" / "case_data.json").exists():
        pytest.skip("10010315 case not prepared — run prepare first")
    return p
