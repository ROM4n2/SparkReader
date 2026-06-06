# Spark GUI Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PySide6 desktop GUI for Spark with Q&A chat, conversation history (SQLite), settings panel, and system tray integration.

**Architecture:** PySide6 wraps the existing backend (OllamaClient, RAGEngine, clipboard_monitor) without modification. A QTabWidget holds 4 tabs; Phase 1 delivers 2 working tabs (Chat + Settings) plus the tray/theme skeleton. Conversation history persists in a local SQLite DB. Settings via QSettings.

**Tech Stack:** Python 3.11, PySide6, SQLite3 (stdlib), existing backend (OllamaClient, RAGEngine)

---

## File Structure

```
gui/
├── __init__.py                  # Empty package init
├── app.py                       # QApplication entry + system tray + hotkey
├── main_window.py               # QTabWidget + 4 tab placeholders
├── chat_tab.py                  # Conversation sidebar + message area + mode toggle
├── settings_tab.py              # ⚙️ Settings panel
├── conversation_db.py           # SQLite CRUD for chat history
├── resources/
│   ├── __init__.py
│   └── theme.qss               # Dark academic stylesheet
```

**Backend untouched.** All GUI code imports from `backend.*`.

---

## Prerequisites

### Task 0: Install PySide6

**Files:** `requirements.txt`

- [ ] **Step 1: Add PySide6 to requirements**

  Edit `requirements.txt`:
  ```
  httpx>=0.27.0
  pyperclip>=1.8.2
  chromadb>=1.5.0
  PySide6>=6.6.0
  ```

- [ ] **Step 2: Install**

  ```bash
  cd d:/Code/Spark/backend
  .venv/Scripts/pip install PySide6
  ```

  Expected: `Successfully installed PySide6-6.x.x`

---

## Implementation Tasks

### Task 1: Package scaffold + theme

**Files:**
- Create: `gui/__init__.py` (empty)
- Create: `gui/resources/__init__.py` (empty)
- Create: `gui/resources/theme.qss`

- [ ] **Step 1: Create directory structure**

  ```bash
  mkdir -p gui/resources
  touch gui/__init__.py gui/resources/__init__.py
  ```

- [ ] **Step 2: Write dark academic theme**

  `gui/resources/theme.qss`:
  ```css
  /* Spark Dark Academic Theme */
  /* Deep navy + amber accent */

  QMainWindow, QWidget {
      background-color: #0f0f1a;
      color: #f0e6d3;
  }

  QTabWidget::pane {
      border: none;
      background-color: #0f0f1a;
  }

  QTabBar::tab {
      background-color: #1a1a2e;
      color: #888888;
      padding: 12px 20px;
      border: none;
      border-right: 1px solid #2a2a3e;
      font-size: 14px;
  }

  QTabBar::tab:selected {
      background-color: #0f0f1a;
      color: #c4956a;
      border-left: 3px solid #c4956a;
  }

  QTabBar::tab:hover:!selected {
      background-color: #2a1f1a;
      color: #c4956a;
  }

  QListWidget {
      background-color: #1a1a2e;
      border: none;
      border-right: 1px solid #2a2a3e;
      outline: none;
  }

  QListWidget::item {
      padding: 8px 12px;
      border-bottom: 1px solid #2a2a3e;
  }

  QListWidget::item:selected {
      background-color: #2a1f1a;
      border-left: 3px solid #c4956a;
  }

  QTextBrowser {
      background-color: #0f0f1a;
      border: none;
      color: #f0e6d3;
      font-size: 14px;
  }

  QLineEdit {
      background-color: #1a1a2e;
      border: 1px solid #2a2a3e;
      border-radius: 6px;
      padding: 10px 14px;
      color: #f0e6d3;
      font-size: 14px;
  }

  QLineEdit:focus {
      border: 1px solid #c4956a;
  }

  QPushButton {
      background-color: #c4956a;
      color: #0f0f1a;
      border: none;
      border-radius: 6px;
      padding: 10px 20px;
      font-size: 14px;
      font-weight: 600;
  }

  QPushButton:hover {
      background-color: #d4a57a;
  }

  QPushButton:pressed {
      background-color: #a47a50;
  }

  QComboBox {
      background-color: #1a1a2e;
      border: 1px solid #2a2a3e;
      border-radius: 4px;
      padding: 6px 12px;
      color: #f0e6d3;
  }

  QComboBox:drop-down {
      border: none;
  }

  QComboBox QAbstractItemView {
      background-color: #1a1a2e;
      color: #f0e6d3;
      selection-background-color: #2a1f1a;
  }

  QCheckBox, QLabel {
      color: #f0e6d3;
  }

  QSpinBox, QDoubleSpinBox {
      background-color: #1a1a2e;
      border: 1px solid #2a2a3e;
      border-radius: 4px;
      padding: 4px 8px;
      color: #f0e6d3;
  }
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add gui/ requirements.txt
  git commit -m "chore: scaffold gui package with dark academic theme"
  ```

