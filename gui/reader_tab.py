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

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QTextBrowser, QSplitter, QLabel,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
)
from pathlib import Path

from backend.ollama_client import OllamaClient


PARAGRAPH_DETECT_PROMPT = (
    "以下是用户正在阅读的一段文本。请判断这段文字是否在讨论某个核心概念或重要观点。\n"
    "如果是，请用中文简要解释这个概念（50-100字），并指出这段文字的核心要点。\n"
    "如果只是过渡段落、叙述性文字或无需解释的简单内容，请只回复「无需解释」。\n\n"
    "文本：\n{text}"
)


class ReaderTab(QWidget):
    """Text reader with automatic concept detection and explanation."""

    RECENT_FILES_KEY = "spark_recent_files"

    def __init__(self):
        super().__init__()
        self.client = OllamaClient()
        self.current_file: str | None = None
        self._detect_timer = QTimer()
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(800)  # debounce 800ms
        self._detect_timer.timeout.connect(self._detect_concept)
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
            "QPlainTextEdit { background: #13131f; color: #f0e6d3;"
            " font-size: 15px; padding: 16px; line-height: 1.8;"
            " border: none; }"
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
            "文本文件 (*.txt *.md);;所有文件 (*.*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
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
        if self.current_file:
            self.status_label.setText("🧠 正在分析...")
            self._detect_timer.start()  # restart timer

    def _get_current_paragraph(self) -> str:
        """Extract the paragraph around the cursor."""
        cursor = self.reader.textCursor()
        # Select the current paragraph (between blank lines)
        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
        cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
        text = cursor.selectedText().strip()
        if not text:
            # Try to select surrounding text within a reasonable range
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            text = cursor.selectedText().strip()
        return text

    def _detect_concept(self):
        """Send current paragraph to AI for concept detection."""
        text = self._get_current_paragraph()
        if not text or len(text) < 10:
            self.status_label.setText("📖 已就绪")
            return

        prompt = PARAGRAPH_DETECT_PROMPT.format(text=text[:800])  # limit length

        try:
            response = self.client.chat(prompt)
            response = response.strip()

            if "无需解释" in response:
                self.explain_browser.clear()
                self.explain_browser.setPlaceholderText("当前段落无需专门解释。")
                self.status_label.setText("📖 已就绪")
            else:
                # Highlight the current paragraph in the reader
                self._highlight_paragraph()
                self.explain_browser.setHtml(
                    f'<div style="color: #c4956a; font-size: 13px; line-height: 1.6;">'
                    f'{response}</div>'
                )
                self.status_label.setText("✅ 概念已识别")
        except Exception:
            self.status_label.setText("⚠️ 分析失败")
            self.explain_browser.clear()
            self.explain_browser.setPlaceholderText("分析失败，请稍后重试。")

    def _highlight_paragraph(self):
        """Visually mark the current paragraph with a temporary selection."""
        cursor = self.reader.textCursor()
        # Briefly highlight, then move to the start
        extra_selections = []
        selection = self.reader.ExtraSelection()
        selection.format.setBackground(self._parse_color("#2a1f1a"))
        selection.format.setProperty(
            self.reader.FormatProperty.FullWidthSelection, True
        )
        selection.cursor = cursor
        extra_selections.append(selection)
        self.reader.setExtraSelections(extra_selections)

    @staticmethod
    def _parse_color(hex_color: str):
        """Parse a hex color to QColor."""
        from PySide6.QtGui import QColor
        return QColor(hex_color)

    def close_client(self):
        self.client.close()
