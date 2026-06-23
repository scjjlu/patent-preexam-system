# 构建指南：专利快速预审案卷辅助审查系统

## 概述

本系统是 Python 3.11 + Streamlit Web 应用。以下提供三种打包为 Windows 独立可执行程序的方案。

---

## 方案一：GitHub Actions 自动构建（推荐）

**不需要在本地安装 Python 或任何构建工具。**

1. 将本仓库推送到 GitHub：

   ```bash
   git remote add origin https://github.com/<你的用户名>/patent-preexam-system.git
   git push -u origin main
   ```

2. 打开 GitHub 仓库页面，点击 **Actions** 标签
3. 在左侧选择 **Build Windows .exe**
4. 点击 **Run workflow** → 选择分支 → **Run workflow**
5. 等待几分钟，构建完成后在 Workflow run 页面下方的 **Artifacts** 区域下载 `.zip` 文件
6. 解压后得到 `专利预审案卷辅助审查系统.exe`

   > 以后每次推送到 `main` 或 `master` 分支，或者推送 `v*` 标签，都会自动触发构建。

---

## 方案二：在 Windows 上手动构建

**前置条件：** 一台安装了 Python 3.11+ 的 Windows 电脑。

### 步骤

1. **安装 Python**（如果还没有）

   从 https://www.python.org/downloads/ 下载 Python 3.11 或 3.12，安装时勾选 "Add Python to PATH"。

2. **将项目复制到 Windows 电脑**

   将整个 `patent-preexam-system` 文件夹拷贝到 Windows 上。

3. **双击运行构建脚本**

   ```cmd
   # 在项目根目录下双击
   build\build_ui.bat
   ```

   脚本会自动：
   - 安装 PyInstaller 和项目依赖
   - 调用 PyInstaller 打包
   - 输出到 `dist\专利预审案卷辅助审查系统\`

4. **手动构建（备选）**

   ```cmd
   cd patent-preexam-system
   pip install pyyaml lxml pillow streamlit pyinstaller
   pyinstaller build/preexam_ui.spec --noconfirm
   ```

---

## 方案三：在 macOS 上用 Wine 交叉编译

如果你当前只有 macOS，可以通过 **Wine** 在本地完成 Windows 打包（不需要另外找 Windows 电脑）。

### 步骤

```bash
# 1. 安装 Wine
brew install --cask wine-stable

# 2. 下载 Windows Python 安装包
cd /tmp
curl -O https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

# 3. 在 Wine 中安装 Python
wine python-3.11.9-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

# 4. 安装项目依赖
wine pip install pyyaml lxml pillow streamlit pyinstaller

# 5. 构建
cd /path/to/patent-preexam-system
wine pyinstaller build/preexam_ui.spec --noconfirm

# 6. 产物在 dist/ 目录下的 Windows 可执行文件
```

> **注意：** Wine 在 Apple Silicon Mac 上需要通过 Rosetta 2 运行 x86 程序，首次运行可能需要额外配置。如果 Wine 方式遇到问题，请使用方案一（GitHub Actions）或方案二（Windows 原生）。

---

## 输出产物说明

打包完成后，`dist/专利预审案卷辅助审查系统/` 目录下包含：

| 文件 | 说明 |
|------|------|
| `专利预审案卷辅助审查系统.exe` | 主程序入口，双击启动 Streamlit Web 界面 |
| `rules/` | 业务规则文件（YAML），可随版本更新替换 |
| `templates/` | Prompt 模板文件 |
| `src/` | 源代码（打包附带的副本） |

### 使用方法

1. 双击 `专利预审案卷辅助审查系统.exe`
2. 命令行窗口会自动打开并启动 Streamlit 服务器
3. 你的默认浏览器将自动打开 http://localhost:8501
4. 使用界面上的文件上传、案卷识别、一键运行等功能
5. 关闭命令行窗口即可停止服务器

---

## 常见问题

### Q: 打包后的 .exe 体积很大（几百 MB）？

A: 这是正常的。PyInstaller 将 Python 解释器 + 所有依赖库 + Streamlit 全部打包进了单个目录，首次运行需要解压。

### Q: 为什么启动后浏览器没有自动打开？

A: 可以手动打开浏览器访问 http://localhost:8501。如果还不行，检查命令行窗口是否有报错信息。

### Q: 我想更新 rules/ 或 templates/ 中的文件？

A: 打包后的 `rules/` 和 `templates/` 目录在 `dist/` 文件夹中，你可以直接替换里面的 YAML/MD 文件，无需重新打包。

### Q: 能支持在浏览器关闭后仍然运行吗？

A: 关闭浏览器不会关闭 Streamlit 服务器。命令行窗口保持打开即服务器在运行。关闭命令行窗口才会完全停止。
