"""
Library tab — document management for the vector database.
Drag-drop import, file list with chunk counts, delete and re-index.
All ingestion runs in background threads to prevent UI freezing.
"""
import sys
import os
_LIB_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_LIB_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from pathlib import Path
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QProgressBar,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from backend.rag_engine import RAGEngine
from backend.config import DOCUMENTS_DIR
from gui.ai_worker import IngestWorker, DirIngestWorker


class LibraryTab(QWidget):
    """Document library — manage vector DB contents."""

    def __init__(self):
        super().__init__()
        self.engine = RAGEngine()
        self._thread: QThread | None = None
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
        self.scan_btn.clicked.connect(self._scan_directory)
        header.addWidget(self.scan_btn)

        self.add_btn = QPushButton("📄 添加文件")
        self.add_btn.clicked.connect(self._add_file)
        header.addWidget(self.add_btn)

        layout.addLayout(header)

        # ── Drop zone hint ──
        self.drop_hint = QLabel(
            "📥 拖拽文件到此处导入到向量库（支持 .txt .md .pdf .docx）"
        )
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(
            "border: 2px dashed #333642; border-radius: 8px;"
            " padding: 20px; color: #555870; font-size: 14px;"
        )
        layout.addWidget(self.drop_hint)

        # ── Progress ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #989aab; font-size: 12px;")
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        # ── Document list ──
        self.doc_list = QListWidget()
        self.doc_list.setStyleSheet(
            "QListWidget { background: #14151c; border: 1px solid #252730;"
            " border-radius: 6px; padding: 8px; }"
            "QListWidget::item { padding: 10px 12px; border-bottom: 1px solid #1e202a; }"
        )
        layout.addWidget(self.doc_list, 1)

        # ── Bottom bar ──
        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #555870; font-size: 12px;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        self.reindex_btn = QPushButton("🔄 全部重新嵌入")
        self.reindex_btn.clicked.connect(self._reindex_all)
        bottom.addWidget(self.reindex_btn)

        self.clear_btn = QPushButton("🗑️ 清空向量库")
        self.clear_btn.setStyleSheet(
            "background: #5a2020; padding: 6px 16px; font-size: 12px;"
        )
        self.clear_btn.clicked.connect(self._clear_all)
        bottom.addWidget(self.clear_btn)

        layout.addLayout(bottom)

    # ── Busy state management ──

    def _set_busy(self, busy: bool):
        """Enable/disable controls during background work."""
        self.add_btn.setEnabled(not busy)
        self.scan_btn.setEnabled(not busy)
        self.reindex_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.setAcceptDrops(not busy)
        if busy:
            self.progress.show()
            self.progress_label.show()
        else:
            self.progress.hide()
            self.progress_label.hide()
            self._thread = None

    # ── Drag & Drop ──

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            if ext in (".txt", ".md", ".pdf", ".docx"):
                files.append(path)
        if files:
            self._ingest_files(files)

    # ── Actions ──

    def _add_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "",
            "支持的文件 (*.txt *.md *.pdf *.docx);;所有文件 (*.*)",
        )
        if files:
            self._ingest_files(files)

    def _scan_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择文件夹", str(DOCUMENTS_DIR)
        )
        if not dir_path:
            return
        self._set_busy(True)
        self.progress_label.setText("正在扫描目录...")

        self._thread = QThread()
        self._worker = DirIngestWorker(dir_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress_label.setText)
        self._worker.finished.connect(self._on_dir_done)
        self._worker.error.connect(self._on_dir_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _ingest_files(self, paths: list[str]):
        """Queue one file at a time for ingestion."""
        self._file_queue = list(paths)
        self._set_busy(True)
        self._ingest_next()

    def _ingest_next(self):
        """Ingest the next file in the queue."""
        if not self._file_queue:
            self._set_busy(False)
            self._refresh()
            return

        file_path = self._file_queue.pop(0)
        name = Path(file_path).name
        self.progress_label.setText(f"正在处理 ({len(self._file_queue) + 1} 个剩余): {name}")

        self._thread = QThread()
        self._worker = IngestWorker(file_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_file_done)
        self._worker.error.connect(self._on_file_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_file_done(self, filename: str, chunk_count: int):
        """Single file ingested successfully."""
        self._ingest_next()  # process next file in queue

    def _on_file_error(self, filename: str, error_msg: str):
        """Single file ingestion failed."""
        QMessageBox.warning(self, "导入失败", f"{filename}: {error_msg}")
        self._ingest_next()  # continue with next file

    def _on_dir_done(self, total: int):
        """Directory scan complete."""
        self._set_busy(False)
        self._refresh()
        QMessageBox.information(self, "扫描完成", f"已导入 {total} 个片段")

    def _on_dir_error(self, error_msg: str):
        """Directory scan failed."""
        self._set_busy(False)
        QMessageBox.warning(self, "扫描失败", error_msg)

    def _reindex_all(self):
        reply = QMessageBox.question(
            self, "重新嵌入",
            "将清空向量库并重新导入 documents/ 目录下的所有文件。\n确定继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self._set_busy(True)
        self.progress_label.setText("正在清空向量库...")

        # Clear in background too
        self._reindex_thread = QThread()
        self._reindex_worker = DirIngestWorker(str(DOCUMENTS_DIR))

        # Override behavior: clear first, then scan
        original_run = self._reindex_worker.run

        def reindex_run():
            try:
                self.progress.emit("正在清空旧嵌入...")
                engine = RAGEngine()
                count = engine.collection.count()
                if count > 0:
                    engine.collection.delete(ids=engine.collection.get()["ids"])
                engine.close()
                self.progress.emit("正在重新导入...")
                engine2 = RAGEngine()
                total = engine2.ingest_directory(str(DOCUMENTS_DIR))
                engine2.close()
                self.finished.emit(total)
            except Exception as e:
                self.error.emit(str(e))

        self._reindex_worker.run = reindex_run
        self._reindex_worker.moveToThread(self._reindex_thread)
        self._reindex_thread.started.connect(self._reindex_worker.run)
        self._reindex_worker.finished.connect(self._on_dir_done)
        self._reindex_worker.error.connect(self._on_dir_error)
        self._reindex_worker.finished.connect(self._reindex_thread.quit)
        self._reindex_worker.error.connect(self._reindex_thread.quit)
        self._reindex_thread.start()

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
