"""Tests for CNIPA XML parsing."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from preexam.cnipa_xml import extract_case_data, write_case_data


# Minimal CNIPA-style XML samples

CLAIMS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <claims>
    <claim>
      <claim-text>一种智能终端，其特征在于，包括：处理器和存储器。</claim-text>
    </claim>
    <claim>
      <claim-text>根据权利要求1所述的智能终端，其特征在于，所述存储器为闪存。</claim-text>
    </claim>
    <claim>
      <claim-text>根据权利要求1所述的智能终端，其特征在于，所述处理器为多核处理器。</claim-text>
    </claim>
  </claims>
</document>
"""

SPEC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <body>
    <p>本发明涉及智能终端技术领域。</p>
    <p>本发明提供一种智能终端，包括处理器和存储器。</p>
  </body>
</document>
"""

ABSTRACT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <abstract>
    <p>本发明公开了一种智能终端，包括处理器和存储器。本发明具有结构简单、成本低的优点。</p>
  </abstract>
</document>
"""

REQUEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <invention-title>智能终端及其控制方法</invention-title>
  <applicant>华为技术有限公司</applicant>
  <inventor>张三</inventor>
  <patent-agency>北京XX专利代理有限公司</patent-agency>
  <patent-agent>李四</patent-agent>
  <early-publication>是</early-publication>
  <substantive-examination>是</substantive-examination>
</document>
"""


class TestExtractCaseData:
    def test_extract_basic_claims(self, tmp_path):
        logger = MagicMock()
        xml_file = tmp_path / "100001.xml"
        xml_file.write_text(CLAIMS_XML)
        data, warnings = extract_case_data([xml_file], logger)

        assert data["claim_count"] == 3
        assert len(data["independent_claims"]) == 1
        assert data["independent_claims"][0]["number"] == 1

    def test_extract_specification(self, tmp_path):
        logger = MagicMock()
        xml_file = tmp_path / "100002.xml"
        xml_file.write_text(SPEC_XML)
        data, warnings = extract_case_data([xml_file], logger)

        assert data["specification_paragraph_count"] == 2

    def test_extract_abstract(self, tmp_path):
        logger = MagicMock()
        xml_file = tmp_path / "100004.xml"
        xml_file.write_text(ABSTRACT_XML)
        data, warnings = extract_case_data([xml_file], logger)

        assert data["abstract"] is not None
        assert "智能终端" in data["abstract"]

    def test_extract_request_form(self, tmp_path):
        logger = MagicMock()
        xml_file = tmp_path / "110101.xml"
        xml_file.write_text(REQUEST_XML)
        data, warnings = extract_case_data([xml_file], logger)

        assert data["title"] == "智能终端及其控制方法"
        assert data["applicant"] == "华为技术有限公司"
        assert data["inventor"] == "张三"
        assert data["agent_company"] == "北京XX专利代理有限公司"
        assert data["agent"] == "李四"
        assert data["early_publication"] == "是"
        assert data["substantive_examination"] == "是"

    def test_extract_unparseable_xml(self, tmp_path):
        logger = MagicMock()
        xml_file = tmp_path / "100001.xml"
        xml_file.write_text("not xml")
        data, warnings = extract_case_data([xml_file], logger)
        assert len(warnings) == 1
        assert "Failed to parse XML" in warnings[0]["message"]


class TestWriteCaseData:
    def test_write_data_and_warnings(self, tmp_path):
        logger = MagicMock()
        case_dir = tmp_path / "case"
        case_dir.mkdir()

        data = {"title": "测试发明", "claim_count": 3}
        warnings = [{"file": "test.xml", "message": "测试警告"}]

        write_case_data(data, warnings, case_dir, logger)

        parsed_dir = case_dir / "parsed"
        assert (parsed_dir / "case_data.json").exists()
        assert (parsed_dir / "warnings.json").exists()

        with open(parsed_dir / "case_data.json") as f:
            loaded = json.load(f)
        assert loaded["title"] == "测试发明"
