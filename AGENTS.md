# AGENTS.md — 专利快速预审案卷辅助审查系统

## 1. 项目定位

本项目是**专利快速预审案卷辅助审查系统**（Patent Quick Preliminary Examination Case Aided Review System），面向中国国家知识产权局（CNIPA）快速预审业务场景。

目标：辅助预审审查员对案卷进行文件完整性检查、形式审查、三性初步判断等，提升审查效率与一致性。系统不替代审查员判断，所有结论均以"初步判断"措辞呈现，最终以国家知识产权局实质审查结果为准。

## 2. 第一阶段范围

**第一阶段只做案卷预处理和结构化数据生成，不接入大模型，不生成最终审查结论，不生成 Word 报告。**

具体交付：
- 输入文件自动识别、分类、解压
- CNIPA XML 结构化提取（发明名称、申请人、发明人、权利要求等）
- 文件清单生成（txt + json）
- 分段 Prompt 模板渲染（供后续阶段调用 LLM）
- 承诺书文件识别与保守标记
- 处理警告记录（warnings.json）

**明确排除：**
- ❌ 不调用任何大模型 API
- ❌ 不生成最终授权/驳回结论
- ❌ 不生成 Word/PDF 审查报告
- ❌ 不执行 OCR 文字识别
- ❌ 不修改 input/ 下任何原始文件

## 3. 工程约束（契约）

### 3.1 文件系统
- **input/ 原始文件只读**：程序不得修改、移动、删除 input/ 下任何文件。所有写入操作限定在 extracted/、parsed/、prompts/、output/、logs/。
- **解压结果** → `extracted/`
- **结构化数据** → `parsed/`
- **提示词** → `prompts/`
- **报告和清单** → `output/`
- **日志** → `logs/`
- 解压时若 ZIP/RAR 内中文文件名解码失败，不得中断流程，必须写入 warnings.json 继续执行。

### 3.2 输出覆盖规则
- **不得默认覆盖 `output/preexam_report.md`**。该文件是审查员手工生成的报告，程序不得自动写入或覆盖。
- 如需覆盖任何已有输出文件（如重新运行时更新 manifest），必须在日志中记录覆盖行为。
- Prompt 文件可以覆盖（每次 prepare 重新生成），但日志中应有记录。

### 3.3 业务规则外置
- 所有业务规则必须外置到 `rules/` 目录，以 YAML 格式存储。
- 主程序代码中不得硬编码业务规则。
- 具体文件：`cnipa_file_mapping.yaml`（XML 编码映射）、`commitment_rules.yaml`（承诺书审查规则）、`formal_check_rules.yaml`（形式审查规则）。
- 如需新增规则类型，在 `rules/` 下新增 YAML 文件并添加对应读取逻辑。

### 3.4 承诺书判断规则
- OCR 不稳定时，不得直接判定"未盖章"。
- 当 OCR 输出不确定、图像模糊、或无法检测签章时，统一标记为"需人工确认"。
- 仅当明确检测到签章图像特征时，方可标记为"已盖章"。
- 所有签章状态的置信度必须记录在输出数据中。

### 3.5 三性表达规范
- 所有三性（新颖性、创造性、实用性）相关结论必须采用审慎措辞。
- 必须包含的限定表达：
  - "初步判断"
  - "基于当前案卷及已提供对比文件"
  - "最终以国家知识产权局实质审查结果为准"
- 不得使用确定性结论（如"具备创造性""具有新颖性"）。
- 此规则同时应用于 `rules/formal_check_rules.yaml` 和 prompt 模板中。

## 4. 开发规范

### 4.1 测试纪律
- **每次修改代码后必须运行 pytest**，确保所有测试通过。
- 测试范围至少包括：
  - `tests/test_manifest.py` — 文件分类与清单生成
  - `tests/test_cnipa_xml.py` — XML 解析与数据写入
  - `tests/test_no_overwrite_report.py` — 覆盖保护规则
- 新增功能时必须补充对应的单元测试。
- 测试代码避免 mock 掉关键路径；对于有副作用的函数（如写文件），优先使用 `tmp_path` fixture。

### 4.2 文档纪律
- **新增功能必须补充 README**。README 始终保持与当前阶段功能一致。
- `AGENTS.md` 记录项目架构、约束、开发规范，供开发者和 AI 代理阅读。
- 功能变更、目录结构调整、规则文件修改均需在 README 或 AGENTS.md 中反映。
- README 应包含：快速开始、目录结构、输出文件说明、工程约束。

### 4.3 可追溯性
- **所有输出和日志必须可追溯。**
- 每运行一次 `prepare` 命令，`logs/preexam.log` 记录：
  - 运行时间
  - 处理的案卷 ID
  - 发现的文件数量与类型
  - 解压操作与结果
  - XML 解析结果与缺失字段
  - 所有警告信息
  - 每个生成的文件路径
- `parsed/warnings.json` 记录结构化的警告信息，包括：
  - 文件路径
  - 警告消息
  - 警告级别（info / warning / error）
- 所有输出文件（manifest、prompt、日志）中的信息应当能够追溯到输入文件。

## 5. 架构

```
src/preexam/
├── cli.py            — CLI 入口（prepare 命令）
├── config.py         — 项目配置（路径解析、扩展名常量）
├── case_manager.py   — 案卷目录初始化和文件扫描
├── archive.py        — ZIP/RAR 解压（中文文件名容错）
├── manifest.py       — 文件清单生成（txt + json）
├── cnipa_xml.py      — CNIPA XML 解析
├── commitment.py     — 承诺书识别与标记
├── prompt_builder.py — 模板渲染引擎
└── logging_utils.py  — 日志配置

rules/
├── cnipa_file_mapping.yaml     # XML 编码→角色映射
├── commitment_rules.yaml       # 承诺书审查规则
└── formal_check_rules.yaml     # 形式审查规则（含三性表达规范）

templates/
├── prompt_01_file_commitment.md   # 文件完整性 & 承诺书
├── prompt_02_formal_claims.md     # 形式审查 & 权利要求
├── prompt_03_patentability.md     # 三性审查
└── prompt_04_opinion.md           # 审查意见

tests/
├── test_manifest.py
├── test_cnipa_xml.py
└── test_no_overwrite_report.py
```

## 6. 数据流

```
input/ ──扫描──▶ 文件分类 ──▶ ZIP/RAR ──▶ extracted/
                              ├── PDF/JPG/DOCX ──▶ manifest
                              └── XML ──▶ CNIPA XML 解析 ──▶ case_data.json
                                                            └── warnings.json
                                    └── + manifest ──▶ 模板渲染 ──▶ prompts/
```

## 7. 验收命令

```bash
# 预处理运行
python -m preexam.cli prepare cases/<case_id>

# 测试
pytest

# 输出检查
ls cases/<case_id>/output/
ls cases/<case_id>/parsed/
ls cases/<case_id>/prompts/
ls cases/<case_id>/logs/
```
