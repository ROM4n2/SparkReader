# Spark — 马列毛经典 AI 阅读助手

本地离线的桌面 AI 阅读助手，专为马列毛经典著作的研读设计。完全离线运行，数据不出本机。

## 功能一览

| 功能 | 说明 |
|------|------|
| 💬 **智能问答** | 三模式：RAG 文档问答 / 剪贴板上下文 / 直接问答，带对话历史持久化 |
| 📖 **内置阅读器** | PDF 图片渲染（QGraphicsView，高 DPI 2x），支持缩放、翻页、拖拽平移、目录导航 |
| | .txt .md .docx 等格式自动切换渲染方式，三栏布局（目录 \| 内容 \| AI 分析） |
| 📚 **文档库** | 拖拽导入文档，自动分块嵌入向量库，分批处理大文件不崩溃，支持全程进度显示 |
| ⚙️ **设置面板** | 模型切换、剪贴板监控、全局快捷键、开机自启 |
| 🎨 **革命红主题** | 深色近黑背景 + #c0392b 红色点缀，几何锐利风格，贴合应用定位 |

**理论立场：** 分析始终基于马列毛主义理论框架和历史唯物主义视角，提供具体的历史背景和时代条件分析。

## 设计缘起

国内互联网上很难找到遵循马列毛立场的资料。向 AI 提问多半被"社区规范"拦截。本地模型的优势在于不受审查——它只服从你给的 prompt，不内置内容过滤。

最初想做讲解视频来正本清源，但马列功底不足，对历史背景的了解也不够。“历史宜粗不宜细”在我看来恰恰是对这段辉煌革命史的亵渎。
与其去讲自己还没吃透的内容，不如做一个能在阅读时实时出示解释的工具——这就是 Spark（星火） 的起点，星星之火可以燎原。

当前 PDF 阅读体验还很粗糙，还有很多路要走。

> "斗争，失败，再斗争，再失败，直至胜利。"

## 系统要求

- **Windows 10/11**（Linux/macOS 可运行但未充分测试）
- **Python 3.10+**
- **Ollama** — [下载安装](https://ollama.com/download)
- **GPU 推荐** — RTX 5060 测试通过，8GB VRAM 可流畅运行 7B 模型

## 快速开始

### 1. 安装 Ollama 并拉取模型

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### 2. 配置 Python 环境

```bash
cd spark
python -m venv backend/.venv
backend\.venv\Scripts\pip install -r requirements.txt
```

### 3. 启动 GUI

```bash
backend\.venv\Scripts\python gui\app.py
```

或者双击 `start_spark.bat --gui`。

## 首次使用

1. 启动程序，自动检查 Ollama 连接状态
2. 切换到 **📚 文档库** Tab
3. 点击 **📄 添加文件**，选择 `documents\马克思主义哲学概要.txt`
4. 切换到 **💬 问答** Tab，在 RAG 模式下提问

## 阅读模式智能分析

在 **📖 阅读** Tab 中打开一个文本文件。点击任意段落，AI 会自动分析该段落的核心概念，并在右侧面板展示其历史背景和理论解释。

## 文档库使用

- **直接拖拽**文件到文档库窗口即可导入
- 支持格式：`.txt` `.md` `.pdf` `.docx`
- 导入的文档自动分块、嵌入向量，用于 RAG 检索增强问答

## 项目结构

```
spark/
├── gui/                  # PySide6 桌面 GUI
│   ├── app.py           # 入口 + 系统托盘 + 全局快捷键
│   ├── main_window.py   # 四标签主窗口
│   ├── chat_tab.py      # 问答对话面板
│   ├── reader_tab.py    # 三栏阅读器（目录 | 内容 | AI 分析）
│   ├── pdf_renderer.py  # PDF 图片渲染 + QGraphicsView 缩放平移
│   ├── toc_panel.py     # 目录侧栏（PDF 书签树 + 文本标题提取）
│   ├── library_tab.py   # 文档库 + 向量库管理
│   ├── settings_tab.py  # 设置面板
│   ├── conversation_db.py # 对话历史 SQLite
│   ├── ai_worker.py     # 后台 AI 线程（不卡 UI）
│   ├── file_parser.py   # .pdf/.docx/.txt 文本提取
│   └── resources/
│       └── theme.qss    # 革命红深色主题
├── backend/              # 核心引擎（CLI 版代码未改动）
│   ├── config.py        # 模型配置 + Prompt 模板
│   ├── ollama_client.py # Ollama HTTP API
│   ├── clipboard_monitor.py # 剪贴板监听
│   ├── rag_engine.py    # ChromaDB 向量检索
│   ├── ingest.py        # 文档导入 CLI
│   └── main.py          # 原 CLI 入口
├── documents/            # 示例文档
├── requirements.txt
├── start_spark.bat       # CLI 启动脚本
└── README.md
```

## 配置说明

可在 `backend/config.py` 或 GUI 的 **⚙️ 设置** Tab 中修改：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 聊天模型 | `qwen2.5:7b` | 问答和分析用的 LLM |
| 嵌入模型 | `nomic-embed-text` | 文本向量化模型 |
| 剪贴板监控 | 开启 | 后台监听剪贴板变化 |
| 自动解释阈值 | 50 字 | 超过此长度的文本自动触发解释 |
| 全局快捷键 | `Ctrl+Shift+S` | 切换窗口显示/隐藏 |
| 开机自启 | 关闭 | 登录时自动启动 |

## 常见问题

**Q: 需要联网吗？**
A: 不需要。所有处理在本地完成，数据不离开你的电脑。

**Q: AI 回答慢怎么办？**
A: Qwen2.5 7B 在消费级 GPU 上需要 2-10 秒生成回答。UI 使用后台线程，不会卡死。

**Q: 能换其他模型吗？**
A: 可以。`ollama pull <模型名>` 后在设置中切换即可。

**Q: 为什么是马列毛主义立场？**
A: 国内主流问答平台和 AI 服务受内容审查限制，无法对马列毛经典著作和相关历史事件给出实质分析。Spark 使用本地模型绕开这一限制，站在马列毛理论立场提供历史唯物主义视角的分析。

## 技术栈

- **GUI 框架：** PySide6 (Qt for Python)
- **语言模型：** Ollama + Qwen2.5 7B
- **向量数据库：** ChromaDB（本地持久化）
- **文本嵌入：** nomic-embed-text
- **文档解析：** PyMuPDF (PDF) + python-docx (Word)

## 许可证

MIT