---

### Task 2: `conversation_db.py` — SQLite chat history

**Files:**
- Create: `gui/conversation_db.py`

This module has zero GUI dependency — pure SQLite. It can be tested independently.

- [ ] **Step 1: Write `conversation_db.py`**

  ```python
  """
  Conversation database — SQLite-backed chat history.
  Auto-creates DB at %APPDATA%/Spark/conversations.db on first use.
  """
  import os
  import sqlite3
  from datetime import datetime
  from pathlib import Path


  def _get_db_path() -> str:
      """Return the path to the conversations SQLite DB."""
      app_dir = Path(os.environ.get("APPDATA", Path.home() / ".local")) / "Spark"
      app_dir.mkdir(parents=True, exist_ok=True)
      return str(app_dir / "conversations.db")


  _conn: sqlite3.Connection | None = None


  def _get_connection() -> sqlite3.Connection:
      """Get or create the persistent DB connection."""
      global _conn
      if _conn is None:
          _conn = sqlite3.connect(_get_db_path())
          _conn.row_factory = sqlite3.Row
          _conn.execute("PRAGMA journal_mode=WAL")
          _init_schema(_conn)
      return _conn


  def _init_schema(conn: sqlite3.Connection):
      conn.executescript("""
          CREATE TABLE IF NOT EXISTS conversations (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              title       TEXT    NOT NULL DEFAULT '新对话',
              created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
              updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
          );
          CREATE TABLE IF NOT EXISTS messages (
              id               INTEGER PRIMARY KEY AUTOINCREMENT,
              conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
              role             TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
              content          TEXT    NOT NULL,
              mode             TEXT    NOT NULL DEFAULT 'direct',
              created_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
          );
          CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
      """)
      conn.commit()


  def create_conversation(title: str = "新对话") -> int:
      """Create a new conversation. Returns its ID."""
      conn = _get_connection()
      cur = conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
      conn.commit()
      return cur.lastrowid


  def delete_conversation(conv_id: int):
      """Delete a conversation and all its messages."""
      conn = _get_connection()
      conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
      conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
      conn.commit()


  def rename_conversation(conv_id: int, title: str):
      """Rename a conversation."""
      conn = _get_connection()
      conn.execute(
          "UPDATE conversations SET title = ?, updated_at = datetime('now','localtime') WHERE id = ?",
          (title, conv_id),
      )
      conn.commit()


  def list_conversations() -> list[dict]:
      """List all conversations, newest first."""
      conn = _get_connection()
      rows = conn.execute(
          "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
      ).fetchall()
      return [dict(r) for r in rows]


  def add_message(conv_id: int, role: str, content: str, mode: str = "direct") -> int:
      """Add a message to a conversation. Returns message ID."""
      conn = _get_connection()
      cur = conn.execute(
          "INSERT INTO messages (conversation_id, role, content, mode) VALUES (?, ?, ?, ?)",
          (conv_id, role, content, mode),
      )
      # Update parent conversation timestamp
      conn.execute(
          "UPDATE conversations SET updated_at = datetime('now','localtime') WHERE id = ?",
          (conv_id,),
      )
      conn.commit()
      return cur.lastrowid


  def get_messages(conv_id: int) -> list[dict]:
      """Get all messages for a conversation, oldest first."""
      conn = _get_connection()
      rows = conn.execute(
          "SELECT id, role, content, mode, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at",
          (conv_id,),
      ).fetchall()
      return [dict(r) for r in rows]


  def auto_title(conv_id: int):
      """Auto-generate a title from the first user message."""
      conn = _get_connection()
      row = conn.execute(
          "SELECT content FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY created_at LIMIT 1",
          (conv_id,),
      ).fetchone()
      if row:
          title = row["content"].strip()[:30]
          conn.execute(
              "UPDATE conversations SET title = ? WHERE id = ?",
              (title, conv_id),
          )
          conn.commit()


  def cleanup_old(max_count: int = 500):
      """Delete oldest conversations if count exceeds max."""
      conn = _get_connection()
      count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
      if count > max_count:
          conn.execute(
              "DELETE FROM conversations WHERE id IN (SELECT id FROM conversations ORDER BY updated_at ASC LIMIT ?)",
              (count - max_count,),
          )
          conn.commit()
  ```

