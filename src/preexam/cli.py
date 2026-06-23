"""CLI entry point for the preexam system.

Usage:
    python -m preexam.cli prepare cases/<case_id>
    python -m preexam.cli check cases/<case_id>
"""

import sys
from pathlib import Path
from argparse import ArgumentParser

from . import config as cfg
from .logging_utils import setup_case_logger
from .case_manager import CaseManager
from .archive import extract_archives
from .manifest import generate_manifest
from .cnipa_xml import extract_case_data, write_case_data
from .commitment import identify_commitment_files, assess_commitment
from .prompt_builder import generate_prompts
from .rules_engine import RuleEngine


def cmd_prepare(case_path: str) -> int:
    """Run the full prepare pipeline for a single case."""

    # 1. Resolve case directory
    case_dir = Path(case_path).resolve()
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        return 1

    case_id = case_dir.name
    cm = CaseManager(case_dir)

    # 2. Logger
    logger = setup_case_logger(case_dir)
    logger.info("=" * 60)
    logger.info("Starting prepare for case: %s", case_id)
    logger.info("Case directory: %s", case_dir)

    # 3. Ensure output directories
    cm.ensure_dirs()
    logger.info("Output directories created")

    # 4. Scan input files
    input_files = cm.scan_input_files()
    logger.info("Found %d files in input/", len(input_files))

    # 5. Extract archives
    archive_files = cm.find_archive_files()
    archive_warnings = []
    if archive_files:
        logger.info("Extracting %d archive(s)...", len(archive_files))
        archive_warnings = extract_archives(archive_files, cm.extracted_dir(), logger)
        if archive_warnings:
            logger.warning("Archive extraction completed with %d warning(s)", len(archive_warnings))

    # 6. Scan all files (input + extracted)
    all_files = cm.scan_all_files()
    logger.info("Total files after extraction: %d", len(all_files))

    # 7. Generate file manifest
    manifest_data = generate_manifest(all_files, case_dir, logger)

    # 8. Parse CNIPA XML files
    xml_files = cm.find_xml_files()
    logger.info("Found %d XML file(s)", len(xml_files))
    case_data = {
        "title": None,
        "applicant": None,
        "inventor": None,
        "agent_company": None,
        "agent": None,
        "claim_count": None,
        "independent_claims": [],
        "abstract": None,
        "specification_paragraph_count": None,
        "early_publication": None,
        "substantive_examination": None,
    }
    warnings_list: list = []
    warnings_list.extend(archive_warnings)

    if xml_files:
        extracted_data, xml_warnings = extract_case_data(xml_files, logger)
        case_data.update(extracted_data)
        warnings_list.extend(xml_warnings)

    missing_fields = [k for k, v in case_data.items()
                      if v is None and k not in ("independent_claims",)]
    for field in missing_fields:
        warnings_list.append({
            "file": "N/A",
            "message": f"字段未提取到: {field}",
        })
        logger.warning("Field not extracted: %s", field)

    # 9. Identify and assess commitment letters
    commitment_files = identify_commitment_files(all_files)
    commitment_data = None
    if commitment_files:
        commitment_data = assess_commitment(commitment_files[0], logger)
        logger.info("Commitment file: %s → %s",
                     commitment_files[0].name, commitment_data["status"])
    else:
        logger.info("No commitment file found")

    # 10. Write case_data.json and warnings.json
    write_case_data(case_data, warnings_list, case_dir, logger)

    # 11. Generate prompts
    generate_prompts(case_id, case_data, warnings_list, manifest_data, commitment_data, case_dir, logger)

    # 12. Final summary
    logger.info("─" * 40)
    logger.info("Prepare completed for case: %s", case_id)
    logger.info("  Warnings: %d", len(warnings_list))
    logger.info("  Output: %s", case_dir)
    logger.info("=" * 60)

    print(f"\n✓ Prepare completed for {case_id}")
    print(f"  Output directory: {case_dir}")

    return 0


