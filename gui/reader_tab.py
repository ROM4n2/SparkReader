"""
Reader tab — built-in text reader with smart concept detection.
Opens .txt/.md files, tracks cursor position, and auto-explains core concepts.
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QTextBrowser, QSplitter, QLabel,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
)
from pathlib import Path

from gui.ai_worker import AiWorker
from gui.file_parser import parse_file


PARAGRAPH_DETECT_PROMPT = (
    "你是一个马列经典著作阅读助手。用户正在阅读一段文本，请做两件事：\n"
    "1. 指出这段文本在讨论什么核心概念或话题\n"
    "2. 用1-3句话简要解释这个概念\n\n"
    "文本：\n{text}"
)


class ReaderTab(QWidget):
    """Text reader with automatic concept detection and explanation."""

    def __init__(self):
        super().__init__()
        self.current_file: str | None = None
        self._detect_timer = QTimer()
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(800)  # debounce 800ms
        self._detect_timer.timeout.connect(self._detect_concept)
        self._thread: QThread | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 8, 12, 8)

        self.open_btn = QPushButton("📂 打开文件")
        self.open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(self.open_btn)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #888; font-size: 13px;")
        toolbar.addWidget(self.file_label)
        toolbar.addStretch()

        self.clear_btn = QPushButton("✕ 关闭")
        self.clear_btn.setStyleSheet("background: #555; padding: 6px 16px; font-size: 12px;")
        self.clear_btn.clicked.connect(self._close_file)
        self.clear_btn.hide()
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # ── Main splitter: reader + explanation ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: text reader
        self.reader = QPlainTextEdit()
        self.reader.setReadOnly(True)
        self.reader.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #181825; color: #e0e0e0;"
            "  font-size: 15px; padding: 20px 24px;"
            "  line-height: 1.9; border: none;"
            "  font-family: 'Microsoft YaHei', 'Noto Sans SC', 'Segoe UI', sans-serif;"
            "}"
        )
        self.reader.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        # Add paragraph spacing by inserting extra blank line between paragraphs
        self.reader.document().setDefaultStyleSheet(
            "p { margin-bottom: 12px; }"
        )
        self.reader.cursorPositionChanged.connect(self._on_cursor_moved)
        splitter.addWidget(self.reader)

        # Right: explanation panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        explain_header = QLabel("🧠 概念解释")
        explain_header.setStyleSheet(
            "font-weight: 600; padding: 12px; font-size: 14px;"
            " border-bottom: 1px solid #2a2a3e;"
        )
        right_layout.addWidget(explain_header)

        self.explain_browser = QTextBrowser()
        self.explain_browser.setOpenExternalLinks(False)
        self.explain_browser.setPlaceholderText("点击文本中的段落，AI 会自动识别核心概念并在此显示解释。")
        right_layout.addWidget(self.explain_browser, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([500, 300])

        layout.addWidget(splitter, 1)

        # ── Status bar ──
        self.status_label = QLabel("📖 点击「打开文件」开始阅读")
        self.status_label.setStyleSheet(
            "color: #666; font-size: 12px; padding: 4px 12px;"
            " border-top: 1px solid #2a2a3e;"
        )
        layout.addWidget(self.status_label)

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

        try:
            content = parse_file(file_path)
            # Normalize paragraph spacing: ensure double newline between paragraphs
            import re
            content = re.sub(r"\n{3,}", "\n\n", content)  # collapse excessive gaps
            content = re.sub(r"([^\n])\n([^\n])", r"\1\n\n\2", content)  # single newline → paragraph break
            self.reader.setPlainText(content)
            self.current_file = file_path
            name = Path(file_path).name
            self.file_label.setText(f"📄 {name}")
            self.clear_btn.show()
            self.status_label.setText(f"📖 正在阅读: {name}")
            self.explain_browser.clear()
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法读取文件:\n{e}")

    def _close_file(self):
        self.reader.clear()
        self.current_file = None
        self.file_label.setText("")
        self.clear_btn.hide()
        self.explain_browser.clear()
        self.status_label.setText("📖 点击「打开文件」开始阅读")

    # ── Cursor tracking ──

    def _on_cursor_moved(self):
        """Called when the cursor position changes. Debounce the AI call."""
        if not self.current_file:
            return
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
        self._worker.finished.connect(self._on_explain_done)
        self._worker.error.connect(self._on_explain_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_explain_done(self, response: str):
        """Handle successful explanation from background thread."""
        self._thread = None
        response = response.strip() or "(无响应)"
        html_text = response.replace("\n", "<br>")
        self.explain_browser.setHtml(
            f'<div style="color: #cdd6f4; font-size: 14px; line-height: 1.7;">'
            f'{html_text}</div>'
        )
        self.status_label.setText("✅ 分析完成")
        try:
            self._highlight_paragraph()
        except Exception:
            pass

    def _on_explain_error(self, error_msg: str):
        """Handle explanation failure from background thread."""
        self._thread = None
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