- [ ] **Step 2: Quick smoke test**

  ```bash
  cd d:/Code/Spark
  PYTHONIOENCODING=utf-8 .venv/Scripts/python -c "
  import sys; sys.path.insert(0, 'gui')
  from gui.conversation_db import (
      create_conversation, add_message, get_messages,
      list_conversations, delete_conversation, auto_title
  )
  cid = create_conversation('测试对话')
  add_message(cid, 'user', '什么是辩证法？')
  add_message(cid, 'assistant', '辩证法是关于普遍联系和发展的哲学学说。')
  auto_title(cid)
  convs = list_conversations()
  msgs = get_messages(cid)
  print(f'Conversations: {len(convs)}')
  print(f'Messages: {len(msgs)}')
  print(f'Title: {convs[0][\"title\"]}')
  delete_conversation(cid)
  print('OK')
  "
  ```

  Expected: `Conversations: 1`, `Messages: 2`, title auto-set, `OK`

- [ ] **Step 3: Commit**

  ```bash
  git add gui/conversation_db.py
  git commit -m "feat: conversation history SQLite CRUD"
  ```

---

### Task 3: `main_window.py` — Tab framework

**Files:**
- Create: `gui/main_window.py`

- [ ] **Step 1: Write `main_window.py`**

  ```python
  """
  Main application window with tab navigation.
  """
  from PySide6.QtCore import Qt
  from PySide6.QtWidgets import (
      QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel,
  )


  class MainWindow(QMainWindow):
      """Spark main window with 4 tabs. Phase 1 delivers Chat + Settings."""

      def __init__(self):
          super().__init__()
          self.setWindowTitle("Spark - 马列经典 AI 阅读助手")
          self.setMinimumSize(900, 600)
          self.resize(1100, 720)

          self.tabs = QTabWidget()
          self.tabs.setTabPosition(QTabWidget.TabPosition.West)
          self.tabs.setTabShape(QTabWidget.TabShape.Rounded)
          self.setCentralWidget(self.tabs)

          # Phase 1 tabs
          self.chat_tab = self._make_placeholder("💬 问答", "聊天功能即将上线")
          self.settings_tab = self._make_placeholder("⚙️ 设置", "设置面板即将上线")

          self.tabs.addTab(self.chat_tab, "💬 问答")
          self.tabs.addTab(self._make_placeholder("📖 阅读", "阅读器将在 Phase 2 实现"), "📖 阅读")
          self.tabs.addTab(self._make_placeholder("📚 文档库", "文档管理将在 Phase 3 实现"), "📚 文档库")
          self.tabs.addTab(self.settings_tab, "⚙️ 设置")

      def _make_placeholder(self, title: str, message: str) -> QWidget:
          widget = QWidget()
          layout = QVBoxLayout(widget)
          label = QLabel(message)
          label.setAlignment(Qt.AlignmentFlag.AlignCenter)
          label.setStyleSheet("color: #888888; font-size: 16px;")
          layout.addWidget(label)
          return widget
  ```

- [ ] **Step 2: Quick visual test**

  ```bash
  cd d:/Code/Spark
  PYTHONIOENCODING=utf-8 .venv/Scripts/python -c "
  import sys; sys.path.insert(0, 'gui')
  from PySide6.QtWidgets import QApplication
  from main_window import MainWindow
  app = QApplication(sys.argv)
  with open('gui/resources/theme.qss') as f:
      app.setStyleSheet(f.read())
  w = MainWindow()
  w.show()
  print('Window should appear. Close it to continue.')
  app.exec()
  "
  ```

  Expected: Window appears with 4 tabs, dark theme applied, placeholder text. Close window to proceed.

- [ ] **Step 3: Commit**

  ```bash
  git add gui/main_window.py
  git commit -m "feat: main window with 4-tab framework"
  ```

---

### Task 4: `app.py` — System tray + entry point

**Files:**
- Create: `gui/app.py`

