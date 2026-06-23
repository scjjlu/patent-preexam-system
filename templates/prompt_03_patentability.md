# Prompt 03: 三性审查

## 案卷信息
- 案卷号: {{ case_id }}
- 发明名称: {{ title }}

## 技术方案
{{ specification_excerpt }}

## 独立权利要求
{% for claim in independent_claims %}
### 独立权利要求 {{ claim.number }}
{{ claim.text }}
{% endfor %}

## 审查要点
1. 基于当前案卷及已提供对比文件，初步判断新颖性
2. 基于当前案卷及已提供对比文件，初步判断创造性
3. 初步判断实用性
4. 注意：以上均为初步判断，最终以国家知识产权局实质审查结果为准
