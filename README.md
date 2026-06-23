# 专利快速预审案卷辅助审查系统

Patent Quick Preliminary Examination Case Aided Review System

## 第一阶段：案卷预处理与结构化数据生成

本阶段实现案卷文件自动识别、解压、分类、结构化数据提取与分段提示词生成，**不调用大模型，不生成最终审查结论，不生成 Word 报告**。

已实现 `prepare` 命令，输入案卷目录后自动完成文件清单生成、XML 结构化提取、警告记录和 4 个分段 prompt 的渲染输出。

## 测试通过情况

### 验收命令

```bash
# 预处理运行
python -m preexam.cli prepare cases/<case_id>

# 运行全部测试
pytest
```

### 测试覆盖

| 测试文件 | 用例数 | 覆盖内容 |
|---------|--------|---------|
| `test_manifest.py` | 7 | 文件分类（PDF/XML/ZIP/RAR/未知）、清单生成（空目录、混合文件） |
| `test_cnipa_xml.py` | 6 | 权利要求提取、说明书段落、摘要提取、请求书信息、无法解析的 XML、数据写入 |
| `test_no_overwrite_report.py` | 3 | report 不被覆盖、预期输出结构完整性、日志文件生成 |

**16 / 16 全部通过。**

### 真实案卷验证

已使用真实 CNIPA 案卷 `10010315`（阻尼器及其工作方法）完成端到端验证：

- input/ 包含 6 个 CNIPA XML（五书 + 请求书）+ 7 张附图 + list.xml
- 提取结果：12 项权利要求（含 2 项独立权利要求）、78 段说明书、发明名称/申请人/发明人/代理机构/代理师 全部正确
- **处理警告：0**

## 输出文件

`prepare` 命令运行后生成的完整输出：

```
cases/<case_id>/
├── output/
│   ├── file_manifest.txt        # 文本格式文件清单
│   └── file_manifest.json       # JSON 格式文件清单
├── parsed/
│   ├── case_data.json           # 结构化案件数据
│   └── warnings.json            # 处理警告记录
├── prompts/
│   ├── prompt_01_file_commitment.txt   # 文件完整性 & 承诺书提示词
│   ├── prompt_02_formal_claims.txt     # 形式审查 & 权利要求提示词
│   ├── prompt_03_patentability.txt     # 三性审查提示词
│   └── prompt_04_opinion.txt           # 审查意见提示词
├── logs/
│   └── preexam.log              # 运行日志
├── extracted/                   # 解压文件目录
├── parsed/                      # 结构化数据目录
├── prompts/                     # prompt 输出目录
├── output/                      # 报告和清单目录
└── logs/                        # 日志目录
```

### 结构化提取字段

`case_data.json` 提取字段说明：

| 字段 | 说明 | 来源 XML |
|------|------|---------|
| `title` | 发明名称 | 110101 |
| `applicant` | 申请人 | 110101 |
| `inventor` | 发明人（多位用；分隔） | 110101 |
| `agent_company` | 代理机构名称 | 110101 |
| `agent` | 代理师姓名 | 110101 |
| `claim_count` | 权利要求总项数 | 100001 |
| `independent_claims` | 独立权利要求列表 | 100001 |
| `abstract` | 说明书摘要 | 100004 |
| `specification_paragraph_count` | 说明书段落数 | 100002 |
| `early_publication` | 是否请求早日公布 | 110101 |
| `substantive_examination` | 是否请求实质审查 | 110101/110401 |

## 第一阶段能力边界

### 已实现

- ✅ 案卷 `input/` 目录递归扫描（支持 PDF/ZIP/RAR/XML/JPG/PNG/DOCX）
- ✅ ZIP/RAR 自动解压到 `extracted/`（中文文件名异常不中断）
- ✅ file_manifest.txt + file_manifest.json 生成（含文件角色识别）
- ✅ CNIPA XML 编码映射（规则外置到 `rules/cnipa_file_mapping.yaml`）
- ✅ 支持 3 种 XML 结构：带命名空间的 lxml 格式、扁平中文标签格式、深层嵌套中文标签格式
- ✅ 6 类 CNIPA XML 文档解析（100001~100004 + 110101 + 110401）
- ✅ 权利要求多段 claim-text 拼接与独立/从属分类
- ✅ 请求书深层嵌套元素提取（`<申请人>/<第一申请人>/<姓名或名称>` 等）
- ✅ 多位发明人收集
- ✅ 承诺书文件识别与保守标记（不判定"未盖章"）
- ✅ 4 个分段 prompt 模板渲染（内置 Jinja2 类模板引擎）
- ✅ warnings.json 记录处理警告
- ✅ 运行日志 `logs/preexam.log`
- ✅ 所有业务规则外置到 `rules/` 目录
- ✅ 16 项单元测试

