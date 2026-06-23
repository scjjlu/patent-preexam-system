"""CNIPA XML parsing — extract structured patent case data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional, Dict
from xml.parsers.expat import ExpatError

from . import config as cfg

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    import xml.etree.ElementTree as etree
    HAS_LXML = False


def _parse_xml(file_path: Path) -> Optional[Any]:
    try:
        tree = etree.parse(str(file_path))
        return tree.getroot()
    except (ExpatError, Exception):
        return None


def _safe_find_text(root, xpath: str, ns_map: Optional[Dict[str, str]] = None) -> Optional[str]:
    try:
        el = root.find(xpath, ns_map) if ns_map else root.find(xpath)
        if el is not None:
            text = _collect_direct_text(el)
            if text:
                return text
    except Exception:
        pass
    return None


def _collect_direct_text(element) -> str:
    if element.text and element.text.strip():
        return element.text.strip()
    for child in element:
        parts = []
        _collect_text(child, parts)
        text = "".join(parts).strip()
        if text:
            return text
    return ""


def _safe_find_all(root, xpath: str, ns_map: Optional[Dict[str, str]] = None) -> List:
    try:
        return root.findall(xpath, ns_map) if ns_map else root.findall(xpath)
    except Exception:
        return []


def extract_case_data(xml_files: List[Path], logger) -> tuple:
    data = {
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
    warnings: List[dict] = []

    for xml_path in xml_files:
        root = _parse_xml(xml_path)
        if root is None:
            warnings.append({"file": str(xml_path), "message": f"Failed to parse XML: {xml_path.name}"})
            logger.warning("Failed to parse XML: %s", xml_path.name)
            continue

        name = xml_path.name
        ns = _detect_namespace(root)
        ns_map = _make_ns_map(ns)

        if "100001" in name:
            claims = _extract_claims(root, ns, ns_map)
            data["claim_count"] = len(claims)
            data["independent_claims"] = [c for c in claims if c.get("is_independent")]
        elif "100002" in name:
            paragraphs = _extract_paragraphs(root, ns, ns_map)
            data["specification_paragraph_count"] = len(paragraphs)
        elif "100004" in name:
            data["abstract"] = _extract_abstract_text(root, ns)
        elif "110101" in name:
            _extract_request_form_data(root, ns, ns_map, data)
        elif "110401" in name:
            data["substantive_examination"] = True

    return data, warnings


def _detect_namespace(root) -> Optional[str]:
    tag = root.tag if hasattr(root, 'tag') else str(root)
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}")[0].lstrip("{")
    return None


def _make_ns_map(ns: Optional[str]) -> Dict[str, str]:
    return {"ns": ns} if ns else {}


# ── Claims ──────────────────────────────────────────────────────────

def _extract_claims(root, ns: Optional[str], ns_map: Dict[str, str]) -> List[dict]:
    """Extract claims, joining all <claim-text> children per claim."""
    claim_els = _safe_find_all(root, ".//ns:claim" if ns else ".//claim", ns_map)
    if not claim_els:
        claim_els = _safe_find_all(root, ".//ns:权利要求" if ns else ".//权利要求", ns_map)
    if not claim_els:
        return []

    claims = []
    for el in claim_els:
        num = el.get("num") or el.get("顺序") or len(claims) + 1
        parts = []

        ct_els = _safe_find_all(el, ".//ns:claim-text" if ns else ".//claim-text", ns_map)
        if not ct_els:
            ct_els = _safe_find_all(el, ".//ns:权利要求书" if ns else ".//权利要求书", ns_map)

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
                "is_independent": _is_independent_claim(full_text),
            })
    return claims


def _is_independent_claim(text: str) -> bool:
    start = text[:100].strip()
    if start.startswith(("根据权利要求", "如权利要求", "按照权利要求")):
        return False
    return True


# ── Specification paragraphs ────────────────────────────────────────

def _extract_paragraphs(root, ns: Optional[str], ns_map: Dict[str, str]) -> List[str]:
    paragraphs = []
    for tag in ["p", "段落", "paragraph", "para"]:
        elements = _safe_find_all(root, f".//ns:{tag}" if ns else f".//{tag}", ns_map)
        if elements:
            for el in elements:
                parts = []
                _collect_text(el, parts)
                text = "".join(parts).strip()
                if text:
                    paragraphs.append(text)
            break
    return paragraphs


# ── Abstract ────────────────────────────────────────────────────────

def _extract_abstract_text(root, ns: Optional[str]) -> Optional[str]:
    ns_map = _make_ns_map(ns)
    for tag in ["p", "段落", "abstract", "摘要"]:
        els = _safe_find_all(root, f".//ns:{tag}" if ns else f".//{tag}", ns_map)
        if els:
            parts = []
            _collect_text(els[0], parts)
            text = "".join(parts).strip()
            if text:
                return text[:1000]
    body = _safe_find_text(root, ".//ns:body" if ns else ".//body")
    return body[:1000] if body else None


# ── Request form data ───────────────────────────────────────────────

def _deep_or_flat_find(root, deep_paths: List[str], flat_tags: List[str],
                       ns: Optional[str]) -> Optional[str]:
    """Try deep chain first, then fall back to flat element."""
    # 1. Try deep chains (nested Chinese structure)
    for chain in deep_paths:
        val = _deep_find(root, chain, ns)
        if val:
            return val
    # 2. Try flat elements (simple English/Chinese tags)
    for tag in flat_tags:
        xp = f".//ns:{tag}" if ns else f".//{tag}"
        val = _safe_find_text(root, xp)
        if val:
            return val
    return None


def _extract_request_form_data(root, ns: Optional[str], ns_map: Dict[str, str], data: dict) -> None:
    """Extract bibliographic data, handling both deep Chinese and flat English XML."""

    # 1. 发明名称
    for tag in ["发明名称", "invention-title", "title"]:
        val = _safe_find_text(root, f".//ns:{tag}" if ns else f".//{tag}")
        if val:
            data["title"] = val
            break

    # 2. 申请人
    val = _deep_or_flat_find(root,
        deep_paths=[
            [".//申请人", ".//第一申请人", ".//姓名或名称"],
            [".//applicant", ".//first-applicant", ".//name"],
        ],
        flat_tags=["申请人", "applicant", "applicant-name"],
        ns=ns)
    if val:
        data["applicant"] = val

    # 3. 发明人 — collect all first
    inv_names = _collect_inventors(root, ns, ns_map)
    if inv_names:
        data["inventor"] = "；".join(inv_names)
    else:
        # Fallback: flat tag
        val = _deep_or_flat_find(root, [], ["发明人", "inventor", "inventor-name"], ns)
        if val:
            data["inventor"] = val

    # 4. 代理机构
    val = _deep_or_flat_find(root,
        deep_paths=[
            [".//专利代理机构", ".//名称"],
            [".//patent-agency", ".//agency-name"],
        ],
        flat_tags=["专利代理机构", "代理机构", "patent-agency", "agency"],
        ns=ns)
    if val:
        data["agent_company"] = val

    # 5. 代理师
    val = _deep_or_flat_find(root,
        deep_paths=[
            [".//专利代理机构", ".//代理师", ".//姓名"],
            [".//patent-agency", ".//agent", ".//name"],
        ],
        flat_tags=["代理人", "代理师", "agent", "patent-agent"],
        ns=ns)
    if val:
        data["agent"] = val

    # 6. 早日公布
    val = _deep_or_flat_find(root,
        deep_paths=[
            [".//提前公开", ".//请求早日公布该专利申请"],
        ],
        flat_tags=["early-publication", "早日公布", "earlyPublication"],
        ns=ns)
    if val and val not in ("0", "null", ""):
        data["early_publication"] = "是" if val == "1" else val

    # 7. 实质审查
    se_el = _deep_find_element(root, [".//实质审查请求"], ns)
    if se_el is not None:
        se_text = _collect_direct_text(se_el)
        data["substantive_examination"] = se_text if se_text else True
    else:
        for tag in ["substantive-examination", "substantiveExamination", "实质审查"]:
            val = _safe_find_text(root, f".//ns:{tag}" if ns else f".//{tag}")
            if val and val not in ("0", "null", ""):
                data["substantive_examination"] = "是" if val == "1" else val
                break


def _deep_find(root, path_parts: List[str], ns: Optional[str]) -> Optional[str]:
    current = root
    for part in path_parts:
        xp = f".//ns:{part[3:]}" if ns else part
        candidates = current.findall(xp) if ns else current.findall(part)
        if not candidates:
            return None
        current = candidates[0]
    return _collect_direct_text(current)


def _deep_find_element(root, path_parts: List[str], ns: Optional[str]) -> Optional[Any]:
    current = root
    for part in path_parts:
        xp = f".//ns:{part[3:]}" if ns else part
        candidates = current.findall(xp) if ns else current.findall(part)
        if not candidates:
            return None
        current = candidates[0]
    return current


def _collect_inventors(root, ns: Optional[str], ns_map: Dict[str, str]) -> List[str]:
    names = []
    container = _deep_find_element(root, [".//发明人"], ns)
    if container is None:
        return names
    for inv in container:
        if not hasattr(inv, 'tag') or (hasattr(etree, 'Comment') and inv.tag is etree.Comment):
            continue
        name_el = inv.find(".//ns:姓名" if ns else ".//姓名")
        if name_el is not None and name_el.text and name_el.text.strip():
            names.append(name_el.text.strip())
    return names


def _collect_text(element, parts: List[str]) -> None:
    if element.text:
        parts.append(element.text)
    for child in element:
        _collect_text(child, parts)
        if child.tail:
            parts.append(child.tail)


# ── Write output ────────────────────────────────────────────────────

def write_case_data(data: dict, warnings: List[dict], case_dir: Path, logger) -> None:
    parsed_dir = case_dir / cfg.PARSED
    parsed_dir.mkdir(parents=True, exist_ok=True)

    data_path = parsed_dir / "case_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Case data written to %s", data_path)

    warnings_path = parsed_dir / "warnings.json"
    with open(warnings_path, "w", encoding="utf-8") as f:
        json.dump(warnings, f, ensure_ascii=False, indent=2)
    logger.info("Warnings written to %s (%d items)", warnings_path, len(warnings))