- [ ] **Step 1: Write `app.py`**

  ```python
  """
  Spark GUI entry point.
  Handles QApplication, system tray, and global hotkey.
  """
  import sys
  import os

  # Ensure backend is importable
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

  from pathlib import Path
  from PySide6.QtCore import Qt, QTimer
  from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
  from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox

  from gui.main_window import MainWindow


  def run():
      """Launch the Spark GUI application."""
      app = QApplication(sys.argv)
      app.setApplicationName("Spark")
      app.setOrganizationName("SparkReader")

      # Load theme
      theme_path = Path(__file__).parent / "resources" / "theme.qss"
      if theme_path.exists():
          with open(theme_path, encoding="utf-8") as f:
              app.setStyleSheet(f.read())

      # Check Ollama availability before showing window
      from backend.ollama_client import OllamaClient
      try:
          client = OllamaClient()
          # Quick health check via embed (lighter than chat)
          client.embed("ping")
          client.close()
      except Exception:
          reply = QMessageBox.question(
              None, "Ollama 未运行",
              "无法连接到 Ollama。请确保 Ollama 正在运行。\n\n是否继续启动？",
              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
          )
          if reply == QMessageBox.StandardButton.No:
              sys.exit(1)

      window = MainWindow()

      # System tray
      tray = QSystemTrayIcon(QIcon(), app)
      tray.setToolTip("Spark - 马列经典 AI 阅读助手")
      tray_menu = QMenu()
      show_action = tray_menu.addAction("显示窗口")
      show_action.triggered.connect(window.show)
      show_action.triggered.connect(window.raise_)
      quit_action = tray_menu.addAction("退出")
      quit_action.triggered.connect(app.quit)
      tray.setContextMenu(tray_menu)
      tray.show()

      # Global hotkey: Ctrl+Shift+S to toggle window
      hotkey = QShortcut(QKeySequence("Ctrl+Shift+S"), window)
      hotkey.activated.connect(lambda: _toggle_window(window))

      # Override close event to minimize to tray
      def close_event(event):
          event.ignore()
          window.hide()
          tray.showMessage("Spark", "已最小化到系统托盘", QSystemTrayIcon.MessageIcon.Information, 2000)

      window.closeEvent = close_event  # type: ignore

      window.show()
      sys.exit(app.exec())


  def _toggle_window(window):
      """Toggle main window visibility."""
      if window.isVisible():
          window.hide()
      else:
          window.show()
          window.raise_()
          window.activateWindow()


  if __name__ == "__main__":
      run()
  ```

- [ ] **Step 2: Test that it launches**

  ```bash
  cd d:/Code/Spark
  PYTHONIOENCODING=utf-8 .venv/Scripts/python -c "
  import sys; sys.path.insert(0, '.')
  from gui.app import run
  run()
  "
  ```

  Expected: Window appears with dark theme. Close → minimizes to tray. Tray right-click → Show/Exit. Ctrl+Shift+S toggles window.

  **Note:** System tray icon won't render without an actual .ico/.png file set. The window still works — tray just has a blank icon. We'll add an icon in a follow-up. For now verify: close → hides to tray, tray menu works, hotkey toggles.

- [ ] **Step 3: Commit**

  ```bash
  git add gui/app.py
  git commit -m "feat: system tray + global hotkey + app entry"
  ```

---

### Task 5: `settings_tab.py` — Settings panel

**Files:**
- Create: `gui/settings_tab.py`

