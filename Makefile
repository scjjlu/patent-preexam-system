# 专利快速预审案卷辅助审查系统 — 常用命令快捷方式
# 用法: make <target> [case=<案卷号>]

SHELL := /bin/zsh
PYTHON := PYTHONPATH=src python3 -m preexam.cli
CASES := cases

# 默认案卷（可替换）
case ?= 10010315

.PHONY: help prepare check report all clean ui test

help:
	@echo "╔══════════════════════════════════════════════════╗"
	@echo "║  专利快速预审案卷辅助审查系统                      ║"
	@echo "╠══════════════════════════════════════════════════╣"
	@echo "║  make prepare case=案卷号   案卷预处理              ║"
	@echo "║  make check   case=案卷号   规则审查                ║"
	@echo "║  make report  case=案卷号   生成报告                ║"
	@echo "║  make all     case=案卷号   三连运行（推荐）          ║"
	@echo "║  make clean   case=案卷号   清空输出                ║"
	@echo "║  make ui                  启动 Streamlit 界面     ║"
	@echo "║  make test                运行全部测试              ║"
	@echo "║  make list                列出已有案卷              ║"
	@echo "║                                                   ║"
	@echo "║  示例: make all case=10010315                     ║"
	@echo "║        make ui                                    ║"
	@echo "╚══════════════════════════════════════════════════╝"

prepare:
	@echo "→ prepare $(case)"
	$(PYTHON) prepare $(CASES)/$(case)

check:
	@echo "→ check $(case)"
	$(PYTHON) check $(CASES)/$(case)

report:
	@echo "→ report $(case)"
	$(PYTHON) report $(CASES)/$(case)

all:
	@echo "═══════════════════════════════════════"
	@echo "  一键运行: prepare → check → report"
	@echo "  案卷: $(case)"
	@echo "═══════════════════════════════════════"
	$(PYTHON) prepare $(CASES)/$(case)
	@echo ""
	$(PYTHON) check $(CASES)/$(case)
	@echo ""
	$(PYTHON) report $(CASES)/$(case)
	@echo ""
	@echo "✓ 全部完成 — 报告: $(CASES)/$(case)/output/report.md"

clean:
	@echo "→ clean $(case)"
	$(PYTHON) clean $(CASES)/$(case)

ui:
	@echo "→ 启动 Streamlit 界面"
	PYTHONPATH=src streamlit run src/preexam/ui_streamlit.py

test:
	@echo "→ 运行测试"
	PYTHONPATH=src python3 -m pytest -q

list:
	@echo "已有案卷:"
	@ls -d $(CASES)/*/ 2>/dev/null | sed 's/$(CASES)\///g;s/\///g'