### 明确排除（不在第一阶段范围内）

- ❌ 不调用任何大模型 API（OpenAI 等）
- ❌ 不生成最终授权/驳回结论
- ❌ 不生成 Word/PDF 审查报告
- ❌ 不覆盖 `output/preexam_report.md`
- ❌ 不修改 `input/` 下任何原始文件（只读）
- ❌ 不执行 OCR 文字识别或签章检测
- ❌ 不分析对比文件
- ❌ 不执行形式审查规则检查
- ❌ 不生成审查意见通知书

## 工程约束

- **input/ 原始文件只读**：程序不得修改、移动、删除 input/ 下任何文件
- **写入目录边界**：解压结果 → `extracted/`，结构化数据 → `parsed/`，prompt → `prompts/`，清单 → `output/`，日志 → `logs/`
- **不覆盖 preexam_report.md**：该文件为审查员手工生成，程序不得自动写入或覆盖
- **解压容错**：ZIP/RAR 中文文件名解码失败不中断流程，写入 warnings.json
- **承诺书标记**：OCR 不确定时不判定"未盖章"，统一标记为"需人工确认"
- **三性措辞**：必须包含"初步判断""基于当前案卷及已提供对比文件""最终以国家知识产权局实质审查结果为准"
- **规则外置**：所有业务规则存放在 `rules/` 目录，不得硬编码
- **测试纪律**：每次修改代码后运行 pytest

## 下一阶段开发计划

### Phase 2：规则审查与提示词优化

1. **形式审查规则实现**
   - 基于 `rules/formal_check_rules.yaml` 实现权利要求编号连续性检查
   - 权利要求引用基础校验（从属权利要求是否引用了正确的独立权利要求）
   - 五书文件完整性检查（权利要求书、说明书、附图、摘要、请求书）
   - 说明书充分公开初步判断

2. **承诺书审查增强**
   - 集成 OCR 引擎（如 Tesseract）对图片/扫描件 PDF 进行签章检测
   - 承诺书格式规范性检查（签章位置、日期完整性）
   - 委托书一致性核验

3. **申请文件一致性核查**
   - 请求书信息与 XML 内容交叉比对（发明名称、申请人、发明人）
   - 说明书、权利要求书、摘要内容一致性检查
   - 附图标记与说明书对应关系检查

4. **报告生成与导出**
   - `output/preexam_report.md` 自动生成（遵循覆盖保护规则）
   - 可选 Word/PDF 格式导出
   - 审查意见要点汇总

### Phase 3：大模型辅助审查

1. **Prompt 正式发送**：将 `prompts/` 中的分段 prompt 发送至 LLM API
2. **三性初步判断**：基于 LLM 输出生成新颖性/创造性/实用性初步分析
3. **对比文件技术特征比对**：支持上传对比文件并与权利要求进行技术特征映射
4. **审查结论草稿**：辅助生成审查意见通知书草稿（审查员最终确认）
5. **审查经验反馈**：历史审查结论分析，常见问题提示

## 快速开始

```bash
# 安装依赖
pip install --user . pytest pyyaml lxml pillow

# 运行案卷预处理
PYTHONPATH=src python3 -m preexam.cli prepare cases/PY25DX39653FNPC-CN

# 运行测试
PYTHONPATH=src python3 -m pytest
```

## 目录结构

```
patent-preexam-system/
├── src/preexam/         # 核心模块
│   ├── cli.py           # CLI 入口
│   ├── config.py        # 配置与路径
│   ├── case_manager.py  # 案卷目录管理
│   ├── archive.py       # 解压模块
│   ├── manifest.py      # 文件清单
│   ├── cnipa_xml.py     # XML 解析
│   ├── commitment.py    # 承诺书处理
│   ├── prompt_builder.py # prompt 渲染
│   └── logging_utils.py # 日志
├── rules/               # 业务规则（YAML）
├── templates/           # prompt 模板
├── cases/               # 案卷数据
└── tests/               # 单元测试
```
