# Prompt 04: 审查意见

## 案卷信息
- 案卷号: {{ case_id }}
- 发明名称: {{ title }}

## 文件完整性审查结论
{% if warnings %}
### 警告事项
{% for w in warnings %}
- {{ w.message }}
{% endfor %}
{% endif %}

## 形式审查初步意见
- 权利要求项数: {{ claim_count }}
- 独立权利要求: {{ independent_claim_count }} 项
- 说明书段落数: {{ specification_paragraph_count }}

## 三性初步判断
基于当前案卷及已提供对比文件：
1. 新颖性: 待审查员确认
2. 创造性: 待审查员确认
3. 实用性: 待审查员确认

> 注意：以上均为初步判断，最终以国家知识产权局实质审查结果为准。
