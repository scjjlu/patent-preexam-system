# Prompt 02: 形式审查 & 权利要求分析

## 案卷信息
- 案卷号: {{ case_id }}
- 发明名称: {{ title }}

## 权利要求信息
- 权利要求总项数: {{ claim_count }}
- 独立权利要求数: {{ independent_claim_count }}

## 独立权利要求
{% for claim in independent_claims %}
### 独立权利要求 {{ claim.number }}
{{ claim.text }}
{% endfor %}

## 摘要
{{ abstract }}

## 审查要点
1. 检查权利要求格式规范性
2. 识别独立权利要求与从属权利要求
3. 检查权利要求引用基础
4. 初步判断权利要求清楚、简要程度
