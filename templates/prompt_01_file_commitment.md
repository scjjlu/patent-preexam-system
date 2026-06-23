# Prompt 01: 文件完整性 & 承诺书审查

## 案卷信息
- 案卷号: {{ case_id }}
- 发明名称: {{ title }}

## 文件清单
{% for item in manifest %}
- {{ item.path }} ({{ item.description }})
{% endfor %}

## 承诺书审查
{% if commitment %}
- 承诺书文件: {{ commitment.path }}
- 签章状态: {{ commitment.status }}
{% else %}
- 未检测到承诺书文件
{% endif %}

## 审查要点
1. 检查五书文件是否齐全（权利要求书、说明书、说明书附图、说明书摘要）
2. 检查请求书信息是否完整
3. 确认承诺书签署状态
4. 标记缺失或异常文件
