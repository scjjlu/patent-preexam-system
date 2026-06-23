"""Template-based prompt generation.

Phase 1 uses a simple custom renderer that handles Jinja2-like syntax
({{ var }}, {% for %}, {% if %}) without external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as cfg


def _load_template(template_name: str) -> str:
    """Load a template file from templates/ directory."""
    templates_dir = cfg.get_templates_dir()
    template_path = templates_dir / template_name
    if not template_path.exists():
        return f"[Template not found: {template_name}]"
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def _resolve_var(varname: str, variables: Dict) -> str:
    """Resolve a dotted variable path like item.path from variables dict."""
    parts = varname.strip().split(".")
    current = variables
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, "")
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else ""
            except ValueError:
                current = ""
        else:
            current = str(current) if current is not None else ""
    if current is None:
        return ""
    if isinstance(current, (dict, list)):
        return str(current)
    return str(current)


def _render_for_block(block_text: str, variables: Dict) -> str:
    """Render a {% for item in list %}...{% endfor %} block."""
    # Parse the for declaration
    decl_match = re.match(r"{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}", block_text)
    if not decl_match:
        return block_text

    item_var = decl_match.group(1)
    list_var = decl_match.group(2)

    # Find body between %} and {%
    body_start = decl_match.end()
    body_end = block_text.rfind("{%")
    if body_end <= body_start:
        body = block_text[body_start:]
    else:
        body = block_text[body_start:body_end]

    items = variables.get(list_var, [])
    if not isinstance(items, list):
        items = [items]

    if not items:
        return ""

    var_pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    parts = []
    for item in items:
        if isinstance(item, dict):
            item_vars = {item_var: item, **variables}
        else:
            item_vars = {item_var: {"text": item}, **variables}

        line = var_pattern.sub(lambda m, iv=item_vars: _resolve_var(m.group(1), iv), body)
        parts.append(line.strip())

    return "\n".join(parts)


def _render_if_block(block_text: str, variables: Dict) -> str:
    """Render a {% if var %}...{% else %}...{% endif %} block."""
    cond_match = re.match(r"{%\s*if\s+(\w+)\s*%}", block_text)
    if not cond_match:
        return block_text

    var_name = cond_match.group(1)
    body_start = cond_match.end()

    else_idx = block_text.find("{% else %}")
    endif_idx = block_text.rfind("{% endif %}")

    if else_idx >= 0 and else_idx < endif_idx:
        true_body = block_text[body_start:else_idx]
        false_body = block_text[else_idx + len("{% else %}"):endif_idx]
    else:
        true_body = block_text[body_start:endif_idx] if endif_idx > body_start else block_text[body_start:]
        false_body = ""

    value = variables.get(var_name)
    is_truthy = bool(value) and value is not None and value != {}

    if isinstance(value, dict) and (value.get("path") is None or value.get("status") == "未检测到"):
        is_truthy = False

    chosen = true_body if is_truthy else false_body
    var_pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    chosen = var_pattern.sub(lambda m: _resolve_var(m.group(1), variables), chosen)
    return chosen.strip()


def render_template(template_text: str, variables: Dict) -> str:
    """Render a template with Jinja2-like syntax using simple substitution."""
    result = template_text

    # 1. Process {% if %} blocks (processed first so vars inside are resolved)
    def _process_if(match):
        return _render_if_block(match.group(0), variables)

    if_pattern = re.compile(
        r"{%\s*if\s+\w+\s*%}.*?{%\s*endif\s*%}", re.DOTALL
    )
    result = if_pattern.sub(_process_if, result)

    # 2. Process {% for %} blocks
    def _process_for(match):
        return _render_for_block(match.group(0), variables)

    for_pattern = re.compile(
        r"{%\s*for\s+\w+\s+in\s+\w+\s*%}.*?{%\s*endfor\s*%}", re.DOTALL
    )
    result = for_pattern.sub(_process_for, result)

    # 3. Clean up any remaining {% %} blocks
    result = re.sub(r"{%[^%]+%}", "", result)

    # 4. Replace remaining {{ var }} placeholders
    var_pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    result = var_pattern.sub(lambda m: _resolve_var(m.group(1), variables), result)

    # 5. Clean up excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def build_prompt_variables(
    case_id: str,
    case_data: dict,
    warnings: List[dict],
    manifest_data: dict,
    commitment_data: Optional[dict],
) -> Dict:
    """Build a flat variable dict for prompt templates."""
    title = case_data.get("title") or "未提取到发明名称"
    claim_count = case_data.get("claim_count") or 0
    independent_claims = case_data.get("independent_claims") or []
    abstract = case_data.get("abstract") or "未提取到摘要"

    manifest_entries = manifest_data.get("entries", [])
    spec_para_count = case_data.get("specification_paragraph_count") or 0

    return {
        "case_id": case_id,
        "title": title,
        "claim_count": str(claim_count),
        "independent_claim_count": str(len(independent_claims)),
        "independent_claims": independent_claims,
        "abstract": abstract[:1000] if abstract else "N/A",
        "specification_excerpt": (
            f"说明书共 {spec_para_count} 个段落"
            if spec_para_count else "未提取到说明书内容"
        ),
        "specification_paragraph_count": str(spec_para_count),
        "manifest": manifest_entries,
        "warnings": warnings,
        "commitment": commitment_data,
    }


def generate_prompts(
    case_id: str,
    case_data: dict,
    warnings: List[dict],
    manifest_data: dict,
    commitment_data: Optional[dict],
    case_dir: Path,
    logger,
) -> None:
    """Generate all 4 prompt files from templates."""
    prompts_dir = case_dir / cfg.PROMPTS
    prompts_dir.mkdir(parents=True, exist_ok=True)

    variables = build_prompt_variables(
        case_id, case_data, warnings, manifest_data, commitment_data
    )

    prompt_templates = [
        ("prompt_01_file_commitment.md", "prompt_01_file_commitment.txt"),
        ("prompt_02_formal_claims.md", "prompt_02_formal_claims.txt"),
        ("prompt_03_patentability.md", "prompt_03_patentability.txt"),
        ("prompt_04_opinion.md", "prompt_04_opinion.txt"),
    ]

    for template_name, output_name in prompt_templates:
        template_text = _load_template(template_name)
        rendered = render_template(template_text, variables)

        output_path = prompts_dir / output_name
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        logger.info("Prompt generated: %s", output_name)
