"""内部审查报告生成器 — Phase 2.

基于 prepare + check 的输出，生成 Markdown 版内部审查报告框架。
包含案卷信息、文件清单、规则审查结果和预审员填写区。
不覆盖 output/preexam_report.md。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import config as cfg
from .manifest import _load_cnipa_mapping


REPORT_FILENAME = "report.md"


class ReportGenerator:
    """Generate internal review report framework from prepare + check output."""

    def __init__(self, case_dir: Path, logger):
        self.case_dir = case_dir
        self.logger = logger
        self._case_data: dict = {}
        self._manifest_entries: list = []
        self._findings: list = []
        self._manual_items: list = []
        self._commitment_data: Optional[dict] = None

    # ── Data loading ────────────────────────────────────────────────

    def load_data(self) -> bool:
        """Load all required data files from prepare + check output.

        Returns True if all critical files exist, False otherwise.
        """
        missing = []

        # case_data.json
        cd_path = self.case_dir / "parsed" / "case_data.json"
        if cd_path.exists():
            with open(cd_path, encoding="utf-8") as f:
                self._case_data = json.load(f)
        else:
            missing.append("parsed/case_data.json")

        # file_manifest.json
        mf_path = self.case_dir / "output" / "file_manifest.json"
        if mf_path.exists():
            with open(mf_path, encoding="utf-8") as f:
                data = json.load(f)
            self._manifest_entries = data if isinstance(data, list) else data.get("entries", [])
        else:
            missing.append("output/file_manifest.json")

        # rule_findings.json (optional — check may not have run)
        rf_path = self.case_dir / "parsed" / "rule_findings.json"
        if rf_path.exists():
            with open(rf_path, encoding="utf-8") as f:
                self._findings = json.load(f)

        # manual_review_items.json (optional)
        mr_path = self.case_dir / "parsed" / "manual_review_items.json"
        if mr_path.exists():
            with open(mr_path, encoding="utf-8") as f:
                self._manual_items = json.load(f)

        if missing:
            self.logger.warning("Missing data files: %s", ", ".join(missing))
            return False
        return True

    # ── Report generation ───────────────────────────────────────────

    def generate(self) -> str:
        """Generate the full Markdown report."""
        sections: List[str] = []
        case_id = self.case_dir.name

        # ── Header ──────────────────────────────────────────────────
        sections.append(f"# 快速预审内部审查报告")
        sections.append("")
        sections.append(f"**案卷号**: {case_id}")
        sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        sections.append(f"**报告类型**: 内部审查框架（预审员填写区见下方）")
        sections.append("")

        # ── 1. 案卷基本信息 ─────────────────────────────────────────
        sections.append("---")
        sections.append("")
        sections.append("## 一、案卷基本信息")
        sections.append("")
        cd = self._case_data
        rows = [
            ("发明名称", cd.get("title") or "—"),
            ("申请人", cd.get("applicant") or "—"),
            ("发明人", cd.get("inventor") or "—"),
            ("代理机构", cd.get("agent_company") or "—"),
            ("代理师", cd.get("agent") or "—"),
            ("权利要求项数", str(cd.get("claim_count") or "—")),
            ("独立权利要求", str(len(cd.get("independent_claims") or []))),
            ("说明书段落数", str(cd.get("specification_paragraph_count") or "—")),
            ("早日公布", cd.get("early_publication") or "未勾选"),
            ("实质审查", "已请求" if cd.get("substantive_examination") else "未请求"),
        ]
        sections.append("| 字段 | 内容 |")
        sections.append("|------|------|")
        for label, value in rows:
            sections.append(f"| {label} | {value} |")
        sections.append("")

        # ── 2. 文件完整性 ──────────────────────────────────────────
        sections.append("---")
        sections.append("")
        sections.append("## 二、文件完整性审查")
        sections.append("")
        sections.append(self._build_file_completeness_table())
        sections.append("")

        # ── 3. 规则审查结果 ─────────────────────────────────────────
        sections.append("---")
        sections.append("")
        sections.append("## 三、规则审查结果")
        sections.append("")
        if self._findings:
            sections.append(self._build_findings_table())
        else:
            sections.append("（未运行 check 命令，无规则审查数据）")
        sections.append("")

        # ── 4. 需人工确认事项 ──────────────────────────────────────
        sections.append("---")
        sections.append("")
        sections.append("## 四、需人工确认事项")
        sections.append("")
        if self._manual_items:
            for item in self._manual_items:
                sections.append(f"- **[{item['rule_id']}] {item['item']}**")
                sections.append(f"  - 原因: {item['reason']}")
                sections.append(f"  - 文件: {item.get('file', '—')}")
                if item.get("details"):
                    sections.append(f"  - 详情: {item['details']}")
                sections.append("")
        else:
            sections.append("（无）")
            sections.append("")

        # ── 5. 预审员填写区 ─────────────────────────────────────────
        sections.append("---")
        sections.append("")
        sections.append("## 五、预审员填写区")
        sections.append("")
        sections.append("*以下内容由预审员根据系统检查结果和专业知识填写。*")
        sections.append("")

        # 5a. 文件完整性审查意见
        sections.append("### 5.1 文件完整性审查意见")
        sections.append("")
        sections.append("**系统检查摘要：**")
        # Summarize manifest completeness
        sections.append(self._manifest_summary_line())
        sections.append("")
        sections.append("**预审员意见：**")
        sections.append("")
        sections.append("> （请在此处填写文件完整性审查意见，例如：五书文件是否齐全、承诺书签署是否完整等）")
        sections.append("")
        sections.append("")

        # 5b. 形式审查意见
        sections.append("### 5.2 形式审查意见")
        sections.append("")
        sections.append("**系统检查摘要：**")
        sections.append(self._formal_check_summary())
        sections.append("")
        sections.append("**预审员意见：**")
        sections.append("")
        sections.append("> （请在此处填写形式审查意见，例如：权利要求格式是否规范、说明书是否充分公开等）")
        sections.append("")
        sections.append("")

        # 5c. 三性初步判断
        sections.append("### 5.3 三性初步判断")
        sections.append("")
        sections.append("**系统提示：**")
        sections.append("")
        sections.append("> 以下内容为初步判断，基于当前案卷及已提供对比文件，最终以国家知识产权局实质审查结果为准。")
        sections.append("")
        sections.append("**预审员意见：**")
        sections.append("")
        sections.append("> （请在此处填写新颖性、创造性、实用性的初步判断意见）")
        sections.append("")
        sections.append("")

        # 5d. 审查意见
        sections.append("### 5.4 审查意见")
        sections.append("")
        sections.append("**预审员意见：**")
        sections.append("")
        sections.append("> （请在此处填写综合审查意见，包括缺陷归纳、修改建议等）")
        sections.append("")
        sections.append("")

        # ── 6. 备注 ─────────────────────────────────────────────────
        sections.append("---")
        sections.append("")
        sections.append("## 六、备注")
        sections.append("")
        sections.append("- 本报告由系统自动生成，仅供预审员参考，不构成最终审查结论。")
        sections.append("- 最终以国家知识产权局实质审查结果为准。")
        sections.append("- 如发现系统检查结果有误，请在预审员意见中予以纠正。")
        sections.append("- 报告文件: `output/report.md`（不会覆盖 `output/preexam_report.md`）")
        sections.append("")

        return "\n".join(sections)

    # ── Helper: file completeness ───────────────────────────────────

    def _build_file_completeness_table(self) -> str:
        """Build a table showing required patent document completeness."""
        mapping = _load_cnipa_mapping()
        lines = []
        lines.append("| 文件类型 | 编码 | 状态 | 文件路径 |")
        lines.append("|---------|------|------|---------|")

        found_roles = set()
        for entry in self._manifest_entries:
            role = entry.get("role", "")
            if role in ("claims", "specification", "drawings", "abstract",
                         "request_form", "substantive_examination_request"):
                found_roles.add(role)

        for code, info in sorted(mapping.items()):
            role = info.get("role", "")
            name = info.get("name", code)
            if role in found_roles:
                entry = next((e for e in self._manifest_entries
                              if e.get("role") == role), None)
                path = entry.get("path", "") if entry else ""
                lines.append(f"| {name} | {code} | ✅ 已提交 | {path} |")
            else:
                lines.append(f"| {name} | {code} | ❌ 缺失 | — |")

        return "\n".join(lines)

    def _manifest_summary_line(self) -> str:
        """One-line summary of manifest completeness."""
        total = len(self._manifest_entries)
        core_codes = {"100001", "100002", "100003", "100004", "110101", "110401"}
        core_xml = 0
        aux_xml = 0
        for e in self._manifest_entries:
            if e.get("file_type") != "xml":
                continue
            path = e.get("path", "")
            if any(code in path for code in core_codes):
                core_xml += 1
            else:
                aux_xml += 1
        img_count = sum(1 for e in self._manifest_entries
                        if e.get("file_type") in ("jpg", "jpeg", "png"))
        other = total - core_xml - aux_xml - img_count
        parts = [f"共 {total} 个文件", f"核心 CNIPA XML: {core_xml}"]
        if aux_xml:
            parts.append(f"辅助 XML: {aux_xml}")
        parts.append(f"图片: {img_count}")
        if other:
            parts.append(f"其他: {other}")
        return "（" + "，".join(parts) + "）"

    # ── Helper: findings table ──────────────────────────────────────

    def _build_findings_table(self) -> str:
        """Build a findings table grouped by category."""
        lines = []

        # Group by category
        categories: dict = {}
        for f in self._findings:
            cat = f.get("category", "其他")
            categories.setdefault(cat, []).append(f)

        for cat_name in sorted(categories.keys()):
            cat_findings = categories[cat_name]
            lines.append(f"**{cat_name}**")
            lines.append("")
            lines.append("| 规则 | 结果 | 严重程度 | 说明 |")
            lines.append("|------|------|---------|------|")
            for f in cat_findings:
                if f.get("severity") == "skip":
                    result = "⏭️ 未适用/跳过"
                elif f.get("severity") == "error":
                    result = "💥 执行异常"
                elif f["passed"]:
                    result = "✅ 通过"
                elif f["severity"] == "manual":
                    result = "⚠️ 需人工确认"
                else:
                    result = "❌ 未通过"
                lines.append(f"| {f['rule_id']} {f['rule_name']} | {result} | {f['severity']} | {f['message']} |")
            lines.append("")

        return "\n".join(lines)

    def _formal_check_summary(self) -> str:
        """Summarize formal check results from findings."""
        if not self._findings:
            return "（未运行 check 命令）"

        relevant = {"Q001", "Q002", "D001", "D002", "R001", "R002", "X001"}
        parts = []
        for f in self._findings:
            if f["rule_id"] in relevant:
                rid = f["rule_id"]
                icon = "✅" if f["passed"] else "❌"
                parts.append(f"- {icon} {rid}: {f['message']}")

        return "\n".join(parts) if parts else "（无相关检查数据）"

    # ── Output ──────────────────────────────────────────────────────

    def write_output(self) -> Path:
        """Write report to output/report.md. Returns the output path."""
        output_dir = self.case_dir / cfg.OUTPUT
        output_dir.mkdir(parents=True, exist_ok=True)

        report_path = output_dir / REPORT_FILENAME
        content = self.generate()

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info("Report written: %s", report_path)
        return report_path
