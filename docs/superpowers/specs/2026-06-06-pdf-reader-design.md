# PDF 阅读器增强设计

## 目标

重构 Spark 阅读器 Tab，从纯文本阅读升级为支持 PDF 图片渲染 + 目录导航 + AI 段落分析的三栏布局，同时保持现有 .txt/.md/.docx 支持。

## 决策矩阵

| # | 问题 | 决策 |
|---|------|------|
| 1 | 渲染方式 | 图片渲染（`page.get_pixmap()` + QPixmap） |
| 2 | 翻页模式 | 单页模式，后续可加连续滚动 |
| 3 | 目录位置 | 左侧栏 |
| 4 | 分析位置 | 右侧栏 |
| 5 | 多格式策略 | 统一三栏布局，后缀自动选渲染方式 |
| 6 | 交互方式 | 点击探查 → 提取附近文字 + AI 分析；后续加主动探知 |
| 7 | 实现策略 | 分三步：布局 → PDF 渲染 → 目录侧栏 |
| 8 | 缩放策略 | 固定宽度自适应 + Ctrl+滚轮缩放（±0.25 步进） |
| 9 | 翻页控制 | ←/→ 快捷键 + 底部状态栏翻页控件（页码显示 + [◀][▶] 按钮） |
| 10 | 非 PDF 目录 | .md 解析 `#` 标题，.txt 按章节标题/段落生成目录 |
| 11 | 代码组织 | 拆成多文件 |

## 布局结构

```
┌──────────────────────────────────────────────────────────┐
│ [📂 打开文件] [📄 xxx.pdf]         缩放 100%  [✕ 关闭]   │
├──────────┬────────────────────────┬──────────────────────┤
│ 目录侧栏  │      内容渲染区         │     分析面板          │
│          │                        │                      │
│ QTreeW.  │  PDF: QLabel+QPixmap   │  QTextBrowser        │
│          │  txt: QPlainTextEdit   │  AI 概念分析 +       │
│          │                        │  历史背景            │
│          │                        │                      │
│          │                        │                      │
├──────────┴────────────────────────┴──────────────────────┤
│ 📖 第 3/120 页    [◀] [▶]    缩放: 100%                  │
└──────────────────────────────────────────────────────────┘
```

## 文件拆分

### `gui/reader_tab.py` — 主容器
- 三栏 QSplitter 布局
- 文件格式路由：根据后缀选择中间区域 widget
- 维护 `current_file` / `current_page` 等状态
- 点击探查信号 → 提取文字 → AiWorker 分析
- 顶部工具栏 + 底部状态栏（翻页控件、页码、缩放比）

### `gui/pdf_renderer.py` — PDF 渲染组件
新建文件，核心类 `PdfRenderer(QWidget)`：

- **打开**: 接收 `fitz.Document` 对象，缓存 `page_count`
- **渲染**: `page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))` → `QImage` → `QPixmap` → `QLabel.setPixmap()`
- **翻页**: `goto_page(n)`，键盘 ←/→ 事件，发射 `page_changed(int)` 信号
- **缩放**: `set_zoom(delta)`，Ctrl+滚轮事件，zoom 从 0.5 到 3.0，步进 0.25
- **点击探查**: 鼠标点击事件 → 计算相对于页面的 x/y → `page.get_text("words", clip=rect)` 提取附近文字 → 发射 `text_selected(str)` 信号
- 提供接口：`get_current_page_text() -> str`（获取整页文本给"分析本页"备用）

### `gui/toc_panel.py` — 目录侧栏
新建文件，核心类 `TocPanel(QWidget)`：

- **PDF 目录**: `doc.get_toc()` 返回 `[level, title, page]` 列表 → 填入 QTreeWidget
- **文本目录**: 解析 `#` 标题（md）或正则匹配"第X章/一、二、三"（txt）→ 扁平 QListWidget
- 点击条目 → 发射 `navigate_requested(int)` 信号（页码）
- 无目录时显示 "(本文件无目录)"

### 不变文件
- `gui/ai_worker.py` — AiWorker 复用现有后台线程
- `gui/file_parser.py` — parse_file 保留，txt/md/docx 的文本提取不走 PDF 分支

## 数据流

### 打开文件流程

```
用户点击 [打开文件]
    ↓
QFileDialog → 选择 .pdf / .txt / .md / .docx
    ↓
reader_tab.py 判断后缀
    ├─ .pdf → fitz.open(path)
    │          ├─ PdfRenderer 渲染第1页
    │          └─ TocPanel.set_toc(doc.get_toc())
    └─ .txt/.md/.docx → parse_file() → QPlainTextEdit 显示
                         ├─ TocPanel.set_text_toc(lines)  # 解析标题
                         └─ 分析面板不变
```

### AI 分析流程

```
用户点击 PDF 页面 / 移动光标到某段
    ↓
PdfRenderer 提取附近文字 / QPlainTextEdit 提取段落
    ↓
reader_tab.py 构造 prompt → AiWorker (QThread)
    ↓
Ollama 返回分析 → 右侧 explain_browser 显示
```

### 翻页/跳转流程

```
用户 ←/→ 或点击目录条目或 [◀]/[▶]
    ↓
page_changed(page_num) 信号
    ↓
PdfRenderer 渲染新页
TocPanel 高亮当前条目（若有）
底部状态栏更新页码
```

## 错误处理

| 场景 | 处理 |
|------|------|
| PDF 加载失败 | QMessageBox 提示，回退到文本模式 |
| PDF 无目录（get_toc 返回空） | TocPanel 显示"(本文件无目录)" |
| 点击空白区域 | 忽略，不触发 AI 分析 |
| AI 分析超时 | 现有 AiWorker 错误信号 → 显示失败消息 |
| 大 PDF 渲染 | 只缓存当前页 + 前后各 1 页的 pixmap，翻页时释放旧页 |

## 不做的功能（YAGNI）

- PDF 文本搜索/高亮
- PDF 批注/划线
- 连续滚动模式（后续可加）
- 双页模式
- 书签系统
- 朗读/语音