- [ ] **Step 1: Write `settings_tab.py`**

  ```python
  """
  Settings tab — model selection, clipboard monitoring, hotkey config.
  Settings persisted via QSettings (Windows Registry / INI fallback).
  """
  import httpx
  from pathlib import Path
  from PySide6.QtCore import Qt, QSettings
  from PySide6.QtWidgets import (
      QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
      QLabel, QComboBox, QCheckBox, QSpinBox,
      QDoubleSpinBox, QKeySequenceEdit, QGroupBox,
  )

  from backend.config import OLLAMA_BASE_URL, EMBED_MODEL


  class SettingsTab(QWidget):
      """Settings panel. Reads/writes QSettings on change."""

      def __init__(self):
          super().__init__()
          self.settings = QSettings("SparkReader", "Spark")
          self._build_ui()
          self._load_settings()

      def _build_ui(self):
          layout = QVBoxLayout(self)
          layout.setSpacing(20)
          layout.setContentsMargins(32, 24, 32, 24)

          # ── Model group ──
          model_group = QGroupBox("模型设置")
          model_layout = QFormLayout(model_group)

          self.chat_model_combo = QComboBox()
          self.chat_model_combo.setMinimumWidth(200)
          self._populate_models()
          model_layout.addRow("聊天模型:", self.chat_model_combo)

          self.embed_model_combo = QComboBox()
          self.embed_model_combo.addItems([EMBED_MODEL, "nomic-embed-text", "all-minilm"])
          model_layout.addRow("嵌入模型:", self.embed_model_combo)

          layout.addWidget(model_group)

          # ── Clipboard group ──
          clip_group = QGroupBox("剪贴板监控")
          clip_layout = QFormLayout(clip_group)

          self.clip_enabled = QCheckBox("启用监控")
          clip_layout.addRow(self.clip_enabled)

          self.threshold_spin = QSpinBox()
          self.threshold_spin.setRange(0, 500)
          self.threshold_spin.setSuffix(" 字")
          self.threshold_spin.setToolTip("0 = 关闭自动解释")
          clip_layout.addRow("自动解释阈值:", self.threshold_spin)

          self.interval_spin = QDoubleSpinBox()
          self.interval_spin.setRange(0.5, 10.0)
          self.interval_spin.setSingleStep(0.5)
          self.interval_spin.setSuffix(" 秒")
          clip_layout.addRow("轮询间隔:", self.interval_spin)

          layout.addWidget(clip_group)

          # ── Hotkey group ──
          hotkey_group = QGroupBox("快捷键")
          hotkey_layout = QFormLayout(hotkey_group)

          self.hotkey_edit = QKeySequenceEdit()
          hotkey_layout.addRow("唤起窗口:", self.hotkey_edit)

          self.auto_start = QCheckBox("开机自动启动")
          self.auto_start.setChecked(False)  # Default off per user preference
          self.auto_start.toggled.connect(self._toggle_auto_start)
          hotkey_layout.addRow(self.auto_start)

          layout.addWidget(hotkey_group)

          # ── About group ──
          about_group = QGroupBox("关于")
          about_layout = QVBoxLayout(about_group)
          about_layout.addWidget(QLabel("Spark v0.2 · 马列经典 AI 阅读助手"))
          about_layout.addWidget(QLabel("后端: Ollama + ChromaDB | GUI: PySide6"))
          layout.addWidget(about_group)

          layout.addStretch()

          # Connect signals to auto-save
          self.chat_model_combo.currentTextChanged.connect(self._save_settings)
          self.embed_model_combo.currentTextChanged.connect(self._save_settings)
          self.clip_enabled.toggled.connect(self._save_settings)
          self.threshold_spin.valueChanged.connect(self._save_settings)
          self.interval_spin.valueChanged.connect(self._save_settings)
          self.hotkey_edit.keySequenceChanged.connect(self._save_settings)
          self.auto_start.toggled.connect(self._save_settings)

      def _populate_models(self):
          """Fetch available models from Ollama and populate combo."""
          current = self.chat_model_combo.currentText()
          try:
              resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
              models = [m["name"] for m in resp.json().get("models", [])]
              self.chat_model_combo.clear()
              self.chat_model_combo.addItems(models)
          except Exception:
              self.chat_model_combo.clear()
              self.chat_model_combo.addItem("(Ollama 未连接)")

          # Restore selection if previously set
          if current:
              idx = self.chat_model_combo.findText(current)
              if idx >= 0:
                  self.chat_model_combo.setCurrentIndex(idx)

      def _load_settings(self):
          """Load persisted settings into widgets."""
          self.chat_model_combo.setCurrentText(
              self.settings.value("chat_model", "qwen2.5:7b", type=str)
          )
          self.embed_model_combo.setCurrentText(
              self.settings.value("embed_model", EMBED_MODEL, type=str)
          )
          self.clip_enabled.setChecked(
              self.settings.value("clip_enabled", True, type=bool)
          )
          self.threshold_spin.setValue(
              self.settings.value("explain_threshold", 50, type=int)
          )
          self.interval_spin.setValue(
              self.settings.value("poll_interval", 2.0, type=float)
          )
          from PySide6.QtGui import QKeySequence
          seq = self.settings.value("hotkey", "Ctrl+Shift+S", type=str)
          self.hotkey_edit.setKeySequence(QKeySequence(seq))
          self.auto_start.setChecked(
              self.settings.value("auto_start", False, type=bool)
          )

      def _save_settings(self):
          """Persist current widget values."""
          self.settings.setValue("chat_model", self.chat_model_combo.currentText())
          self.settings.setValue("embed_model", self.embed_model_combo.currentText())
          self.settings.setValue("clip_enabled", self.clip_enabled.isChecked())
          self.settings.setValue("explain_threshold", self.threshold_spin.value())
          self.settings.setValue("poll_interval", self.interval_spin.value())
          self.settings.setValue("hotkey", self.hotkey_edit.keySequence().toString())
          self.settings.setValue("auto_start", self.auto_start.isChecked())

      def get_chat_model(self) -> str:
          return self.chat_model_combo.currentText()

      def get_clipboard_enabled(self) -> bool:
          return self.clip_enabled.isChecked()

      def _toggle_auto_start(self, enabled: bool):
          """Register or unregister Windows auto-start via registry."""
          try:
              import winreg
              key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
              key = winreg.OpenKey(
                  winreg.HKEY_CURRENT_USER, key_path,
                  0, winreg.KEY_SET_VALUE,
              )
              if enabled:
                  import sys
                  exe = sys.executable
                  script = Path(__file__).parent.parent / "gui" / "app.py"
                  winreg.SetValueEx(key, "Spark", 0, winreg.REG_SZ, f'"{exe}" "{script}"')
              else:
                  try:
                      winreg.DeleteValue(key, "Spark")
                  except FileNotFoundError:
                      pass
              winreg.CloseKey(key)
          except Exception:
              pass  # Non-Windows or permission error — silently ignore

      def get_explain_threshold(self) -> int:
          return self.threshold_spin.value()
  ```

