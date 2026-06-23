"""规则化审查引擎 — Phase 2.

从 rules/check_rules.yaml 加载规则定义，对 case_data.json 和
file_manifest.json 执行检查，输出 rule_findings.json、
manual_review_items.json 和 rule_check_report.md。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from . import config as cfg
from .cnipa_xml import _parse_xml, _collect_text, _detect_namespace, _make_ns_map, _safe_find_all, _safe_find_text

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


class RuleEngine:
    """Rule engine that loads definitions from YAML and executes all checks."""

    def __init__(self, case_dir: Path, logger):
        self.case_dir = case_dir
        self.logger = logger
        self.findings: List[dict] = []
        self.manual_items: List[dict] = []

        # Load rule definitions
        self.rule_defs: Dict[str, dict] = {}
        self._load_rule_defs()

        # Data caches
        self._case_data: dict = {}
        self._manifest_entries: List[dict] = []
        self._raw_xml_roots: Dict[str, Any] = {}
        self._paragraphs: List[str] = []

    # ── Initialization ──────────────────────────────────────────────

    def _load_rule_defs(self) -> None:
        rules_path = cfg.get_rules_dir() / "check_rules.yaml"
        if rules_path.exists():
            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.rule_defs = data.get("rules", {})
            self.logger.info("Loaded %d rule definitions from check_rules.yaml", len(self.rule_defs))
        else:
            self.logger.warning("check_rules.yaml not found — no rules loaded")

    def load_data(self) -> None:
        """Load case_data.json and file_manifest.json from the case directory."""
        # case_data.json
        cd_path = self.case_dir / "parsed" / "case_data.json"
        if cd_path.exists():
            with open(cd_path, encoding="utf-8") as f:
                self._case_data = json.load(f)
            self.logger.info("Loaded case_data.json with %d fields", len(self._case_data))
        else:
            self.logger.warning("case_data.json not found — running with empty data")

        # file_manifest.json
        mf_path = self.case_dir / "output" / "file_manifest.json"
        if mf_path.exists():
            with open(mf_path, encoding="utf-8") as f:
                data = json.load(f)
            self._manifest_entries = data if isinstance(data, list) else data.get("entries", [])
            self.logger.info("Loaded file_manifest.json with %d entries", len(self._manifest_entries))
        else:
            self.logger.warning("file_manifest.json not found")

    def _get_xml_root(self, filename_pattern: str) -> Optional[Any]:
        """Find and parse an XML file matching the given filename pattern."""
        if filename_pattern in self._raw_xml_roots:
            return self._raw_xml_roots[filename_pattern]

        for d in [self.case_dir / "input", self.case_dir / "extracted"]:
            if d.exists():
                for f in d.rglob("*.xml"):
                    if filename_pattern in f.name:
                        root = _parse_xml(f)
                        if root is not None:
                            self._raw_xml_roots[filename_pattern] = root
                            return root
        return None

    def _get_xml_roots(self) -> Dict[str, Any]:
        """Return all cached XML roots, populating if needed."""
        return self._raw_xml_roots

    # ── Run all rules ───────────────────────────────────────────────

    def run_all(self) -> Tuple[List[dict], List[dict]]:
        """Execute all rules. Returns (findings, manual_items)."""
        self.logger.info("Starting rule check — %d rules loaded", len(self.rule_defs))

        for rid in sorted(self.rule_defs.keys()):
            method_name = f"_check_{rid.lower()}"
            method = getattr(self, method_name, None)
            if method is None:
                self.logger.warning("No implementation for rule %s, skipping", rid)
                continue
            try:
                method()
            except Exception as e:
                self.logger.error("Rule %s raised exception: %s", rid, e)
                self._add_finding(rid, passed=False, message=f"规则执行异常: {e}",
                                  details=str(e), _is_error=True)

        self._post_process_manual_items()
        self.logger.info("Rule check complete — %d findings, %d manual items",
                         len(self.findings), len(self.manual_items))
        return self.findings, self.manual_items

    # ── Findings helpers ────────────────────────────────────────────

    def _post_process_manual_items(self) -> None:
        """After all rules run, add manual review items for findings
        that need human confirmation even if the rule is not manual type."""
        # C001 fail → manual item
        c001 = next((f for f in self.findings if f["rule_id"] == "C001"), None)
        if c001 and not c001["passed"]:
            if not any(m["rule_id"] == "C001" for m in self.manual_items):
                self._add_manual_item("C001", item="承诺书文件缺失",
                    reason="承诺书文件缺失，请确认是否确未提交或需补充",
                    file="",
                    details="C001 检查未通过，文件清单中未找到名称含«承诺书»的文件")
        # D002 fail → manual item
        d002 = next((f for f in self.findings if f["rule_id"] == "D002"), None)
        if d002 and not d002["passed"]:
            if not any(m["rule_id"] == "D002" for m in self.manual_items):
                self._add_manual_item("D002", item="说明书重复段落/过短片段核查",
                    reason="D002 检出的重复段落或过短片段，请人工核查是否为真实缺陷或解析误报",
                    file="input/100002/100002.xml",
                    details=d002.get("details", "")[:300])


    def _add_finding(self, rule_id: str, *, passed: bool, message: str,
                     details: str = "", severity_override: Optional[str] = None,
                     _is_error: bool = False, _is_skipped: bool = False) -> None:
        """Add a finding with metadata from the rule definition."""
        rule_def = self.rule_defs.get(rule_id, {})
        if _is_skipped:
            severity = "skip"
        elif _is_error:
            severity = "error"
        else:
            severity = severity_override or rule_def.get("severity", "medium")
        self.findings.append({
            "rule_id": rule_id,
            "rule_name": rule_def.get("name", rule_id),
            "category": rule_def.get("category", ""),
            "severity": severity,
            "passed": passed,
            "message": message,
            "details": details,
        })

    def _add_manual(self, rule_id: str, *, item: str, reason: str,
                    file: str = "", details: str = "") -> None:
        """Add a manual review item (also creates a failed finding)."""
        rule_def = self.rule_defs.get(rule_id, {})
        self.manual_items.append({
            "rule_id": rule_id,
            "rule_name": rule_def.get("name", rule_id),
            "item": item,
            "reason": reason,
            "file": file,
            "details": details,
        })
        self._add_finding(rule_id, passed=False,
                          message=f"需人工确认 — {reason}",
                          details=details, severity_override="manual")

    def _add_manual_item(self, rule_id: str, *, item: str, reason: str,
                     file: str = "", details: str = "") -> None:
        """Add a manual review item only, without creating a new finding.
        Use when the finding already exists (e.g. from a non-manual rule)."""
        rule_def = self.rule_defs.get(rule_id, {})
        self.manual_items.append({
            "rule_id": rule_id,
            "rule_name": rule_def.get("name", rule_id),
            "item": item,
            "reason": reason,
            "file": file,
            "details": details,
        })


    # ── R001: 请求书应勾选早日公布 ─────────────────────────────────

    def _check_r001(self) -> None:
        ep = self._case_data.get("early_publication")
        passed = ep is not None and str(ep).strip() in ("是", "1", "True", "true")
        self._add_finding("R001", passed=passed,
                          message="已勾选早日公布" if passed else "未勾选「请求早日公布该专利申请」",
                          details=f"early_publication = {ep!r}")

    # ── R002: 应提交实质审查请求书 ──────────────────────────────────

    def _check_r002(self) -> None:
        se = self._case_data.get("substantive_examination")
        has_110401 = any("110401" in e.get("path", "") for e in self._manifest_entries)
        passed = bool(se) or has_110401
        self._add_finding("R002", passed=passed,
                          message="实质审查请求书已提交" if passed else "未检测到实质审查请求",
                          details=f"substantive_examination={se!r}, 110401_file={'存在' if has_110401 else '未找到'}")

    # ── R003: 不应声明同日申请实用新型 ──────────────────────────────

    def _check_r003(self) -> None:
        root = self._get_xml_root("110101")
        if root is None:
            self._add_finding("R003", passed=True, message="未找到 110101.xml，跳过检查",
                              details="110101.xml not found")
            return

        ns = _detect_namespace(root)
        ns_map_r003 = _make_ns_map(ns)
        # Look for <同日申请><声明本发明在同日申请实用新型 patent><附加>1</附加>
        same_day_el = root.find(".//同日申请" if not ns else ".//ns:同日申請",
                                 ns_map_r003 if ns else None)
        if same_day_el is None:
            # Try English-ish path
            same_day_el = root.find(".//same-day-application" if not ns else ".//ns:same-day-application",
                                     ns_map_r003 if ns else None)

        if same_day_el is not None:
            text = _collect_element_text(same_day_el)
            if any(kw in text for kw in ("1", "是", "true")):
                self._add_manual("R003", item="同日申请实用新型声明",
                                 reason="请求书中声明了同日申请实用新型，快速预审案件需人工确认",
                                 file="110101.xml", details=f"同日申请段落内容: {text[:200]}")
                return

        self._add_finding("R003", passed=True,
                          message="未声明同日申请实用新型",
                          details="同日申请段落为空或不存在")

    # ── C001: 承诺书文件应存在 ──────────────────────────────────────

    def _check_c001(self) -> None:
        commitment_files = [
            e for e in self._manifest_entries
            if "承诺书" in e.get("path", "") or "commitment" in e.get("path", "").lower()
        ]
        if commitment_files:
            self._add_finding("C001", passed=True,
                              message=f"承诺书文件存在: {commitment_files[0]['path']}",
                              details=f"共 {len(commitment_files)} 个承诺书相关文件")
        else:
            self._add_finding("C001", passed=False,
                              message="未找到承诺书文件",
                              details="文件清单中未包含名称含「承诺书」的文件")

    # ── C002: 承诺书为图片扫描件时需人工确认 ────────────────────────

    def _check_c002(self) -> None:
        commitment_files = [
            e for e in self._manifest_entries
            if "承诺书" in e.get("path", "") or "commitment" in e.get("path", "").lower()
        ]
        if not commitment_files:
            self._add_finding("C002", passed=False,
                              message="未找到承诺书文件，无法核查扫描件盖章和日期",
                              details="承诺书不存在，C002 跳过检查",
                              _is_skipped=True)
            return
        for entry in commitment_files:
            ftype = entry.get("file_type", "")
            if ftype in ("jpg", "jpeg", "png"):
                self._add_manual("C002", item="承诺书签章确认",
                                 reason="图片型承诺书，盖章、签署日期、扫描件清晰度均需人工确认",
                                 file=entry.get("path", ""),
                                 details=f"文件类型: {ftype}；需重点确认：①公章/签字是否完整 ②签署日期是否填写 ③扫描件是否清晰可辨")
            elif ftype == "pdf":
                self._add_manual("C002", item="承诺书签章确认",
                                 reason="PDF 承诺书，盖章、签署日期、扫描件清晰度均需人工确认",
                                 file=entry.get("path", ""),
                                 details="PDF 文件，未执行 OCR 签章检测；需重点确认：①公章/签字是否完整 ②签署日期是否填写 ③扫描件是否清晰可辨")

    # ── X001: CNIPA XML 编码映射正确性 ──────────────────────────────

    def _check_x001(self) -> None:
        from .manifest import _load_cnipa_mapping
        mapping = _load_cnipa_mapping()
        known_codes = set(mapping.keys())

        unknown: List[str] = []
        known: List[str] = []
        for entry in self._manifest_entries:
            path = entry.get("path", "")
            if entry.get("file_type") != "xml":
                continue
            # Extract potential CNIPA code from filename
            import re as _re
            match = _re.search(r"(\d{6})", path)
            if not match:
                continue
            code = match.group(1)
            if code in known_codes:
                known.append(path)
            else:
                unknown.append(path)

        if unknown:
            self._add_finding("X001", passed=False,
                              message=f"发现 {len(unknown)} 个未识别编码的 XML 文件",
                              details="未识别: " + "; ".join(unknown))
        else:
            self._add_finding("X001", passed=True,
                              message=f"所有 {len(known)} 个 XML 文件编码均在映射表中",
                              details=f"已知编码: {sorted(known_codes)}")

    # ── Q001: 权利要求编号连续性检查 ────────────────────────────────

    def _check_q001(self) -> None:
        claims = self._extract_all_claims()
        if not claims:
            self._add_finding("Q001", passed=True,
                              message="未找到权利要求书，跳过检查",
                              details="未解析到 100001.xml 或其中无权利要求")
            return

        numbers = sorted(c["number"] for c in claims)
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            gaps = [n for n in expected if n not in numbers]
            self._add_finding("Q001", passed=False,
                              message=f"权利要求编号不连续，缺失编号: {gaps}",
                              details=f"实际编号: {numbers}，期望: {expected}")
        else:
            self._add_finding("Q001", passed=True,
                              message=f"权利要求编号连续（1–{len(numbers)}）",
                              details=f"共 {len(numbers)} 项权利要求")

    # ── Q002: 权利要求引用关系基础检查 ──────────────────────────────

    def _check_q002(self) -> None:
        claims = self._extract_all_claims()
        if not claims:
            self._add_finding("Q002", passed=True,
                              message="未找到权利要求书，跳过检查",
                              details="未解析到 100001.xml 或其中无权利要求")
            return

        total = len(claims)
        ref_issues: List[str] = []
        for c in claims:
            if c.get("is_independent"):
                continue
            refs = self._extract_referenced_claims(c["text"])
            for ref in refs:
                if ref > total or ref < 1:
                    ref_issues.append(
                        f"权利要求 {c['number']} 引用了不存在的权利要求 {ref}"
                    )
                elif ref == c["number"]:
                    ref_issues.append(
                        f"权利要求 {c['number']} 自引用"
                    )

        if ref_issues:
            self._add_finding("Q002", passed=False,
                              message=f"发现 {len(ref_issues)} 个引用关系问题",
                              details="\n".join(ref_issues[:10]))
        else:
            self._add_finding("Q002", passed=True,
                              message=f"所有 {total} 项权利要求引用关系检查通过",
                              details=f"总权利要求数: {total}")

    # ── D001: 说明书明显术语冲突检查 ────────────────────────────────

    def _check_d001(self) -> None:
        paragraphs = self._load_specification_paragraphs()
        if not paragraphs:
            self._add_finding("D001", passed=True,
                              message="未找到说明书内容，跳过检查",
                              details="未解析到 100002.xml")
            return

        # Simple check: look for contradictory "本发明涉及" statements
        field_statements = []
        for p in paragraphs:
            m = re.search(r"(?:本发明|本申请)(?:\s*涉及|\s*属于|\s*公开)", p[:100])
            if m:
                field_statements.append(p[:150])

        field_issues: List[str] = []
        if len(field_statements) >= 2:
            # Check if the first segment after keywords differs significantly
            segments = []
            for s in field_statements:
                m = re.search(r"(?:涉及|属于|公开)(.+?)[，。]", s)
                if m:
                    segments.append(m.group(1).strip()[:30])
            if len(set(segments)) > 1 and len(segments) >= 2:
                field_issues.append(f"发现多个技术领域描述: {' | '.join(segments)}")

        if field_issues:
            self._add_finding("D001", passed=False,
                              message=f"发现 {len(field_issues)} 个可能的术语冲突",
                              details="\n".join(field_issues))
        else:
            self._add_finding("D001", passed=True,
                              message="未检测到明显术语冲突",
                              details=f"检查了 {len(paragraphs)} 个说明书段落")

    # ── D002: 说明书重复段落/孤立残句提示 ───────────────────────────

    def _check_d002(self) -> None:
        paragraphs = self._load_specification_paragraphs()
        if not paragraphs:
            self._add_finding("D002", passed=True,
                              message="未找到说明书内容，跳过检查",
                              details="未解析到 100002.xml")
            return

        issues: List[str] = []

        # Duplicate paragraphs
        seen: Dict[str, List[int]] = {}
        for i, p in enumerate(paragraphs, 1):
            stripped = p.strip()
            if len(stripped) < 10:
                continue
            if stripped in seen:
                seen[stripped].append(i)
            else:
                seen[stripped] = [i]
        dupes = {text: idxs for text, idxs in seen.items() if len(idxs) > 1}
        if dupes:
            for text, idxs in list(dupes.items())[:5]:
                issues.append(f"重复段落（第 {idxs} 段）: {text[:60]}...")

        # Isolated fragments (very short paragraphs)
        # Threshold: 20 chars. Filter out common legitimate short patterns:
        # - "图中：" image captions
        # - "X、..." figure reference labels
        # - "；" or "、" terminated technical labels
        _short_filter_patterns = ["图中", "附图", "图"]  # image/figure references
        short_paras = []
        for i, p in enumerate(paragraphs):
            stripped = p.strip()
            if len(stripped) < 20 and stripped:
                # Skip if it matches a known legitimate pattern
                is_legitimate = False
                for pat in _short_filter_patterns:
                    if pat in stripped:
                        is_legitimate = True
                        break
                if is_legitimate:
                    continue
                short_paras.append((i+1, stripped))
        if short_paras:
            for idx, p in short_paras[:5]:
                issues.append(f"孤立残句/过短段落（第 {idx} 段）: {p.strip()[:40]}")

        if issues:
            self._add_finding("D002", passed=False,
                              message=f"发现 {len(issues)} 个问题（{len(dupes)} 处重复, {len(short_paras)} 处过短）",
                              details="\n".join(issues))
        else:
            self._add_finding("D002", passed=True,
                              message="未检测到明显重复或过短段落",
                              details=f"检查了 {len(paragraphs)} 个说明书段落")

    # ── Data helpers ────────────────────────────────────────────────

    def _extract_all_claims(self) -> List[dict]:
        """Extract all claims (not just independent) from 100001.xml."""
        root = self._get_xml_root("100001")
        if root is None:
            return self._case_data.get("independent_claims", [])

        ns = _detect_namespace(root)
        ns_map = _make_ns_map(ns)

        claim_els = _safe_find_all(root, ".//ns:claim" if ns else ".//claim", ns_map)
        if not claim_els:
            claim_els = _safe_find_all(root, ".//ns:权利要求" if ns else ".//权利要求", ns_map)
        if not claim_els:
            return self._case_data.get("independent_claims", [])

        claims = []
        for el in claim_els:
            num = el.get("num") or el.get("顺序") or len(claims) + 1
            ct_els = _safe_find_all(el, ".//ns:claim-text" if ns else ".//claim-text", ns_map)
            if not ct_els:
                ct_els = _safe_find_all(el, ".//ns:权利要求书" if ns else ".//权利要求书", ns_map)

            parts = []
            if ct_els:
                for ct in ct_els:
                    child_parts = []
                    _collect_text(ct, child_parts)
                    parts.append("".join(child_parts).strip())
            else:
                _collect_text(el, parts)

            full_text = "".join(parts).strip()
            if full_text:
                claims.append({
                    "number": int(num) if str(num).isdigit() else len(claims) + 1,
                    "text": full_text[:1000],
                    "is_independent": self._is_independent(full_text),
                })
        return claims

    @staticmethod
    def _is_independent(text: str) -> bool:
        start = text[:100].strip()
        if start.startswith(("根据权利要求", "如权利要求", "按照权利要求")):
            return False
        return True

    @staticmethod
    def _extract_referenced_claims(text: str) -> List[int]:
        """Extract claim numbers referenced in a dependent claim text."""
        refs: List[int] = []
        refs.append(RuleEngine._extract_referenced_number(text))
        # Also check for ranges like 权利要求1-11
        range_match = re.search(r"权利要求(\d+)[-–—至](\d+)", text)
        if range_match:
            for n in range(int(range_match.group(1)), int(range_match.group(2)) + 1):
                if n not in refs:
                    refs.append(n)
        # Check for comma-separated: 权利要求1、3、5
        comma_match = re.findall(r"权利要求(\d+)[、,，]", text)
        for n in comma_match:
            ni = int(n)
            if ni not in refs:
                refs.append(ni)
        return refs

    @staticmethod
    def _extract_referenced_number(text: str) -> Optional[int]:
        """Extract the primary claim number referenced in text like
        '根据权利要求1所述的' or '如权利要求X-Y任一项所述的'."""
        m = re.search(r"(?:根据权利要求|如权利要求|按照权利要求)\s*(\d+)", text)
        if m:
            return int(m.group(1))
        return None

    def _load_specification_paragraphs(self) -> List[str]:
        """Load paragraphs from 100002.xml."""
        if self._paragraphs:
            return self._paragraphs

        root = self._get_xml_root("100002")
        if root is None:
            return []

        ns = _detect_namespace(root)
        ns_map = _make_ns_map(ns)

        for tag in ["p", "段落", "paragraph", "para"]:
            elements = _safe_find_all(root, f".//ns:{tag}" if ns else f".//{tag}", ns_map)
            if elements:
                for el in elements:
                    parts = []
                    _collect_text(el, parts)
                    text = "".join(parts).strip()
                    if text:
                        self._paragraphs.append(text)
                break

        return self._paragraphs

    # ── Output ──────────────────────────────────────────────────────

    def write_output(self) -> None:
        """Write rule_findings.json, manual_review_items.json, and rule_check_report.md."""
        parsed_dir = self.case_dir / cfg.PARSED
        output_dir = self.case_dir / cfg.OUTPUT
        parsed_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # rule_findings.json
        findings_path = parsed_dir / "rule_findings.json"
        with open(findings_path, "w", encoding="utf-8") as f:
            json.dump(self.findings, f, ensure_ascii=False, indent=2)
        self.logger.info("Rule findings written: %s (%d items)", findings_path, len(self.findings))

        # manual_review_items.json
        manual_path = parsed_dir / "manual_review_items.json"
        with open(manual_path, "w", encoding="utf-8") as f:
            json.dump(self.manual_items, f, ensure_ascii=False, indent=2)
        self.logger.info("Manual review items written: %s (%d items)", manual_path, len(self.manual_items))

        # rule_check_report.md
        report_path = output_dir / "rule_check_report.md"
        report_md = self._generate_report()
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        self.logger.info("Rule check report written: %s", report_path)

    def _generate_report(self) -> str:
        """Generate a Markdown report from findings."""
        lines: List[str] = []
        lines.append("# 规则审查报告")
        lines.append("")
        lines.append(f"- **案卷号**: {self.case_dir.name}")
        lines.append(f"- **审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **规则总数**: {len(self.findings)}")

        passed = sum(1 for f in self.findings if f["passed"])
        failed = sum(1 for f in self.findings if not f["passed"] and f["severity"] not in ("manual", "error"))
        manual_count = sum(1 for f in self.findings if f["severity"] == "manual" and not f["passed"])
        error_count = sum(1 for f in self.findings if f["severity"] == "error")

        lines.append(f"- **通过**: {passed}")
        lines.append(f"- **未通过**: {failed}")
        lines.append(f"- **需人工确认**: {manual_count}")
        lines.append("")

        # Group by category
        categories: Dict[str, List[dict]] = {}
        for f in self.findings:
            cat = f.get("category", "其他")
            categories.setdefault(cat, []).append(f)

        lines.append("---")
        lines.append("")
        lines.append("## 审查结果汇总")
        lines.append("")

        for cat_name in sorted(categories.keys()):
            cat_findings = categories[cat_name]
            lines.append(f"### {cat_name}")
            lines.append("")
            lines.append("| 规则 | 结果 | 严重程度 | 说明 |")
            lines.append("|------|------|---------|------|")
            for f in cat_findings:
                if f["severity"] == "error":
                    result = "💥 执行异常"
                elif f["passed"]:
                    result = "✅ 通过"
                elif f["severity"] == "manual":
                    result = "⚠️ 需人工确认"
                else:
                    result = "❌ 未通过"
                lines.append(f"| {f['rule_id']} {f['rule_name']} | {result} | {f['severity']} | {f['message']} |")
            lines.append("")

        # Manual review items
        if self.manual_items:
            lines.append("---")
            lines.append("")
            lines.append("## 需人工确认事项")
            lines.append("")
            for item in self.manual_items:
                lines.append(f"### [{item['rule_id']}] {item['item']}")
                lines.append(f"- **原因**: {item['reason']}")
                lines.append(f"- **文件**: {item['file']}")
                if item.get("details"):
                    lines.append(f"- **详情**: {item['details']}")
                lines.append("")

        # Summary statistics
        lines.append("---")
        lines.append("")
        severity_counts = {}
        for f in self.findings:
            sev = f["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        lines.append("## 统计")
        lines.append("")
        for sev in ["high", "medium", "low", "manual", "error"]:
            cnt = severity_counts.get(sev, 0)
            passed_cnt = sum(1 for f in self.findings if f["severity"] == sev and f["passed"])
            lines.append(f"- **{sev}**: {cnt} 项（通过 {passed_cnt}，未通过 {cnt - passed_cnt}）")

        lines.append("")
        lines.append("---")
        lines.append("*本报告由系统自动生成，仅供审查员参考，不构成最终审查结论。*")
        lines.append("*最终以国家知识产权局实质审查结果为准。*")

        return "\n".join(lines)


def _collect_element_text(element) -> str:
    """Collect all text recursively from an element."""
    parts = []
    _collect_text(element, parts)
    return "".join(parts).strip()
