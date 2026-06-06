"""
TocPanel — table of contents sidebar.
PDF: tree from doc.get_toc()
TXT/MD: flat list from heading regex
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QListWidget, QListWidgetItem, QStackedWidget,
)


class TocPanel(QWidget):
    """Table of contents panel. Tree for PDF, flat list for text files."""

    navigate_requested = Signal(int)  # page number (1-indexed for PDF, 0 for non-PDF)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("📖 目录")
        header.setProperty("class", "panel-header")
        layout.addWidget(header)

        self.stack = QStackedWidget()

        self.empty_label = QLabel("📂 打开文件后\n自动显示目录")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setProperty("class", "empty-state")
        self.stack.addWidget(self.empty_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setProperty("class", "sidebar")
        self.tree.itemClicked.connect(self._on_tree_clicked)
        self.stack.addWidget(self.tree)

        self.list_widget = QListWidget()
        self.list_widget.setProperty("class", "sidebar")
        self.list_widget.itemClicked.connect(self._on_list_clicked)
        self.stack.addWidget(self.list_widget)

        layout.addWidget(self.stack, 1)

    def set_pdf_toc(self, toc: list):
        """Populate tree from fitz doc.get_toc() — [(level, title, page), ...]."""
        self.tree.clear()
        if not toc:
            self.stack.setCurrentWidget(self.empty_label)
            return

        stack = [self.tree]
        for level, title, page in toc:
            level = max(1, level)
            while len(stack) > level:
                stack.pop()
            item = QTreeWidgetItem(stack[-1])
            item.setText(0, title)
            item.setData(0, Qt.ItemDataRole.UserRole, page)
            item.setToolTip(0, f"第 {page} 页")
            while len(stack) <= level:
                stack.append(item)

        self.tree.expandAll()
        self.stack.setCurrentWidget(self.tree)

    def set_text_toc(self, lines: list[str]):
        """Populate flat list from text headings (## / 第X章 / 一、...)."""
        self.list_widget.clear()
        headings = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())
            if re.match(r'^第[一二三四五六七八九十百千]+[章节篇部]', stripped):
                headings.append(stripped)

        if not headings:
            self.stack.setCurrentWidget(self.empty_label)
            return

        for title in headings:
            item = QListWidgetItem(title)
            self.list_widget.addItem(item)

        self.stack.setCurrentWidget(self.list_widget)

    def clear(self):
        self.tree.clear()
        self.list_widget.clear()
        self.stack.setCurrentWidget(self.empty_label)

    # ── Internal ──

    def _on_tree_clicked(self, item: QTreeWidgetItem, _column: int):
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page:
            self.navigate_requested.emit(int(page))

    def _on_list_clicked(self, item: QListWidgetItem):
        # Text TOC: can't jump to exact page in flat text renderer
        pass