def cmd_check(case_path: str) -> int:
    """Run rule-based check on an already-prepared case."""

    case_dir = Path(case_path).resolve()
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        return 1

    case_id = case_dir.name
    logger = setup_case_logger(case_dir)
    logger.info("=" * 60)
    logger.info("Starting check for case: %s", case_id)

    # Verify prepare has been run
    cd_path = case_dir / "parsed" / "case_data.json"
    mf_path = case_dir / "output" / "file_manifest.json"
    if not cd_path.exists() or not mf_path.exists():
        logger.error("Prepare has not been run for this case — missing case_data.json or file_manifest.json")
        print(f"ERROR: Run 'prepare' first: python -m preexam.cli prepare {case_path}")
        return 1

    # Run rule engine
    engine = RuleEngine(case_dir, logger)
    engine.load_data()
    engine.run_all()
    engine.write_output()

    # Summary
    passed = sum(1 for f in engine.findings if f["passed"])
    failed = sum(1 for f in engine.findings if not f["passed"] and f["severity"] != "manual")
    manual = len(engine.manual_items)
    logger.info("─" * 40)
    logger.info("Check completed for case: %s", case_id)
    logger.info("  Passed: %d | Failed: %d | Manual: %d", passed, failed, manual)
    logger.info("  Findings: %s", case_dir / "parsed" / "rule_findings.json")
    logger.info("  Report:   %s", case_dir / "output" / "rule_check_report.md")
    logger.info("=" * 60)

    print(f"\n✓ Check completed for {case_id}")
    print(f"  Passed: {passed}  Failed: {failed}  Manual review: {manual}")
    print(f"  Report: {case_dir / 'output' / 'rule_check_report.md'}")

    return 0



def cmd_report(case_path: str) -> int:
    """Generate internal review report framework from prepare + check output."""

    case_dir = Path(case_path).resolve()
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        return 1

    case_id = case_dir.name
    logger = setup_case_logger(case_dir)
    logger.info("=" * 60)
    logger.info("Starting report generation for case: %s", case_id)

    # Verify prepare has been run
    cd_path = case_dir / "parsed" / "case_data.json"
    mf_path = case_dir / "output" / "file_manifest.json"
    if not cd_path.exists() or not mf_path.exists():
        logger.error("Prepare has not been run — missing case_data.json or file_manifest.json")
        print(f"ERROR: Run 'prepare' first: python -m preexam.cli prepare {case_path}")
        return 1

    # Generate report
    from .report_generator import ReportGenerator
    rg = ReportGenerator(case_dir, logger)
    rg.load_data()
    rg.write_output()

    report_path = case_dir / "output" / "report.md"
    logger.info("─" * 40)
    logger.info("Report generated for case: %s", case_id)
    logger.info("  Report: %s", report_path)
    logger.info("=" * 60)

    print(f"\n✓ Report generated for {case_id}")
    print(f"  Report: {report_path}")

    return 0


def cmd_clean(case_path: str, force: bool = False) -> int:
    """Clean generated output from a case, keeping input/ untouched."""
    case_dir = Path(case_path).resolve()
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        return 1

    case_id = case_dir.name
    logger = setup_case_logger(case_dir)
    logger.info("=" * 60)
    logger.info("Starting clean for case: %s", case_id)

    cm = CaseManager(case_dir)
    removed = cm.clean_output(force=force)

    logger.info("Cleaned %d item(s)", len(removed))
    for r in removed:
        logger.info("  Removed: %s", r)
    logger.info("=" * 60)

    print(f"\n✓ Clean completed for {case_id}")
    if removed:
        print(f"  Removed: {', '.join(removed)}")
    else:
        print("  Nothing to clean")
    return 0

def main() -> int:
    parser = ArgumentParser(
        description="专利快速预审案卷辅助审查系统 — 案卷预处理与规则审查"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # prepare subcommand
    p = sub.add_parser("prepare", help="运行案卷预处理流程")
    p.add_argument("case_path", help="案卷目录路径 (e.g. cases/PY25DX39653FNPC-CN)")

    # check subcommand
    c = sub.add_parser("check", help="运行规则化审查")
    c.add_argument("case_path", help="案卷目录路径 (e.g. cases/PY25DX39653FNPC-CN)")

    # report subcommand
    r = sub.add_parser("report", help="生成内部审查报告框架")
    r.add_argument("case_path", help="案卷目录路径 (e.g. cases/PY25DX39653FNPC-CN)")

    # clean subcommand
    cl = sub.add_parser("clean", help="清空本案生成的输出文件（保留 input/）")
    cl.add_argument("case_path", help="案卷目录路径 (e.g. cases/PY25DX39653FNPC-CN)")
    cl.add_argument("--force", action="store_true", help="同时删除 preexam_report.md")

    args = parser.parse_args()
    if args.command == "prepare":
        return cmd_prepare(args.case_path)
    elif args.command == "check":
        return cmd_check(args.case_path)
    elif args.command == "report":
        return cmd_report(args.case_path)
    elif args.command == "clean":
        return cmd_clean(args.case_path, force=getattr(args, "force", False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
