"""
Knowledge graph panel — searchable concept tree + detail view.
Embedded in the reader tab's right panel alongside the explanation view.
"""
import sys
import os
_KG_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_KG_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QTextBrowser, QLabel, QPushButton,
)

from backend import knowledge_db


_RELATION_ICONS = {
    "包含": "🔗",
    "对立": "⚡",
    "发展": "🌱",
    "背景": "📜",
    "引用": "📖",
}


class KnowledgeGraphPanel(QWidget):
    """Searchable concept relationship tree + detail view."""

    concept_selected = Signal(str)  # emitted when user clicks search/analyze

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("🧠 知识图谱")
        header.setStyleSheet(
            "font-weight: 600; padding: 12px; font-size: 14px;"
            " border-bottom: 1px solid rgba(255,255,255,0.06);"
        )
        layout.addWidget(header)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(8, 8, 8, 4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索概念...")
        self.search_input.setStyleSheet(
            "QLineEdit { padding: 6px 10px; font-size: 13px;"
            " background: #1a2230; border: 1px solid rgba(255,255,255,0.08);"
            " border-radius: 6px; color: #d4d4d8; }"
        )
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("分析")
        self.search_btn.setFixedWidth(60)
        self.search_btn.setToolTip("搜索并分析概念关联")
        self.search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_btn)

        layout.addLayout(search_layout)

        # Tree widget for concept relations
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setStyleSheet(
            "QTreeWidget { background: transparent; border: none; font-size: 13px; }"
            "QTreeWidget::item { padding: 4px 0px; }"
            "QTreeWidget::item:hover { background: rgba(192,57,43,0.1); }"
            "QTreeWidget::item:selected { background: rgba(192,57,43,0.2); }"
        )
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree, 1)

        # Detail panel at bottom
        self.detail = QTextBrowser()
        self.detail.setMaximumHeight(150)
        self.detail.setStyleSheet(
            "QTextBrowser { background: #161d27; border-top: 1px solid rgba(255,255,255,0.06);"
            " padding: 8px; font-size: 12px; color: #9ca3af; }"
        )
        self.detail.setPlaceholderText("点击关联概念查看详情")
        layout.addWidget(self.detail)

        self._show_empty()

    def _show_empty(self):
        self.tree.clear()
        empty = QTreeWidgetItem(self.tree)
        empty.setText(0, "输入概念名搜索关联")
        empty.setFlags(Qt.ItemFlag.NoItemFlags)
        self.detail.clear()

    def search(self, concept_name: str):
        """Search and display relations for a concept (alias for display_concept)."""
        self.display_concept(concept_name)

    def _on_search(self):
        concept_name = self.search_input.text().strip()
        if not concept_name:
            return
        self.concept_selected.emit(concept_name)

    def display_concept(self, concept_name: str):
        """Display cached or fresh relations for a concept."""
        self.search_input.setText(concept_name)
        self.tree.clear()

        concept = knowledge_db.get_concept(concept_name)
        relations = knowledge_db.get_relations(concept_name, max_depth=2)

        if not relations:
            empty = QTreeWidgetItem(self.tree)
            empty.setText(0, "暂无关联数据 — 点击「分析」按钮生成")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            return

        # Root: concept_name
        root = QTreeWidgetItem(self.tree)
        root.setText(0, f"📌 {concept_name}")
        root.setData(0, Qt.ItemDataRole.UserRole, concept_name)
        font = root.font(0)
        font.setBold(True)
        root.setFont(0, font)

        # Direct relations
        direct = [r for r in relations if r.get("_depth", 1) == 1]
        for r in direct:
            icon = _RELATION_ICONS.get(r["relation_type"], "➤")
            item = QTreeWidgetItem(root)
            item.setText(0, f"{icon} {r['target_name']}  [{r['relation_type']}]")
            item.setData(0, Qt.ItemDataRole.UserRole, r["target_name"])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, r.get("explanation", ""))

            # Second-level relations
            sub_rels = [
                s for s in relations
                if s.get("_depth") == 2 and s.get("_parent") == r["target_name"]
            ]
            for s in sub_rels:
                icon2 = _RELATION_ICONS.get(s["relation_type"], "➤")
                sub_item = QTreeWidgetItem(item)
                sub_item.setText(0, f"{icon2} {s['target_name']}  [{s['relation_type']}]")
                sub_item.setData(0, Qt.ItemDataRole.UserRole, s["target_name"])
                sub_item.setData(0, Qt.ItemDataRole.UserRole + 1, s.get("explanation", ""))

        self.tree.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        explanation = item.data(0, Qt.ItemDataRole.UserRole + 1) or ""
        concept_name = item.data(0, Qt.ItemDataRole.UserRole) or ""
        if explanation:
            self.detail.setHtml(
                f'<div style="color: #d4d4d8; font-size: 13px; line-height: 1.6;">'
                f'<b>{concept_name}</b><br>{explanation}</div>'
            )
