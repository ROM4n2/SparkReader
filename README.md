# Spark — 马列毛经典 AI 阅读助手

本地离线的桌面 AI 阅读助手，专为马列毛经典著作的研读设计。完全离线运行，数据不出本机。

## 功能一览

| 功能 | 说明 |
|------|------|
| 📖 **内置阅读器** | PDF 高清渲染（3x DPI），缩放翻页保持 zoom，点击取词，8秒自动分析 |
| | .txt .md .docx 等格式自动切换，三栏布局（目录 \| 内容 \| AI 分析） |
| 🧠 **知识图谱** | 点段落自动提取关联概念，构建知识关系树，支持手动搜索和分析 |
| 💬 **智能问答** | 三模式：RAG 文档问答 / 剪贴板上下文 / 直接问答，带对话历史持久化 |
| 📚 **文档库** | 拖拽导入文档，自动分块嵌入向量库，分批处理大文件不崩溃 |
| 🖍️ **高亮/书签** | 选中文本高亮标注，添加书签标记，高亮可关联到知识图谱概念 |
| 📝 **结构化总结** | 对当前章节或选中文本生成三层总结（核心论点/论证结构/关联知识点） |
| ⚙️ **设置面板** | 模型切换、剪贴板监控、全局快捷键、开机自启 |
| 🎨 **极简呼吸主题** | 暖蓝灰背景 + 柔和珊瑚色点缀，宽间距，微妙 hover 过渡 |

**理论立场：** 分析始终基于马列毛主义理论框架和历史唯物主义视角，提供具体的历史背景和时代条件分析。

## 设计缘起

国内互联网上很难找到遵循马列毛立场的资料。向 AI 提问多半被”社区规范”拦截。本地模型的优势在于不受审查——它只服从你给的 prompt，不内置内容过滤。

与其去做自己还没吃透的内容讲解，不如做一个能在阅读时实时出示解释的工具——这就是 Spark（星火） 的起点，星星之火可以燎原。

> “斗争，失败，再斗争，再失败，直至胜利。”

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

或者双击 `start_spark.bat`。

## 使用指南

### 知识图谱

1. 在 📖 阅读 Tab 打开文件
2. 点击任意段落 → 右侧自动显示概念解释，后台自动提取关联概念
3. 在右侧搜索框输入概念名 → 按 Enter → 切换到知识图谱视图查看关系树
4. 点击「分析」按钮可强制重新提取关联

### 高亮与书签

- 选中文本 → 右键 → 🖍️ 高亮选中文本
- 右键 → 🔖 添加书签
- 右键 → 🔗 关联到概念（将高亮关联到知识图谱中的概念）

### 结构化总结

- 右键选中文本 → 📝 总结选中内容
- 工具栏 → 📝 总结本章（自动识别当前章节）

### 智能问答

- 💬 直接问答：直接向 AI 提问
- 📋 上下文问答：基于剪贴板内容回答
- 📚 RAG 问答：基于导入文档回答

## 项目结构

```
spark/
├── gui/                      # PySide6 桌面 GUI
│   ├── app.py               # 入口 + 系统托盘 + 全局快捷键
│   ├── main_window.py       # 四标签主窗口
│   ├── chat_tab.py          # 问答对话面板
│   ├── reader_tab.py        # 三栏阅读器（目录 | 内容 | AI 分析/知识图谱）
│   ├── pdf_renderer.py      # PDF 高清渲染 + QGraphicsView 缩放平移
│   ├── toc_panel.py         # 目录侧栏（PDF 书签树 + 文本标题提取）
│   ├── library_tab.py       # 文档库 + 向量库管理
│   ├── settings_tab.py      # 设置面板
│   ├── knowledge_graph.py   # 知识图谱面板（搜索 + 关系树 + 详情）
│   ├── conversation_db.py   # 对话历史 SQLite
│   ├── summary_worker.py    # 结构化总结 Worker
│   ├── ai_worker.py         # 后台 AI 线程（不卡 UI）
│   ├── file_parser.py       # .pdf/.docx/.txt 文本提取
│   └── resources/
│       └── theme.qss        # 极简呼吸主题
├── backend/                  # 核心引擎
│   ├── config.py            # 模型配置 + Prompt 模板
│   ├── ollama_client.py     # Ollama HTTP API
│   ├── clipboard_monitor.py # 剪贴板监听
│   ├── rag_engine.py        # ChromaDB 向量检索
│   ├── concept_extractor.py # 概念提取引擎（RAG + LLM）
│   ├── knowledge_db.py      # 知识图谱/高亮/书签/总结 SQLite
│   ├── ingest.py            # 文档导入 CLI
│   └── main.py              # CLI 入口
├── documents/                # 示例文档
├── requirements.txt
├── start_spark.bat           # 启动脚本
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
- **知识存储：** SQLite（概念图/高亮/书签/总结/对话历史）

## 许可证

MIT