- [ ] **Step 2: Wire settings_tab into main_window.py**

  Modify `gui/main_window.py`:

  ```python
  from gui.settings_tab import SettingsTab   # add to imports

  # In __init__, replace:
  # self.settings_tab = self._make_placeholder(...)
  # with:
  self.settings_tab = SettingsTab()

  # Add to class:
  def get_settings(self) -> SettingsTab:
      return self.settings_tab
  ```

- [ ] **Step 3: Test**

  ```bash
  cd d:/Code/Spark
  PYTHONIOENCODING=utf-8 .venv/Scripts/python -c "
  import sys; sys.path.insert(0, '.')
  from PySide6.QtWidgets import QApplication
  from gui.main_window import MainWindow
  app = QApplication(sys.argv)
  with open('gui/resources/theme.qss') as f:
      app.setStyleSheet(f.read())
  w = MainWindow()
  w.tabs.setCurrentIndex(3)  # Switch to Settings tab
  w.show()
  print('Settings tab should show. Modify a value, close, reopen to verify persistence.')
  app.exec()
  "
  ```

  Expected: Settings tab shows model combo (populated from Ollama), clipboard checkboxes, hotkey editor. Change a value → close → reopen → value persists.

- [ ] **Step 4: Commit**

  ```bash
  git add gui/settings_tab.py gui/main_window.py
  git commit -m "feat: settings tab with QSettings persistence"
  ```

---

### Task 6: `chat_tab.py` — Conversation sidebar + messages

**Files:**
- Create: `gui/chat_tab.py`

This is the largest component. It connects to `conversation_db.py` and `backend` for AI responses.

- [ ] **Step 1: Write `chat_tab.py`**

  ```python
  """
  Chat tab — conversation sidebar, message display, mode selector, input bar.
  Three modes: RAG / Clipboard Context / Direct Q&A.
  """
  import sys
  import os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

  from datetime import datetime
  from PySide6.QtCore import Qt, QTimer
  from PySide6.QtWidgets import (
      QWidget, QVBoxLayout, QHBoxLayout,
      QListWidget, QListWidgetItem, QTextBrowser,
      QLineEdit, QPushButton, QSplitter, QLabel,
      QFrame, QMenu, QMessageBox, QSizePolicy,
  )

  from gui import conversation_db as db
  from backend.ollama_client import OllamaClient
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
          self.client = OllamaClient()
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

          # Ensure we have a conversation
          if self.current_conv_id is None:
              self.current_conv_id = db.create_conversation()
              self._load_conversation_list()

          # Show user message immediately
          db.add_message(self.current_conv_id, "user", text, self.mode)
          self._load_messages()
          self.input_edit.clear()

          # Get AI response
          try:
              prompt = self._build_prompt(text)
              response = self.client.chat(prompt)
              db.add_message(self.current_conv_id, "assistant", response, self.mode)
              db.auto_title(self.current_conv_id)
              self._load_conversation_list()
              self._load_messages()
          except Exception as e:
              QMessageBox.warning(self, "错误", f"AI 回答失败:\n{e}")

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
          self.client.close()
  ```

