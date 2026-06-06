"""
Chat tab — conversation sidebar, message display, mode selector, input bar.
Three modes: RAG / Clipboard Context / Direct Q&A.
"""
import sys
import os
_CHAT_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_CHAT_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)                                    # project root
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))           # backend/ for config imports

from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextBrowser,
    QLineEdit, QPushButton, QSplitter, QLabel,
    QFrame, QMenu, QMessageBox, QSizePolicy,
)

from gui import conversation_db as db
from gui.ai_worker import AiWorker
from backend.config import DIRECT_QA_TEMPLATE, CONTEXT_QA_TEMPLATE


class ChatTab(QWidget):
    """Interactive Q&A with conversation management."""

    MODES = [
        ("rag", "📚 RAG 问答"),
        ("context", "📋 上下文"),
        ("direct", "💬 直接"),
    ]

    # Shared clipboard reference (set by main_window's clipboard monitor)
    latest_clipboard = ""

    def __init__(self, settings_getter=None):
        """
        Args:
            settings_getter: optional callable returning a SettingsTab
                (used to read model choice at send time)
        """
        super().__init__()
        self.settings_getter = settings_getter
        self.current_conv_id: int | None = None
        self.mode = "rag"  # default
        self._thread: QThread | None = None
        self._build_ui()
        self._load_conversation_list()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: conversation sidebar ──
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(4)

        # Top bar
        top_bar = QHBoxLayout()
        top_label = QLabel("📜 历史")
        top_label.setStyleSheet("font-weight: 600; padding: 8px 12px;")
        new_btn = QPushButton("＋")
        new_btn.setFixedSize(32, 32)
        new_btn.setStyleSheet("font-size: 18px; padding: 0;")
        new_btn.clicked.connect(self._new_conversation)
        top_bar.addWidget(top_label)
        top_bar.addStretch()
        top_bar.addWidget(new_btn)
        sidebar_layout.addLayout(top_bar)

        self.conv_list = QListWidget()
        self.conv_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.conv_list.customContextMenuRequested.connect(self._show_conv_menu)
        self.conv_list.currentRowChanged.connect(self._on_conv_selected)
        sidebar_layout.addWidget(self.conv_list)

        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(280)
        splitter.addWidget(sidebar)

        # ── Right: messages + input ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Mode selector
        mode_bar = QHBoxLayout()
        mode_bar.setContentsMargins(8, 8, 8, 8)
        self.mode_btns = []
        for key, label in self.MODES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(self._mode_style(False))
            btn.clicked.connect(lambda checked, k=key: self._set_mode(k))
            self.mode_btns.append(btn)
            mode_bar.addWidget(btn)
        mode_bar.addStretch()
        right_layout.addLayout(mode_bar)

        # Message area
        self.msg_browser = QTextBrowser()
        self.msg_browser.setOpenExternalLinks(True)
        right_layout.addWidget(self.msg_browser, 1)

        # Input bar
        input_bar = QHBoxLayout()
        input_bar.setContentsMargins(8, 8, 8, 8)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入问题... (Enter 发送)")
        self.input_edit.returnPressed.connect(self._send_message)
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self._send_message)
        input_bar.addWidget(self.input_edit)
        input_bar.addWidget(self.send_btn)
        right_layout.addLayout(input_bar)

        splitter.addWidget(right)
        splitter.setSizes([220, 680])
        layout.addWidget(splitter)

        # Default to RAG if vector DB has content, else direct
        self._auto_detect_default_mode()

    def _mode_style(self, active: bool) -> str:
        if active:
            return (
                "QPushButton { background: #c4956a; color: #0f0f1a;"
                " border: none; border-radius: 12px; padding: 4px 14px; font-size: 12px; }"
            )
        return (
            "QPushButton { background: #333; color: #888;"
            " border: none; border-radius: 12px; padding: 4px 14px; font-size: 12px; }"
        )

    def _set_mode(self, mode: str):
        self.mode = mode
        for btn, (key, _) in zip(self.mode_btns, self.MODES):
            btn.setChecked(key == mode)
            btn.setStyleSheet(self._mode_style(key == mode))

    def _auto_detect_default_mode(self):
        try:
            from backend.rag_engine import RAGEngine
            engine = RAGEngine()
            has_docs = engine.collection.count() > 0
            engine.close()
            self._set_mode("rag" if has_docs else "direct")
        except Exception:
            self._set_mode("direct")

    # ── Conversation management ──

    def _load_conversation_list(self):
        self.conv_list.blockSignals(True)
        self.conv_list.clear()
        conversations = db.list_conversations()
        if not conversations:
            # Auto-create first conversation
            cid = db.create_conversation()
            conversations = db.list_conversations()

        # Group by date
        today = datetime.now().strftime("%Y-%m-%d")
        groups: dict[str, list] = {}
        for conv in conversations:
            date = conv["updated_at"][:10]
            if date == today:
                group = "今天"
            else:
                try:
                    d = datetime.strptime(date, "%Y-%m-%d")
                    diff = (datetime.now() - d).days
                    group = "昨天" if diff == 1 else "本周" if diff <= 7 else "更早"
                except ValueError:
                    group = "更早"
            groups.setdefault(group, []).append(conv)

        group_order = ["今天", "昨天", "本周", "更早"]
        for g in group_order:
            if g in groups:
                header = QListWidgetItem(f"── {g} ──")
                header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                header.setForeground(Qt.GlobalColor.gray)
                self.conv_list.addItem(header)
                for conv in groups[g]:
                    item = QListWidgetItem(f"{conv['title']}")
                    item.setData(Qt.ItemDataRole.UserRole, conv["id"])
                    # Show time
                    time_str = conv["updated_at"][11:16] if len(conv["updated_at"]) > 16 else ""
                    item.setToolTip(f"{conv['title']}\n{time_str}")
                    self.conv_list.addItem(item)

        self.conv_list.blockSignals(False)
        if self.conv_list.count() > 0:
            self.conv_list.setCurrentRow(0)

    def _on_conv_selected(self, row: int):
        item = self.conv_list.item(row)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return
        self.current_conv_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_messages()

    def _load_messages(self):
        self.msg_browser.clear()
        if self.current_conv_id is None:
            return
        messages = db.get_messages(self.current_conv_id)
        if not messages:
            self.msg_browser.setHtml(
                '<div style="color: #555870; text-align: center; '
                'padding: 40px 20px; font-size: 14px; line-height: 2;">'
                '💬 在下方输入问题开始对话<br><br>'
                '三种模式：<br>'
                '  📚 RAG 问答 — 基于导入文档回答<br>'
                '  📋 上下文 — 基于剪贴板内容回答<br>'
                '  💬 直接 — 直接向 AI 提问'
                '</div>'
            )
            return
        for msg in messages:
            prefix = "🧑" if msg["role"] == "user" else "🤖"
            mode_tag = f" [{msg['mode']}]" if msg["mode"] != "direct" else ""
            html = (
                f'<div style="margin: 8px 0; padding: 8px 12px;'
                f' border-left: 3px solid {"#c4956a" if msg["role"] == "assistant" else "#555"};'
                f' border-radius: 4px;">'
                f'<div style="font-size: 12px; color: #888;">{prefix} {msg["created_at"][:16]}{mode_tag}</div>'
                f'<div style="margin-top: 4px;">{msg["content"]}</div>'
                f'</div>'
            )
            self.msg_browser.append(html)
        # Scroll to bottom
        self.msg_browser.verticalScrollBar().setValue(
            self.msg_browser.verticalScrollBar().maximum()
        )

    def _new_conversation(self):
        cid = db.create_conversation()
        self._load_conversation_list()
        # Select the new conversation (first item after reload)
        for i in range(self.conv_list.count()):
            item = self.conv_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == cid:
                self.conv_list.setCurrentRow(i)
                break

    def _show_conv_menu(self, pos):
        item = self.conv_list.itemAt(pos)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu()
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        action = menu.exec(self.conv_list.viewport().mapToGlobal(pos))

        if action == rename_action:
            from PySide6.QtWidgets import QInputDialog
            title, ok = QInputDialog.getText(self, "重命名", "新名称:", text=item.text())
            if ok and title.strip():
                db.rename_conversation(conv_id, title.strip())
                self._load_conversation_list()
        elif action == delete_action:
            reply = QMessageBox.question(
                self, "确认删除", "确定要删除这个对话吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                db.delete_conversation(conv_id)
                self._load_conversation_list()

    # ── Sending messages ──

    def _send_message(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        if text.lower() in ("/exit", "/quit"):
            self.window().close()
            return
        if text.lower() == "/clear":
            self.msg_browser.clear()
            self.input_edit.clear()
            return

        # Don't queue another request while one is running
        if self._thread and self._thread.isRunning():
            QMessageBox.information(self, "提示", "正在等待上一条回答，请稍后。")
            return

        # Ensure we have a conversation
        if self.current_conv_id is None:
            self.current_conv_id = db.create_conversation()
            self._load_conversation_list()

        # Show user message immediately
        db.add_message(self.current_conv_id, "user", text, self.mode)
        self._load_messages()
        self.input_edit.clear()
        self.send_btn.setEnabled(False)
        self.send_btn.setText("思考中...")

        # Build prompt and fire background thread
        try:
            prompt = self._build_prompt(text)
        except Exception as e:
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")
            QMessageBox.warning(self, "错误", f"构建问题失败:\n{e}")
            return

        self._thread = QThread()
        self._worker = AiWorker(prompt)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # quit() before handler (signal order matters)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._on_chat_done)
        self._worker.error.connect(self._on_chat_error)
        self._thread.start()

    def _on_chat_done(self, response: str):
        """Handle successful AI response from background thread."""
        self._thread = None
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        if self.current_conv_id is None:
            return
        db.add_message(self.current_conv_id, "assistant", response.strip(), self.mode)
        db.auto_title(self.current_conv_id)
        self._load_conversation_list()
        self._load_messages()

    def _on_chat_error(self, error_msg: str):
        """Handle AI response failure from background thread."""
        self._thread = None
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        QMessageBox.warning(self, "错误", f"AI 回答失败:\n{error_msg}")

    def _build_prompt(self, question: str) -> str:
        """Build prompt based on current mode. Returns a prompt string
        that will be sent to self.client.chat() by _send_message."""
        if self.mode == "rag":
            from backend.rag_engine import RAGEngine
            from backend.config import RAG_PROMPT_TEMPLATE
            engine = RAGEngine()
            hits = engine.search(question)
            engine.close()
            if hits:
                context = "\n\n".join(
                    f"--- 来自《{h['source']}》---\n{h['text']}" for h in hits
                )
                return RAG_PROMPT_TEMPLATE.format(context=context, question=question)
            else:
                # No relevant docs found, fall back to direct
                return DIRECT_QA_TEMPLATE.format(question=question)
        elif self.mode == "context" and self.latest_clipboard:
            return CONTEXT_QA_TEMPLATE.format(
                context=self.latest_clipboard[:2000],
                question=question,
            )
        else:
            return DIRECT_QA_TEMPLATE.format(question=question)

    def close_client(self):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
