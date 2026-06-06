"""
Library tab — document management for the vector database.
Drag-drop import, file list with chunk counts, delete and re-index.
"""
import sys
import os
_LIB_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_LIB_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QProgressBar, QSplitter, QFrame,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from backend.rag_engine import RAGEngine
from backend.config import DOCUMENTS_DIR


class LibraryTab(QWidget):
    """Document library — manage vector DB contents."""

    def __init__(self):
        super().__init__()
        self.engine = RAGEngine()
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("📚 文档库")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 13px;")
        header.addWidget(self.status_label)
        header.addStretch()

        self.scan_btn = QPushButton("📁 扫描文件夹")
        self.scan_btn.setStyleSheet("background: #555; padding: 6px 16px; font-size: 12px;")
        self.scan_btn.clicked.connect(self._scan_directory)
        header.addWidget(self.scan_btn)

        self.add_btn = QPushButton("📄 添加文件")
        self.add_btn.clicked.connect(self._add_file)
        header.addWidget(self.add_btn)

        layout.addLayout(header)

        # ── Drop zone hint ──
        self.drop_hint = QLabel(
            "📥 拖拽 .txt / .md 文件到此处导入到向量库"
        )
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(
            "border: 2px dashed #2a2a3e; border-radius: 8px;"
            " padding: 20px; color: #666; font-size: 14px;"
        )
        layout.addWidget(self.drop_hint)

        # ── Progress bar (hidden by default) ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.hide()
        layout.addWidget(self.progress)

        # ── Document list ──
        self.doc_list = QListWidget()
        self.doc_list.setStyleSheet(
            "QListWidget { background: #13131f; border: 1px solid #2a2a3e;"
            " border-radius: 6px; padding: 8px; }"
            "QListWidget::item { padding: 10px 12px; border-bottom: 1px solid #2a2a3e; }"
        )
        layout.addWidget(self.doc_list, 1)

        # ── Bottom bar ──
        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888; font-size: 12px;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        self.reindex_btn = QPushButton("🔄 全部重新嵌入")
        self.reindex_btn.setStyleSheet("background: #555; padding: 6px 16px; font-size: 12px;")
        self.reindex_btn.clicked.connect(self._reindex_all)
        bottom.addWidget(self.reindex_btn)

        self.clear_btn = QPushButton("🗑️ 清空向量库")
        self.clear_btn.setStyleSheet(
            "background: #5a2020; padding: 6px 16px; font-size: 12px;"
        )
        self.clear_btn.clicked.connect(self._clear_all)
        bottom.addWidget(self.clear_btn)

        layout.addLayout(bottom)

    # ── Drag & Drop ──

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.endswith(".txt") or path.endswith(".md"):
                self._ingest_file(path)
        self._refresh()

    # ── Actions ──

    def _add_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "",
            "文本文件 (*.txt *.md);;所有文件 (*.*)",
        )
        if not files:
            return
        for f in files:
            self._ingest_file(f)
        self._refresh()

    def _scan_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择文件夹", str(DOCUMENTS_DIR)
        )
        if not dir_path:
            return
        self.progress.show()
        self.progress.setRange(0, 0)
        try:
            count = self.engine.ingest_directory(dir_path)
            QMessageBox.information(self, "扫描完成", f"已导入 {count} 个片段")
        except Exception as e:
            QMessageBox.warning(self, "扫描失败", str(e))
        finally:
            self.progress.hide()
        self._refresh()

    def _ingest_file(self, path: str):
        self.progress.show()
        self.progress.setRange(0, 0)
        try:
            self.engine.ingest_file(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"{Path(path).name}: {e}")
        finally:
            self.progress.hide()

    def _reindex_all(self):
        reply = QMessageBox.question(
            self, "重新嵌入",
            "将清空向量库并重新导入 documents/ 目录下的所有文件。\n确定继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self.progress.show()
        self.progress.setRange(0, 0)
        try:
            # Clear and re-ingest
            count = self.engine.collection.count()
            if count > 0:
                self.engine.collection.delete(
                    ids=self.engine.collection.get()["ids"]
                )
            total = self.engine.ingest_directory(str(DOCUMENTS_DIR))
            QMessageBox.information(
                self, "重新嵌入完成",
                f"已清除旧嵌入，重新导入 {total} 个片段。"
            )
        except Exception as e:
            QMessageBox.warning(self, "重新嵌入失败", str(e))
        finally:
            self.progress.hide()
        self._refresh()

    def _clear_all(self):
        reply = QMessageBox.question(
            self, "清空向量库",
            "确定要删除向量库中的所有文档片段？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        try:
            count = self.engine.collection.count()
            if count > 0:
                self.engine.collection.delete(
                    ids=self.engine.collection.get()["ids"]
                )
            QMessageBox.information(self, "已清空", f"已删除 {count} 个片段")
        except Exception as e:
            QMessageBox.warning(self, "清空失败", str(e))
        self._refresh()

    def _refresh(self):
        """Refresh the document list from ChromaDB."""
        self.doc_list.clear()
        try:
            count = self.engine.collection.count()
            if count == 0:
                self.doc_list.addItem("(向量库为空)")
                self.count_label.setText("0 个片段")
                self.status_label.setText("空")
                return

            # Group by source file
            results = self.engine.collection.get(include=["metadatas"])
            sources: dict[str, int] = {}
            for m in results["metadatas"]:
                src = m.get("source", "未知来源")
                sources[src] = sources.get(src, 0) + 1

            for src, cnt in sorted(sources.items()):
                item = QListWidgetItem(f"📄 {src}   —   {cnt} 个片段")
                item.setToolTip(f"{src}: {cnt} chunks")
                self.doc_list.addItem(item)

            self.count_label.setText(f"{count} 个片段 · {len(sources)} 个文件")
            self.status_label.setText(f"{len(sources)} 文件")

        except Exception as e:
            self.doc_list.addItem(f"(加载失败: {e})")
            self.count_label.setText("?")
            self.status_label.setText("错误")

    def closeEvent(self, event):
        self.engine.close()
        super().closeEvent(event)
