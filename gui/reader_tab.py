"""
Reader tab — built-in text reader with smart concept detection.
Opens .txt/.md/.pdf files, tracks cursor position, auto-explains concepts,
and builds knowledge graph in the background.
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QTextBrowser, QSplitter, QLabel,
    QFileDialog, QMessageBox, QLineEdit, QMenu, QStackedWidget,
    QInputDialog,
)
from pathlib import Path

from gui.ai_worker import AiWorker
from gui.file_parser import parse_file
from gui.pdf_renderer import PdfRenderer
from gui.toc_panel import TocPanel
from gui.knowledge_graph import KnowledgeGraphPanel
from backend import knowledge_db
from backend.concept_extractor import extract_concepts, extract_concepts_for_text
from backend.config import CHAPTER_SUMMARY_PROMPT, SELECTION_SUMMARY_PROMPT, SYSTEM_PROMPT


PARAGRAPH_DETECT_PROMPT = (
    "你是一个马列毛主义经典著作阅读助手。用户正在阅读一段文本，请做三件事：\n"
    "1. 指出这段文本在讨论什么核心概念\n"
    "2. 分析这个概念提出的历史背景和时代条件\n"
    "3. 用1-3句话简要解释\n"
    "立场：站在马列毛主义理论立场，而非当代中国特色社会主义话语体系。\n\n"
    "文本：\n{text}"
)


class ReaderTab(QWidget):
    """Text reader with automatic concept detection and explanation."""

    def __init__(self):
        super().__init__()
        self.current_file: str | None = None
        self.current_page = 0
        self.total_pages = 0
        self.current_zoom = 1.0
        self._toc_visible = True
        self._toc_sizes: list[int] | None = None
        self._detect_timer = QTimer()
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(800)  # debounce 800ms
        self._detect_timer.timeout.connect(self._detect_concept)
        self._thread: QThread | None = None
        self._build_ui()
        self._setup_context_menu()

    def _setup_context_menu(self):
        """Set up right-click context menu for the reader."""
        self.reader.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.reader.customContextMenuRequested.connect(self._show_context_menu)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top toolbar — three groups ──
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 8, 12, 8)

        # Left: file operations
        self.open_btn = QPushButton("📂 打开文件")
        self.open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(self.open_btn)

        self.clear_btn = QPushButton("✕ 关闭")
        self.clear_btn.setStyleSheet("background: #3a3a4a; padding: 6px 16px; font-size: 12px;")
        self.clear_btn.clicked.connect(self._close_file)
        self.clear_btn.hide()
        toolbar.addWidget(self.clear_btn)

        toolbar.addStretch(1)

        # Center: reading controls
        self.toc_toggle_btn = QPushButton("目录")
        self.toc_toggle_btn.setFixedSize(60, 28)
        self.toc_toggle_btn.setStyleSheet(
            "QPushButton { padding: 2px 6px; font-size: 12px; }"
        )
        self.toc_toggle_btn.setToolTip("切换目录栏")
        self.toc_toggle_btn.clicked.connect(self._toggle_toc)
        toolbar.addWidget(self.toc_toggle_btn)

        self.summary_btn = QPushButton("📝 总结本章")
        self.summary_btn.setFixedHeight(28)
        self.summary_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 12px; }"
        )
        self.summary_btn.setToolTip("对当前章节生成结构化总结")
        self.summary_btn.clicked.connect(self._summarize_chapter)
        self.summary_btn.hide()
        toolbar.addWidget(self.summary_btn)

        self.toolbar_zoom_label = QLabel("")
        self.toolbar_zoom_label.setStyleSheet("color: #888; font-size: 13px; margin-left: 8px;")
        self.toolbar_zoom_label.hide()
        toolbar.addWidget(self.toolbar_zoom_label)

        toolbar.addStretch(1)

        # Right: current file name
        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #888; font-size: 13px;")
        toolbar.addWidget(self.file_label)

        layout.addLayout(toolbar)

        # ── Three-column splitter: TOC | content | explain ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: TOC panel
        self.toc_panel = TocPanel()
        self.toc_panel.setMinimumWidth(180)
        self.toc_panel.setMaximumWidth(300)
        self.toc_panel.navigate_requested.connect(self._on_toc_navigate)
        splitter.addWidget(self.toc_panel)

        # Center: content area (QPlainTextEdit for txt, replaced by PdfRenderer for PDF)
        self.reader = QPlainTextEdit()
        self.reader.setReadOnly(True)
        self.reader.setPlaceholderText(
            "📂 点击上方「打开文件」开始阅读\n\n"
            "支持格式：\n"
            "  · PDF 文件 — 图片渲染，带目录导航\n"
            "  · TXT / Markdown — 纯文本阅读\n"
            "  · Word 文档 (.docx)\n\n"
            "操作提示：\n"
            "  · ←/→ 翻页  · Ctrl+滚轮缩放\n"
            "  · 点击页面文字 → AI 分析概念\n"
            "  · 拖拽可平移视图"
        )
        self.reader.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #181825; color: #e0e0e0;"
            "  font-size: 15px; padding: 20px 24px;"
            "  line-height: 1.9; border: none;"
            "  font-family: 'Microsoft YaHei', 'Noto Sans SC', 'Segoe UI', sans-serif;"
            "}"
        )
        self.reader.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.reader.cursorPositionChanged.connect(self._on_cursor_moved)
        splitter.addWidget(self.reader)

        # Right: stacked panel (explanation / knowledge graph) with search box
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Search box (serves both views)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索概念...")
        self.search_box.setStyleSheet(
            "QLineEdit { padding: 8px 12px; font-size: 13px;"
            " background: #1a1a2a; border: none;"
            " border-bottom: 1px solid #2a2a3e; color: #e0e0e6; }"
        )
        self.search_box.returnPressed.connect(self._on_search_concept)
        right_layout.addWidget(self.search_box)

        # Stacked widget: explanation (index 0) <-> knowledge graph (index 1)
        self.right_stack = QStackedWidget()

        self.explain_browser = QTextBrowser()
        self.explain_browser.setOpenExternalLinks(False)
        self.explain_browser.setPlaceholderText("点击文本中的段落，AI 会自动识别核心概念并在此显示解释。")
        self.right_stack.addWidget(self.explain_browser)  # index 0

        self.kg_panel = KnowledgeGraphPanel()
        self.kg_panel.concept_selected.connect(self._on_kg_search)
        self.right_stack.addWidget(self.kg_panel)  # index 1

        self.right_stack.setCurrentIndex(0)  # default: explanation
        right_layout.addWidget(self.right_stack, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([200, 500, 300])
        layout.addWidget(splitter, 1)

        # ── Bottom status bar with page navigation (hidden until PDF opens) ──
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(12, 4, 12, 4)

        # Left: status text / filename
        self.status_label = QLabel("📖 点击「打开文件」开始阅读")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Center: page controls
        self.page_label = QLabel("")
        self.page_label.setStyleSheet("color: #888; font-size: 12px; margin: 0 4px;")
        status_layout.addWidget(self.page_label)

        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("跳转")
        self.page_input.setFixedWidth(60)
        self.page_input.setStyleSheet(
            "QLineEdit { padding: 2px 6px; font-size: 12px;"
            " background: #1e1e2a; border: 1px solid rgba(42,42,56,0.6);"
            " border-radius: 4px; color: #e0e0e6; }"
        )
        self.page_input.returnPressed.connect(self._jump_to_page)
        status_layout.addWidget(self.page_input)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(28, 24)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(lambda: self._prev_page())
        status_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(28, 24)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(lambda: self._next_page())
        status_layout.addWidget(self.next_btn)

        # Zoom indicator
        self.status_zoom_label = QLabel("")
        self.status_zoom_label.setStyleSheet("color: #888; font-size: 12px; margin-left: 8px;")
        status_layout.addWidget(self.status_zoom_label)

        self.status_bar = QWidget()
        self.status_bar.setLayout(status_layout)
        self.status_bar.setStyleSheet("border-top: 1px solid #2a2a3e;")
        self.status_bar.hide()
        layout.addWidget(self.status_bar)

    # ── Right panel switching ──

    def _switch_to_explain(self):
        self.search_box.clear()
        self.search_box.setPlaceholderText("点击段落自动分析...")
        self.right_stack.setCurrentIndex(0)

    def _switch_to_kg(self):
        self.search_box.setPlaceholderText("🔍 搜索概念...")
        self.right_stack.setCurrentIndex(1)

    def _on_search_concept(self):
        text = self.search_box.text().strip()
        if not text:
            return
        self._switch_to_kg()
        self._status_msg("🔍 正在分析概念关联...")
        self._run_in_thread(self._do_extract_and_show, text, self._on_kg_ready)

    def _on_kg_search(self, concept_name: str):
        self._status_msg("🔍 正在分析概念关联...")
        self._run_in_thread(self._do_extract_and_show, concept_name, self._on_kg_ready)

    def _do_extract_and_show(self, concept_name: str):
        extract_concepts(concept_name)
        relations = knowledge_db.get_relations(concept_name, max_depth=2)
        return (concept_name, relations)

    def _on_kg_ready(self, result):
        concept_name, relations = result
        self.kg_panel.display_concept(concept_name)
        count = len([r for r in relations if r.get("_depth", 1) == 1])
        self._status_msg(f"✅ 找到 {count} 个关联概念")

    # ── Context menu ──

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        highlight_action = menu.addAction("🖍️ 高亮选中文本\tCtrl+H")
        highlight_action.triggered.connect(self._add_highlight)
        bookmark_action = menu.addAction("🔖 添加书签\tCtrl+D")
        bookmark_action.triggered.connect(self._add_bookmark)
        summary_action = menu.addAction("📝 总结选中内容")
        summary_action.triggered.connect(self._summarize_selection)
        menu.addSeparator()
        link_action = menu.addAction("🔗 关联到概念...")
        link_action.triggered.connect(self._link_to_concept)
        menu.exec(self.reader.mapToGlobal(pos))

    # ── Highlights ──

    def _add_highlight(self):
        cursor = self.reader.textCursor()
        if not cursor.hasSelection():
            QMessageBox.information(self, "提示", "请先选中要标注的文本")
            return
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        knowledge_db.add_highlight(self.current_file, start, end, color="#c0392b")
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#c0392b"))
        fmt.setForeground(QColor("#ffffff"))
        cursor.mergeCharFormat(fmt)
        self._status_msg("✅ 已添加高亮")

    def _load_highlights(self):
        if not self.current_file:
            return
        highlights = knowledge_db.get_highlights(self.current_file)
        if not highlights:
            return
        doc = self.reader.document()
        for h in highlights:
            cursor = QTextCursor(doc)
            cursor.setPosition(h["start_pos"])
            cursor.setPosition(h["end_pos"], QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(h["color"]))
            fmt.setForeground(QColor("#ffffff"))
            cursor.mergeCharFormat(fmt)

    # ── Bookmarks ──

    def _add_bookmark(self):
        if not self.current_file:
            return
        if hasattr(self, 'pdf_renderer') and self.pdf_renderer.doc:
            page = self.current_page
            knowledge_db.add_bookmark(self.current_file, page_number=page)
            self._status_msg(f"✅ 已添加书签 (第 {page + 1} 页)")
        else:
            cursor = self.reader.textCursor()
            line = cursor.block().blockNumber() + 1
            knowledge_db.add_bookmark(self.current_file, line_number=line)
            self._status_msg(f"✅ 已添加书签 (第 {line} 行)")

    # ── Concept linking ──

    def _link_to_concept(self):
        cursor = self.reader.textCursor()
        if not cursor.hasSelection():
            QMessageBox.information(self, "提示", "请先选中文本再关联概念")
            return
        start = cursor.selectionStart()
        highlights = knowledge_db.get_highlights(self.current_file)
        highlight_id = None
        for h in highlights:
            if h["start_pos"] <= start <= h["end_pos"]:
                highlight_id = h["id"]
                break
        if not highlight_id:
            QMessageBox.information(self, "提示", "请先高亮文本再关联概念")
            return
        concepts = knowledge_db.list_concepts()
        if not concepts:
            QMessageBox.information(self, "提示", "知识图谱中暂无概念，请先在阅读中积累")
            return
        names = [c["name"] for c in concepts]
        name, ok = QInputDialog.getItem(self, "关联到概念", "选择概念:", names, 0, False)
        if ok and name:
            knowledge_db.update_highlight_concept(highlight_id, name)
            self._status_msg(f"✅ 已关联到「{name}」")

    # ── Chapter detection ──

    def _get_chapter_text(self) -> str:
        if hasattr(self, 'pdf_renderer') and self.pdf_renderer.doc:
            return self.pdf_renderer.get_current_page_text()
        content = self.reader.toPlainText()
        if not content:
            return ""
        cursor_block = self.reader.textCursor().block()
        current_line_num = cursor_block.blockNumber()
        lines = content.split("\n")
        chapter_starts = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or (
                stripped and (stripped[0].isdigit() or "第" in stripped[:3])
                and any(kw in stripped[:6] for kw in ["章", "节", "部分", "篇"])
            ):
                chapter_starts.append(i)
        if not chapter_starts:
            sections = content.split("\n\n\n")
            if len(sections) > 1:
                pos = 0
                cursor_pos = sum(len(l) + 1 for l in lines[:current_line_num])
                for sec in sections:
                    sec_end = pos + len(sec)
                    if pos <= cursor_pos <= sec_end:
                        return sec[:4000]
                    pos = sec_end + 3
            return content[:4000]
        chapter_start = 0
        for s in chapter_starts:
            if s > current_line_num:
                break
            chapter_start = s
        chapter_end = len(lines)
        for s in chapter_starts:
            if s > chapter_start:
                chapter_end = s
                break
        return "\n".join(lines[chapter_start:chapter_end])[:4000]

    # ── Summarization ──

    def _summarize_chapter(self):
        if not self.current_file:
            return
        text = self._get_chapter_text()
        if not text or len(text) < 50:
            QMessageBox.information(self, "提示", "当前章节内容不足，无法生成总结")
            return
        prompt = CHAPTER_SUMMARY_PROMPT.format(text=text[:4000])
        self._status_msg("📝 正在生成章节总结...")
        self._run_in_thread(self._do_summary,
                            (self.current_file, "chapter", "auto", prompt),
                            self._on_summary_done)

    def _summarize_selection(self):
        cursor = self.reader.textCursor()
        if not cursor.hasSelection():
            QMessageBox.information(self, "提示", "请先选中要总结的文本")
            return
        text = cursor.selectedText()
        if len(text) < 30:
            QMessageBox.information(self, "提示", "选中文本太短（至少30字）")
            return
        prompt = SELECTION_SUMMARY_PROMPT.format(text=text[:3000])
        self._status_msg("📝 正在生成总结...")
        self._run_in_thread(self._do_summary,
                            (self.current_file, "selection", text[:50], prompt),
                            self._on_summary_done)

    def _do_summary(self, args):
        file_path, scope, scope_ref, prompt = args
        from backend.ollama_client import OllamaClient
        client = OllamaClient()
        result = client.chat(prompt, system_prompt=SYSTEM_PROMPT)
        client.close()
        knowledge_db.save_summary(file_path, scope, scope_ref, result)
        return result

    def _on_summary_done(self, result: str):
        self._switch_to_explain()
        html = result.replace("\n", "<br>")
        self.explain_browser.setHtml(
            f'<div style="color: #cdd6f4; font-size: 14px; line-height: 1.7;">{html}</div>'
        )
        self._status_msg("✅ 总结完成")

    # ── Utility ──

    def _status_msg(self, msg: str):
        self.status_label.setText(msg)

    def _run_in_thread(self, func, arg, callback):
        # Guard: don't stomp on a running thread
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)
        from PySide6.QtCore import Signal

        class _Worker(QThread):
            finished = Signal(object)
            error = Signal(str)

            def __init__(self, fn, a):
                super().__init__()
                self.fn = fn
                self.arg = a

            def run(self):
                try:
                    result = self.fn(self.arg)
                    self.finished.emit(result)
                except Exception as e:
                    self.error.emit(str(e))

        self._thread = _Worker(func, arg)
        self._thread.finished.connect(callback)
        self._thread.error.connect(lambda e: self._status_msg(f"⚠️ 操作失败: {e[:80]}"))
        self._thread.start()

    # ── Page navigation helpers ──

    def _toggle_toc(self):
        """Show/hide the TOC sidebar."""
        splitter = self.findChild(QSplitter)
        if self._toc_visible:
            # Save current sizes before hiding
            self._toc_sizes = splitter.sizes()
            self.toc_panel.hide()
            self._toc_visible = False
        else:
            self.toc_panel.show()
            self._toc_visible = True
            # Restore previous sizes after the splitter has re-laid-out
            if self._toc_sizes:
                QTimer.singleShot(0, lambda: splitter.setSizes(self._toc_sizes))

    def _toggle_page_nav(self, visible: bool):
        """Show/hide PDF page navigation controls."""
        self.status_bar.setVisible(visible)
        self.toolbar_zoom_label.setVisible(visible)
        self.status_zoom_label.setVisible(visible)
        self.prev_btn.setEnabled(visible and self.current_page > 0)
        self.next_btn.setEnabled(visible and self.current_page < self.total_pages - 1)

    def _prev_page(self):
        if hasattr(self, 'pdf_renderer'):
            self.pdf_renderer.prev_page()

    def _next_page(self):
        if hasattr(self, 'pdf_renderer'):
            self.pdf_renderer.next_page()

    # ── File management ──

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "",
            "支持的文件 (*.txt *.md *.pdf *.docx);;"
            "文本文件 (*.txt *.md);;PDF 文件 (*.pdf);;"
            "Word 文档 (*.docx);;所有文件 (*.*)",
        )
        if not file_path:
            return
        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".pdf":
                self._open_pdf(file_path)
            else:
                self._open_text(file_path)
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法读取文件:\n{e}")

    def _open_text(self, file_path: str):
        """Open a .txt/.md/.docx file in QPlainTextEdit."""
        content = parse_file(file_path)
        import re
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r"([^\n])\n([^\n])", r"\1\n\n\2", content)
        self.reader.setPlainText(content)
        self.current_file = file_path
        name = Path(file_path).name
        self.file_label.setText(f"📄 {name}")
        self.clear_btn.show()
        self.status_label.setText(f"📖 正在阅读: {name}")
        self.explain_browser.clear()
        self._toggle_page_nav(False)
        self.reader.show()
        # Set text TOC from headings
        lines = content.split("\n")
        self.toc_panel.set_text_toc(lines)
        # Restore highlights and enable summary
        self._load_highlights()
        self.summary_btn.show()

    def _open_pdf(self, file_path: str):
        """Open a PDF file for image-based rendering."""
        import fitz
        doc = fitz.open(file_path)
        name = Path(file_path).name
        self.current_file = file_path

        # Set TOC
        toc = doc.get_toc()
        self.toc_panel.set_pdf_toc(toc or [])

        # Replace reader with PdfRenderer in the splitter
        splitter = self.findChild(QSplitter)
        idx = splitter.indexOf(self.reader)
        self.pdf_renderer = PdfRenderer()
        self.pdf_renderer.load_document(doc)
        splitter.replaceWidget(idx, self.pdf_renderer)
        self.reader.hide()

        # Wire signals
        self.pdf_renderer.page_changed.connect(self._on_pdf_page_changed)
        self.pdf_renderer.text_selected.connect(self._on_pdf_text_selected)
        self.pdf_renderer.zoom_changed.connect(self._on_pdf_zoom_changed)
        self.pdf_renderer.auto_analyze_requested.connect(self._on_pdf_auto_analyze)

        # UI state
        self.total_pages = doc.page_count
        self.current_page = 0
        self._toggle_page_nav(True)
        self.file_label.setText(f"📄 {name}")
        self.clear_btn.show()
        self.status_label.setText(f"📄 {name}")
        self.explain_browser.clear()
        self._update_page_label()
        self.summary_btn.show()
        self.pdf_renderer.setFocus()

    def _on_toc_navigate(self, page: int):
        """Jump to PDF page from TOC click (TOC is 1-indexed, PdfRenderer 0-indexed)."""
        if hasattr(self, 'pdf_renderer') and self.pdf_renderer.doc:
            self.pdf_renderer.goto_page(page - 1)

    def _on_pdf_page_changed(self, page_num: int):
        self.current_page = page_num
        self._update_page_label()
        self.prev_btn.setEnabled(page_num > 0)
        self.next_btn.setEnabled(page_num < self.total_pages - 1)

    def _on_pdf_text_selected(self, text: str):
        """Trigger AI analysis on clicked PDF text."""
        self._trigger_analysis(text)

    def _on_pdf_auto_analyze(self, text: str):
        """Auto-analysis triggered by idle timer."""
        self._trigger_analysis(text)

    def _on_pdf_zoom_changed(self, zoom: float):
        self.current_zoom = zoom
        text = f"缩放: {zoom:.0%}"
        self.toolbar_zoom_label.setText(text)
        self.status_zoom_label.setText(text)

    def _update_page_label(self):
        self.page_label.setText(f"第 {self.current_page + 1}/{self.total_pages} 页")

    def _jump_to_page(self):
        """Parse page input and jump to that page."""
        text = self.page_input.text().strip()
        self.page_input.clear()
        try:
            page = int(text)
        except ValueError:
            return
        if hasattr(self, 'pdf_renderer'):
            # PdfRenderer uses 0-indexed pages
            self.pdf_renderer.goto_page(page - 1)

    def _trigger_analysis(self, text: str):
        """Send text to AI analysis (shared by PDF click and text cursor).
        Chain: explain concept -> extract concept name -> extract relations -> save to DB."""
        if not text or len(text) < 10:
            return
        text = text[:1200]
        prompt = PARAGRAPH_DETECT_PROMPT.format(text=text)
        if self._thread and self._thread.isRunning():
            return
        self._switch_to_explain()
        self._status_msg("🧠 后台分析中...")
        self._thread = QThread()
        self._worker = AiWorker(prompt)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._on_explain_done)
        self._worker.error.connect(self._on_explain_error)
        self._thread.start()
        # Store text for follow-up concept extraction
        self._last_analyzed_text = text

    def _close_file(self):
        self.reader.clear()
        if hasattr(self, 'pdf_renderer'):
            splitter = self.findChild(QSplitter)
            idx = splitter.indexOf(self.pdf_renderer)
            splitter.replaceWidget(idx, self.reader)
            self.pdf_renderer.close_document()
            self.pdf_renderer.deleteLater()
            del self.pdf_renderer
        self.reader.show()
        self.current_file = None
        self.file_label.setText("")
        self.clear_btn.hide()
        self.toc_panel.clear()
        self.status_zoom_label.setText("")
        self.explain_browser.clear()
        self.status_label.setText("📖 点击「打开文件」开始阅读")
        self._toggle_page_nav(False)
        self.summary_btn.hide()
        self._last_analyzed_text = None

    # ── Cursor tracking ──

    def _on_cursor_moved(self):
        """Called when the cursor position changes. Debounce the AI call."""
        if not self.current_file:
            return
        if hasattr(self, 'pdf_renderer'):
            return  # PDF uses click, not cursor-based
        if self._thread and self._thread.isRunning():
            self.status_label.setText("⏳ 等待上一条分析完成...")
        else:
            self.status_label.setText("🧠 正在分析...")
        self._detect_timer.start()  # restart timer

    def _get_current_paragraph(self) -> str:
        """Extract the full paragraph around the cursor (between blank lines)."""
        doc = self.reader.document()
        cursor = self.reader.textCursor()
        current_block = cursor.block()

        # Find paragraph start (previous blank line or document start)
        start_block = current_block
        while start_block.blockNumber() > 0:
            prev = start_block.previous()
            if prev.text().strip() == "":
                break
            start_block = prev

        # Find paragraph end (next blank line or document end)
        end_block = current_block
        while end_block.blockNumber() < doc.blockCount() - 1:
            nxt = end_block.next()
            if nxt.text().strip() == "":
                break
            end_block = nxt

        # Collect text from start_block to end_block
        lines = []
        block = start_block
        while True:
            lines.append(block.text())
            if block.blockNumber() == end_block.blockNumber():
                break
            block = block.next()

        return "\n".join(lines).strip()

    def _detect_concept(self):
        """Send current paragraph to AI for concept detection (background thread)."""
        # Don't queue another request while one is running
        if self._thread and self._thread.isRunning():
            return

        text = self._get_current_paragraph()
        if not text or len(text) < 10:
            self.status_label.setText("📖 已就绪")
            return

        text = text[:1200]
        prompt = PARAGRAPH_DETECT_PROMPT.format(text=text)

        self.status_label.setText("🧠 后台分析中...")

        # Fire up background thread
        self._current_prompt = prompt
        self._thread = QThread()
        self._worker = AiWorker(prompt)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # quit() must connect BEFORE our handler (signal order matters)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._on_explain_done)
        self._worker.error.connect(self._on_explain_error)
        self._thread.start()

    def _on_explain_done(self, response: str):
        """Handle successful explanation, then trigger concept extraction in background."""
        self._thread = None
        response = response.strip() or "(无响应)"
        html_text = response.replace("\n", "<br>")
        self.explain_browser.setHtml(
            f'<div style="color: #cdd6f4; font-size: 14px; line-height: 1.7;">'
            f'{html_text}</div>'
        )
        self._status_msg("⚡ 正在分析知识关联...")
        try:
            self._highlight_paragraph()
        except Exception:
            pass
        # Step 2: Extract concept name and relations in background
        if hasattr(self, '_last_analyzed_text') and self._last_analyzed_text:
            text = self._last_analyzed_text
            self._run_in_thread(self._do_concept_chain, text, self._on_concept_chain_done)

    def _do_concept_chain(self, text: str):
        """Background: detect primary concept -> extract relations."""
        concept_name = extract_concepts_for_text(text)
        if concept_name:
            extract_concepts(concept_name)
            return knowledge_db.get_relations(concept_name, max_depth=2)
        return None

    def _on_concept_chain_done(self, relations):
        """Concept extraction complete — silently update KG cache."""
        if relations:
            direct = [r for r in relations if r.get("_depth", 1) == 1]
            self._status_msg(f"✅ 分析完成 · 关联 {len(direct)} 个概念")
        else:
            self._status_msg("✅ 分析完成")
        self._last_analyzed_text = None

    def _on_explain_error(self, error_msg: str):
        """Handle explanation failure from background thread."""
        self._thread = None
        self._last_analyzed_text = None
        self.status_label.setText("⚠️ 分析失败")
        self.explain_browser.setHtml(
            f'<div style="color: #f38ba8; font-size: 13px;">'
            f'分析失败: {error_msg[:100]}</div>'
        )

    def _highlight_paragraph(self):
        """Visually mark the current paragraph with a temporary selection."""
        from PySide6.QtWidgets import QTextEdit
        from PySide6.QtGui import QTextFormat
        cursor = self.reader.textCursor()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self._parse_color("#2a1f1a"))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = cursor
        self.reader.setExtraSelections([selection])

    @staticmethod
    def _parse_color(hex_color: str):
        """Parse a hex color to QColor."""
        from PySide6.QtGui import QColor
        return QColor(hex_color)

    def close_client(self):
        """Stop any running thread on close."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
