# Spark GUI Desktop Application — Design Spec

## Overview

Spark is a local AI reading assistant for Marxist-Leninist-Maoist classics. It currently runs as a CLI tool with two modes (clipboard monitor + interactive Q&A) and a RAG engine (ChromaDB vector search). This spec covers adding a **PySide6 GUI desktop application** that wraps the existing backend.

**Target user:** Beginner Python developer, Windows 11, 32GB RAM, RTX 5060 Laptop.
**Tech stack:** PySide6 (Qt for Python) + existing Python backend (Ollama, ChromaDB, httpx).

---

## Architecture

```
gui/app.py                QApplication entry + system tray
gui/main_window.py        QTabWidget: 阅读/问答/文档库/设置
gui/chat_tab.py           💬 Tab: conversation sidebar + message area + mode selector
gui/reader_tab.py         📖 Tab: built-in text reader + smart concept detection (Phase 2)
gui/library_tab.py        📚 Tab: document management with drag-drop (Phase 3)
gui/settings_tab.py       ⚙️ Tab: settings panel
gui/conversation_db.py    SQLite storage for chat history
gui/resources/            Icons, QSS stylesheets
gui/models.py             Data models / constants shared across tabs

backend/                  Existing — no changes needed
```

**Backend imports unchanged.** GUI code directly imports from `backend.rag_engine`, `backend.ollama_client`, `backend.config`.

---

## Development Phasing

### Phase 1 (this round)

- `gui/app.py` + `main_window.py` — system tray, global hotkey, tab framework
- `gui/chat_tab.py` — full interactive Q&A with:
  - Three toggleable modes: Direct Q&A / Clipboard Context / RAG
  - Left sidebar: conversation history (create/switch/delete, date grouping, auto-naming)
  - SQLite persistence via `conversation_db.py`
- `gui/settings_tab.py` — model selection, clipboard monitoring toggle + threshold, hotkey config
- `gui/resources/` — dark academic theme (deep navy + amber accent)

### Phase 2 (next round)
- `gui/reader_tab.py` — built-in text viewer with cursor-position smart detection
- Selection-based explanation popup

### Phase 3 (next round)
- `gui/library_tab.py` — document management, drag-drop import, batch re-embedding

---

## Phase 1 Detailed Design

### System Tray (`app.py`)

- Close button → minimize to tray (not exit)
- Tray icon with right-click menu: "Show Window" / "Exit"
- Global hotkey: `Ctrl+Shift+S` to toggle window visibility
- First launch opens maximized; subsequent launches restores last geometry

### Main Window (`main_window.py`)

- `QTabWidget` with four tabs, left-aligned vertical tab bar
- Tab icons: 📖 💬 📚 ⚙️ (unicode or SVG)
- Window title: "Spark - 马列经典 AI 阅读助手"
- Minimum size: 900×600
- Remember geometry between sessions (QSettings)

### Settings Tab (`settings_tab.py`)

| Setting | Widget | Default |
|---------|--------|---------|
| Chat model | QComboBox (populated from Ollama `/api/tags`) | qwen2.5:7b |
| Embed model | QComboBox | nomic-embed-text |
| Clipboard monitoring | QCheckBox | On |
| Auto-explain threshold | QSpinBox (0-500) | 50 |
| Poll interval | QDoubleSpinBox (0.5-10) | 2.0 |
| Global hotkey | QKeySequenceEdit | Ctrl+Shift+S |
| Auto-start on boot | QCheckBox | **Off** (user must opt in) |

Settings stored to `QSettings` (Windows registry fallback) + `config.py` overrides.

### Chat Tab (`chat_tab.py`)

**Layout:** Horizontal splitter
- Left: conversation list (QListWidget, ~220px)
- Right: message area (QTextBrowser) + input bar (QLineEdit + QPushButton)

**Conversation sidebar:**
- Top bar: title "历史" + "＋" new conversation button
- Items grouped by date: "今天", "昨天", "本周", "更早"
- Each item: auto-generated title (from first message), timestamp
- Right-click: rename, delete
- Current session highlighted

**Message area:**
- QTextBrowser with rich text (Markdown rendering)
- Messages displayed as styled bubbles (QSS)
- AI messages: amber accent left border
- User messages: right-aligned
- Scroll-to-bottom on new message

**Mode selector:**
- Three toggle buttons above the input bar: "📚 RAG 问答" / "📋 上下文" / "💬 直接"
- Default: RAG (if vector DB has content) → Direct (fallback)
- Active mode highlighted in amber; inactive in dark gray
- Mode label shown per-message in conversation DB for filtering

**Input bar:**
- QLineEdit with placeholder "输入问题..."
- Send button (Enter key also sends)
- Commands: `/clear` (clear screen), `/exit` (minimize to tray)

**Conversation DB (`conversation_db.py`):**
- SQLite stored at `%APPDATA%/Spark/conversations.db`
- Tables:
  ```sql
  conversations(id, title, created_at, updated_at)
  messages(id, conversation_id, role, content, mode, created_at)
  ```
- Auto-create DB on first launch
- Max 500 conversations auto-cleanup (oldest first)

---

## Theme (Dark Academic)

```css
/* Color palette */
--bg-deep:      #0f0f1a;   /* main background */
--bg-surface:   #1a1a2e;   /* card/sidebar background */
--bg-hover:     #2a1f1a;   /* hover/active state */
--accent:       #c4956a;   /* amber accent */
--accent-dim:   #8b6f4f;   /* dimmed accent */
--text-primary: #f0e6d3;   /* main text */
--text-dim:     #888888;   /* secondary text */
--text-muted:   #555555;   /* disabled text */
```

QSS stylesheet in `gui/resources/theme.qss`.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Ollama not running | Status bar shows ❌, RAG/Direct modes show error toast |
| Model not found | Settings QComboBox empty, user prompted to `ollama pull` |
| Vector DB empty | Chat tab shows notice: "请先导入文档 (python ingest.py)" |
| Clipboard inaccessible | Monitoring silently skips cycle, status bar shows ⚠️ |
| ChromaDB uninstalled | RAG mode hidden, chat falls back to Direct |
| Conversation DB corrupt | Backup file restored, or fresh DB created |

---

## Files to Create

```
gui/__init__.py
gui/app.py                    # QApplication + tray + hotkey
gui/main_window.py            # QTabWidget + 4 tabs
gui/chat_tab.py               # Conversation sidebar + message area + mode toggle
gui/settings_tab.py           # Settings panel
gui/conversation_db.py        # SQLite CRUD
gui/resources/__init__.py
gui/resources/theme.qss       # Dark academic stylesheet
gui/resources/icons/           # SVG tray icon, tab icons
```

---

## Files to Modify

- `requirements.txt` — add `PySide6>=6.6`
- `.gitignore` — add `gui/__pycache__/`
- `start_spark.bat` — update to support `--gui` flag

---

## Verification

1. `python gui/app.py` → window appears with 4 tabs
2. 💬 Tab: Type question → AI answers (RAG mode if docs ingested)
3. 💬 Tab: Switch modes (RAG/Context/Direct) → behavior matches
4. Conversation sidebar: Create/switch/delete sessions → persists across restarts
5. Settings: Change model → applies without restart
6. Close window → minimizes to tray, not exits
7. Ctrl+Shift+S → window toggles visibility
8. Tray right-click → Show/Exit works