- [ ] **Step 2: Wire chat_tab into main_window.py**

  Modify `gui/main_window.py`:

  ```python
  from gui.chat_tab import ChatTab   # add to imports

  # In __init__, replace:
  # self.chat_tab = self._make_placeholder(...)
  # with:
  self.chat_tab = ChatTab(settings_getter=self.get_settings)
  # And replace the addTab call:
  # self.tabs.addTab(self.chat_tab, "💬 问答")
  # (keep the other tabs as placeholders)

  # Add to class:
  def closeEvent(self, event):
      self.chat_tab.close_client()
      super().closeEvent(event)
  ```

- [ ] **Step 3: Open the app and send a message**

  ```bash
  cd d:/Code/Spark
  PYTHONIOENCODING=utf-8 .venv/Scripts/python -c "
  import sys; sys.path.insert(0, '.')
  from gui.app import run
  run()
  "
  ```

  Expected: Window with Chat tab active. Left sidebar shows "新对话". Type a question → AI responds (mode depends on vector DB state). New conversation creates another entry. Right-click → rename/delete. Restart app → history persists.

- [ ] **Step 4: Commit**

  ```bash
  git add gui/chat_tab.py gui/main_window.py
  git commit -m "feat: chat tab with conversation management and mode selector"
  ```

---

### Task 7: Wire clipboard monitor into GUI

**Files:**
- Modify: `gui/app.py`

The existing `ClipboardMonitor` runs in a background thread. In GUI mode, we want it to:
1. Run silently in the background
2. Update `ChatTab.latest_clipboard` with detected text
3. Not print to console (no print() calls since there's no terminal)

- [ ] **Step 1: Run clipboard monitor in background thread**

  Add to `gui/app.py`:

  ```python
  import threading
  from backend.clipboard_monitor import ClipboardMonitor
  from gui.chat_tab import ChatTab

  class SilentClipboardMonitor(ClipboardMonitor):
      """ClipboardMonitor variant that updates ChatTab instead of printing."""
      def _check_once(self):
          try:
              import pyperclip
              current = pyperclip.paste()
          except Exception:
              return
          if not current or not current.strip():
              return
          if current == self.last_text:
              return
          self.last_text = current
          ChatTab.latest_clipboard = current

  # In run(), after window = MainWindow():
  clipboard_thread = threading.Thread(
      target=SilentClipboardMonitor().start, daemon=True
  )
  clipboard_thread.start()
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add gui/app.py
  git commit -m "feat: background clipboard monitor in GUI mode"
  ```

---

### Task 8: Final integration — `start_spark.bat` update + full test

**Files:**
- Modify: `start_spark.bat`

- [ ] **Step 1: Add `--gui` flag to `start_spark.bat`**

  At the bottom of `start_spark.bat`, replace the `python main.py %*` call:

  ```bat
  if /I "%1"=="--gui" (
      shift
      python gui\app.py %*
  ) else (
      python main.py %*
  )
  ```

- [ ] **Step 2: Full end-to-end test**

  ```bash
  # Option A: via batch file
  start_spark.bat --gui

  # Option B: direct
  cd d:/Code/Spark
  PYTHONIOENCODING=utf-8 .venv/Scripts/python gui/app.py
  ```

  **Test checklist:**
  1. ✅ Window appears with dark theme, 4 tabs, Settings and Chat functional
  2. ✅ Type question in Chat → AI answers in correct mode
  3. ✅ Multiple conversations: create, switch, rename, delete
  4. ✅ Close window → minimizes to tray (check system tray)
  5. ✅ Ctrl+Shift+S → toggles window visibility
  6. ✅ Tray right-click → Show / Exit works
  7. ✅ Close and reopen → conversation history persists
  8. ✅ Settings: change values → persist across restart
  9. ✅ Ollama offline → shows warning dialog on startup

- [ ] **Step 3: Commit**

  ```bash
  git add start_spark.bat
  git commit -m "feat: add --gui flag to launcher"
  ```
