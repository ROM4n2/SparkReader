# Knowledge Graph & Reading Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add passive concept knowledge graph auto-building, on-demand structured summaries, text highlighting, and bookmarks to the Spark desktop reader.

**Architecture:** A new `knowledge.db` SQLite database stores concepts, relations, highlights, bookmarks, and summaries. A `ConceptExtractor` engine uses RAG retrieval + LLM to extract related concepts and auto-populate the graph. The reader's right panel gains a searchable knowledge graph tree view that shares space with the existing explanation panel. Highlights and bookmarks persist per-file with concept linkage. Summary generation runs on-demand for selected text or auto-detected chapters.

**Tech Stack:** Python 3.11, PySide6, SQLite, existing Ollama + ChromaDB backends.

---

## Design Decisions (from grilling session)

| Decision | Choice |
|----------|--------|
| Knowledge graph engine | On-demand caching with SQLite (option 3) |
| Analysis granularity | One concept at a time |
| GUI presentation | Tree widget + detail panel, embedded in reader right panel |
| User interaction | Passive auto-build: click paragraph → explain (existing) → extract concepts (new, serial) |
| Concept extraction prompt | Structural only — no stance injection (saves tokens) |
| Structured summary | On-demand by selection or auto-detected chapter (option C) |
| Summary entry points | Toolbar button "总结本章" + right-click menu "总结选中内容" |
| Highlights | Text files only (QPlainTextEdit), stored in SQLite, associated to concepts |
| Bookmarks | All file types, stored in SQLite |
| Implementation order | knowledge_db → concept_extractor + config → knowledge_graph GUI → reader_tab integration → highlights/bookmarks → summary → chat_tab |

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `backend/knowledge_db.py` | **Create** | SQLite schema + CRUD for concepts, relations, highlights, bookmarks, summaries |
| `backend/concept_extractor.py` | **Create** | LLM-powered concept extraction using RAG retrieval + Ollama |
| `gui/knowledge_graph.py` | **Create** | QWidget: search box + QTreeWidget + detail QTextBrowser, embeddable in reader right panel |
| `gui/summary_worker.py` | **Create** | QThread worker for on-demand chapter/selection summarization |
| `backend/config.py` | **Modify** | Add KNOWLEDGE_EXTRACT_PROMPT, CHAPTER_SUMMARY_PROMPT, SELECTION_SUMMARY_PROMPT |
| `gui/reader_tab.py` | **Modify** | Right panel search box + view switching, serial analysis chain (explain → extract), right-click menu, toolbar "总结本章" button, highlight/bookmark logic |
| `gui/chat_tab.py` | **Modify** | Detect concept names in AI responses, make them clickable to open knowledge graph |
| `gui/resources/theme.qss` | **Modify** | Add styles for knowledge graph tree, highlight/bookmark indicators, summary panel |

**No changes to:** `gui/app.py`, `gui/main_window.py`, `gui/settings_tab.py`, `gui/library_tab.py`, `gui/toc_panel.py`, `gui/pdf_renderer.py`, `gui/conversation_db.py`, `gui/file_parser.py`, `gui/ai_worker.py`, `backend/rag_engine.py`, `backend/clipboard_monitor.py`, `backend/ollama_client.py`, `backend/main.py`, `backend/ingest.py`

---

### Task 1: Knowledge Database (`backend/knowledge_db.py`)

**Files:**
- Create: `backend/knowledge_db.py`

- [ ] **Step 1: Create `backend/knowledge_db.py` with schema and CRUD**

```python
"""
Knowledge database — SQLite-backed concept graph, highlights, bookmarks, summaries.
Auto-creates DB at %APPDATA%/Spark/knowledge.db on first use.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def _get_db_path() -> str:
    app_dir = Path(os.environ.get("APPDATA", Path.home() / ".local")) / "Spark"
    app_dir.mkdir(parents=True, exist_ok=True)
    return str(app_dir / "knowledge.db")


_conn: sqlite3.Connection | None = None


def _get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_get_db_path())
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS concepts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS relations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id     INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            target_id     INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            relation_type TEXT    NOT NULL CHECK(relation_type IN ('包含','对立','发展','背景','引用')),
            explanation   TEXT    NOT NULL DEFAULT '',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(source_id, target_id, relation_type)
        );

        CREATE TABLE IF NOT EXISTS highlights (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT    NOT NULL,
            start_pos   INTEGER NOT NULL,
            end_pos     INTEGER NOT NULL,
            color       TEXT    NOT NULL DEFAULT '#c0392b',
            concept_name TEXT   DEFAULT NULL,
            note        TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_highlights_file ON highlights(file_path);

        CREATE TABLE IF NOT EXISTS bookmarks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT    NOT NULL,
            page_number INTEGER DEFAULT NULL,
            line_number INTEGER DEFAULT NULL,
            label       TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_bookmarks_file ON bookmarks(file_path);

        CREATE TABLE IF NOT EXISTS summaries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT    NOT NULL,
            scope       TEXT    NOT NULL CHECK(scope IN ('chapter','selection')),
            scope_ref   TEXT    NOT NULL DEFAULT '',
            content     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_summaries_file ON summaries(file_path);
    """)
    conn.commit()


# ── Concepts ──

def upsert_concept(name: str, description: str = "") -> int:
    """Insert or update a concept. Returns its ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO concepts (name, description) VALUES (?, ?)"
        " ON CONFLICT(name) DO UPDATE SET description = CASE WHEN ? != '' THEN ? ELSE description END",
        (name, description, description, description),
    )
    conn.commit()
    # get the id (need to select since upsert may not return rowid on conflict)
    row = conn.execute("SELECT id FROM concepts WHERE name = ?", (name,)).fetchone()
    return row["id"]


def get_concept(name: str) -> dict | None:
    """Get a concept by name, or None."""
    conn = _get_connection()
    row = conn.execute("SELECT * FROM concepts WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def list_concepts() -> list[dict]:
    """List all concepts, newest first."""
    conn = _get_connection()
    rows = conn.execute("SELECT * FROM concepts ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_concept(name: str):
    """Delete a concept and its relations."""
    conn = _get_connection()
    conn.execute("DELETE FROM concepts WHERE name = ?", (name,))
    conn.commit()


# ── Relations ──

def add_relation(source_name: str, target_name: str, relation_type: str, explanation: str = ""):
    """Add a directed relation between two concepts. Creates target concept if it doesn't exist."""
    source_id = upsert_concept(source_name)
    target_id = upsert_concept(target_name)
    conn = _get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, explanation) VALUES (?, ?, ?, ?)",
        (source_id, target_id, relation_type, explanation),
    )
    conn.commit()


def get_relations(source_name: str, max_depth: int = 1) -> list[dict]:
    """
    Get all relations for a concept (as source). Returns list of dicts with
    target_name, relation_type, explanation.
    For max_depth > 1, also returns second-level relations.
    """
    conn = _get_connection()
    concept = get_concept(source_name)
    if not concept:
        return []

    def _direct_relations(cid):
        return conn.execute(
            """SELECT c.name AS target_name, r.relation_type, r.explanation
               FROM relations r JOIN concepts c ON r.target_id = c.id
               WHERE r.source_id = ?""",
            (cid,),
        ).fetchall()

    results = [dict(r) for r in _direct_relations(concept["id"])]

    if max_depth > 1:
        for r in results:
            sub = get_concept(r["target_name"])
            if sub:
                second = _direct_relations(sub["id"])
                for s in second:
                    sd = dict(s)
                    sd["_depth"] = 2
                    sd["_parent"] = r["target_name"]
                    results.append(sd)
    return results


def concept_has_relations(name: str) -> bool:
    """Check if a concept already has extracted relations (cache hit)."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM relations r JOIN concepts c ON r.source_id = c.id WHERE c.name = ?",
        (name,),
    ).fetchone()
    return row["cnt"] > 0


# ── Highlights ──

def add_highlight(file_path: str, start_pos: int, end_pos: int,
                  color: str = "#c0392b", concept_name: str = None, note: str = "") -> int:
    """Add a text highlight. Returns its ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO highlights (file_path, start_pos, end_pos, color, concept_name, note) VALUES (?, ?, ?, ?, ?, ?)",
        (file_path, start_pos, end_pos, color, concept_name, note),
    )
    conn.commit()
    return cur.lastrowid


def get_highlights(file_path: str) -> list[dict]:
    """Get all highlights for a file, ordered by position."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM highlights WHERE file_path = ? ORDER BY start_pos",
        (file_path,),
    ).fetchall()
    return [dict(r) for r in rows]


def remove_highlight(highlight_id: int):
    """Remove a highlight by ID."""
    conn = _get_connection()
    conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
    conn.commit()


def update_highlight_concept(highlight_id: int, concept_name: str):
    """Link a highlight to a concept."""
    conn = _get_connection()
    conn.execute("UPDATE highlights SET concept_name = ? WHERE id = ?", (concept_name, highlight_id))
    conn.commit()


# ── Bookmarks ──

def add_bookmark(file_path: str, page_number: int = None, line_number: int = None, label: str = "") -> int:
    """Add a bookmark. Returns its ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO bookmarks (file_path, page_number, line_number, label) VALUES (?, ?, ?, ?)",
        (file_path, page_number, line_number, label),
    )
    conn.commit()
    return cur.lastrowid


def get_bookmarks(file_path: str) -> list[dict]:
    """Get all bookmarks for a file."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM bookmarks WHERE file_path = ? ORDER BY COALESCE(page_number, line_number)",
        (file_path,),
    ).fetchall()
    return [dict(r) for r in rows]


def remove_bookmark(bookmark_id: int):
    """Remove a bookmark by ID."""
    conn = _get_connection()
    conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
    conn.commit()


# ── Summaries ──

def save_summary(file_path: str, scope: str, scope_ref: str, content: str) -> int:
    """Save a summary. scope is 'chapter' or 'selection'. Returns ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO summaries (file_path, scope, scope_ref, content) VALUES (?, ?, ?, ?)",
        (file_path, scope, scope_ref, content),
    )
    conn.commit()
    return cur.lastrowid


def get_summaries(file_path: str) -> list[dict]:
    """Get all summaries for a file, newest first."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM summaries WHERE file_path = ? ORDER BY created_at DESC",
        (file_path,),
    ).fetchall()
    return [dict(r) for r in rows]


def close():
    """Close the database connection."""
    global _conn
    if _conn:
        _conn.close()
        _conn = None
```

- [ ] **Step 2: Test the module loads correctly**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "from backend.knowledge_db import _init_schema, upsert_concept, add_relation, get_relations; print('knowledge_db OK')"
Expected: knowledge_db OK
```

- [ ] **Step 3: Commit**

```bash
git add backend/knowledge_db.py
git commit -m "feat: add knowledge.db SQLite schema and CRUD for concepts, relations, highlights, bookmarks, summaries"
```

---

### Task 2: Config Update (`backend/config.py`)

**Files:**
- Modify: `backend/config.py` (append new prompt templates)

- [ ] **Step 1: Append knowledge graph and summary prompt templates to `backend/config.py`**

Add after line 64 (after `RAG_PROMPT_TEMPLATE`):

```python
# --- Knowledge graph ---
KNOWLEDGE_EXTRACT_PROMPT = (
    "从以下文本中，找出与【{concept_name}】直接相关的其他概念。\n\n"
    "参考文本：\n{context}\n\n"
    "请输出 JSON 数组，每个元素包含：\n"
    '- "concept": 关联概念名称\n'
    '- "relation": 关系类型，必须是以下之一: "包含" "对立" "发展" "背景" "引用"\n'
    '- "explanation": 1-2句说明两者关系\n\n'
    "要求：\n"
    "- 每个关联概念必须有明确的理论依据（在参考文本中能找到）\n"
    "- 输出 3-8 个关联概念\n"
    "- 不虚构不存在的概念\n"
    "- 只返回 JSON 数组，不包含其他文字\n"
    "示例输出：\n"
    '[{"concept":"对立统一","relation":"包含","explanation":"矛盾是对立统一关系的核心体现"}]'
)

# --- Structured summaries ---
CHAPTER_SUMMARY_PROMPT = (
    "你是一个马列毛主义经典著作阅读助手。请对以下章节内容生成分层总结。\n\n"
    "章节文本：\n{text}\n\n"
    "请按三层结构输出：\n"
    "1. **核心论点**：本章最主要的1-2个论点\n"
    "2. **论证结构**：论点→论据→结论的逻辑框架\n"
    "3. **关联知识点**：本章涉及的核心概念及其关联\n\n"
    "要求：\n"
    "- 每层用 ### 标题分隔\n"
    "- 总长度控制在 500 字以内\n"
    "- 引用原文时用「」标注"
)

SELECTION_SUMMARY_PROMPT = (
    "你是一个马列毛主义经典著作阅读助手。请对以下选中文本生成分层总结。\n\n"
    "选中文本：\n{text}\n\n"
    "请按三层结构输出：\n"
    "1. **核心论点**：这段文本最主要的论点\n"
    "2. **论证结构**：论点→论据→结论的逻辑框架\n"
    "3. **关联知识点**：涉及的核心概念及其关联\n\n"
    "要求：\n"
    "- 每层用 ### 标题分隔\n"
    "- 总长度控制在 300 字以内\n"
    "- 引用原文时用「」标注"
)
```

- [ ] **Step 2: Verify import**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'D:\\Code\\Spark'); from backend.config import KNOWLEDGE_EXTRACT_PROMPT, CHAPTER_SUMMARY_PROMPT, SELECTION_SUMMARY_PROMPT; print('config OK')"
Expected: config OK
```

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "feat: add knowledge extract and summary prompt templates to config"
```

---

### Task 3: Concept Extractor (`backend/concept_extractor.py`)

**Files:**
- Create: `backend/concept_extractor.py`

- [ ] **Step 1: Create `backend/concept_extractor.py`**

```python
"""
Concept extractor — uses RAG retrieval + LLM to extract related concepts.
Populates knowledge.db with concepts and relations.
"""
import json
import re

from backend.config import KNOWLEDGE_EXTRACT_PROMPT, RAG_TOP_K
from backend.ollama_client import OllamaClient
from backend.rag_engine import RAGEngine
from backend import knowledge_db


def _clean_json(text: str) -> str:
    """Extract JSON array from LLM output that may contain markdown fences."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop the first line (```json or ```) and last line (```)
        text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    return text


def extract_concepts(concept_name: str, client: OllamaClient = None) -> list[dict]:
    """
    Extract related concepts for a given concept name.
    Returns list of {concept, relation, explanation} dicts.
    Uses RAG retrieval to get context, then LLM to extract relations.
    Results are auto-saved to knowledge.db.
    """
    should_close = False
    if client is None:
        client = OllamaClient()
        should_close = True

    try:
        # 1. Check cache
        if knowledge_db.concept_has_relations(concept_name):
            return knowledge_db.get_relations(concept_name)

        # 2. RAG retrieval
        engine = RAGEngine()
        chunks = engine.search(concept_name, top_k=RAG_TOP_K)
        context = "\n\n".join(c["content"] for c in chunks)
        engine.close()

        if not context.strip():
            # No relevant docs — save concept stub only
            knowledge_db.upsert_concept(concept_name)
            return []

        # 3. LLM extraction
        prompt = KNOWLEDGE_EXTRACT_PROMPT.format(
            concept_name=concept_name,
            context=context[:3000],
        )
        raw = client.chat(prompt, system_prompt="")  # No stance — structural task
        cleaned = _clean_json(raw)

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: try to find JSON array with regex
            match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if match:
                items = json.loads(match.group())
            else:
                items = []

        # 4. Save to DB
        knowledge_db.upsert_concept(concept_name)
        for item in items:
            knowledge_db.add_relation(
                source_name=concept_name,
                target_name=item["concept"],
                relation_type=item["relation"],
                explanation=item.get("explanation", ""),
            )

        return items

    finally:
        if should_close:
            client.close()


def extract_concepts_for_text(text: str, client: OllamaClient = None) -> str | None:
    """
    Given a paragraph of text, detect the primary concept name.
    Used as the first step in the passive analysis chain: click paragraph →
    detect concept → extract relations.
    Returns the concept name, or None if no clear concept found.
    """
    should_close = False
    if client is None:
        client = OllamaClient()
        should_close = True

    try:
        prompt = (
            "从以下文本中提取最核心的一个概念（只用1-5个字回答，只返回概念名）：\n\n{text}"
        ).format(text=text[:500])
        name = client.chat(prompt, system_prompt="").strip()
        # Clean common LLM verbosity
        name = name.strip("。，. ,\"'「」《》").split("\n")[0]
        if not name or len(name) > 20:
            return None
        return name
    finally:
        if should_close:
            client.close()
```

- [ ] **Step 2: Verify the module loads**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'D:\\Code\\Spark'); from backend.concept_extractor import extract_concepts, extract_concepts_for_text; print('concept_extractor OK')"
Expected: concept_extractor OK
```

- [ ] **Step 3: Commit**

```bash
git add backend/concept_extractor.py
git commit -m "feat: add concept extractor — RAG retrieval + LLM for knowledge graph population"
```

---

### Task 4: Knowledge Graph Panel (`gui/knowledge_graph.py`)

**Files:**
- Create: `gui/knowledge_graph.py`

- [ ] **Step 1: Create `gui/knowledge_graph.py`**

```python
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


class KnowledgeGraphPanel(QWidget):
    """Searchable concept relationship tree + detail view."""

    concept_selected = Signal(str)  # emitted when user clicks a concept node

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
            " border-bottom: 1px solid #2a2a3e;"
        )
        layout.addWidget(header)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(8, 8, 8, 4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索概念...")
        self.search_input.setStyleSheet(
            "QLineEdit { padding: 6px 10px; font-size: 13px;"
            " background: #1e1e2a; border: 1px solid rgba(42,42,56,0.6);"
            " border-radius: 4px; color: #e0e0e6; }"
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
            "QTextBrowser { background: #181825; border-top: 1px solid #2a2a3e;"
            " padding: 8px; font-size: 12px; color: #aaa; }"
        )
        self.detail.setPlaceholderText("点击关联概念查看详情")
        layout.addWidget(self.detail)

        # Empty state
        self._show_empty()

    def _show_empty(self):
        self.tree.clear()
        empty = QTreeWidgetItem(self.tree)
        empty.setText(0, "输入概念名搜索关联")
        empty.setFlags(Qt.ItemFlag.NoItemFlags)
        self.detail.clear()

    def search(self, concept_name: str):
        """Search and display relations for a concept."""
        concept_name = concept_name.strip()
        if not concept_name:
            self._show_empty()
            return

        self.search_input.setText(concept_name)
        self._display_concept(concept_name)

    def _on_search(self):
        concept_name = self.search_input.text().strip()
        if not concept_name:
            return
        # Emit so reader_tab can trigger background extraction
        self.concept_selected.emit(concept_name)

    def display_concept(self, concept_name: str):
        """Display cached or fresh relations for a concept."""
        self.search_input.setText(concept_name)
        self._display_concept(concept_name)

    def _display_concept(self, concept_name: str):
        self.tree.clear()

        # Get concept info
        concept = knowledge_db.get_concept(concept_name)
        relations = knowledge_db.get_relations(concept_name, max_depth=2)

        if not relations:
            empty = QTreeWidgetItem(self.tree)
            empty.setText(0, "暂无关联数据 — 点击「分析」按钮生成")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            return

        # Build tree: group by second-level depth
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
            item = QTreeWidgetItem(root)
            item.setText(0, f"{_relation_icon(r['relation_type'])} {r['target_name']}  [{r['relation_type']}]")
            item.setData(0, Qt.ItemDataRole.UserRole, r["target_name"])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, r.get("explanation", ""))

            # Second-level relations
            sub_rels = [s for s in relations if s.get("_depth") == 2 and s.get("_parent") == r["target_name"]]
            for s in sub_rels:
                sub_item = QTreeWidgetItem(item)
                sub_item.setText(0, f"{_relation_icon(s['relation_type'])} {s['target_name']}  [{s['relation_type']}]")
                sub_item.setData(0, Qt.ItemDataRole.UserRole, s["target_name"])
                sub_item.setData(0, Qt.ItemDataRole.UserRole + 1, s.get("explanation", ""))

        self.tree.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        explanation = item.data(0, Qt.ItemDataRole.UserRole + 1) or ""
        concept_name = item.data(0, Qt.ItemDataRole.UserRole) or ""
        if explanation:
            self.detail.setHtml(
                f'<div style="color: #cdd6f4; font-size: 13px; line-height: 1.6;">'
                f'<b>{concept_name}</b><br>{explanation}</div>'
            )


def _relation_icon(rel_type: str) -> str:
    return {
        "包含": "🔗",
        "对立": "⚡",
        "发展": "🌱",
        "背景": "📜",
        "引用": "📖",
    }.get(rel_type, "➤")
```

- [ ] **Step 2: Verify the widget imports**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'D:\\Code\\Spark'); from gui.knowledge_graph import KnowledgeGraphPanel; print('knowledge_graph OK')"
Expected: knowledge_graph OK
```

- [ ] **Step 3: Commit**

```bash
git add gui/knowledge_graph.py
git commit -m "feat: add knowledge graph panel — search box + tree widget + detail view"
```

---

### Task 5: Reader Tab Integration (`gui/reader_tab.py`)

**Files:**
- Modify: `gui/reader_tab.py`

This is the largest integration task. The reader tab's right panel needs to support two views (explanation / knowledge graph) switched by context, the analysis chain needs to become serial (explain → extract), and highlight/bookmark infrastructure needs to be added.

- [ ] **Step 1: Modify imports at top of `gui/reader_tab.py`**

Replace lines 1-23 (the imports block) with:

```python
"""
Reader tab — built-in text reader with smart concept detection.
Opens .txt/.md/.pdf files, tracks cursor position, and auto-explains core concepts.
Right panel now includes knowledge graph integration.
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QTextBrowser, QSplitter, QLabel,
    QFileDialog, QMessageBox, QLineEdit, QMenu, QStackedWidget,
)
from pathlib import Path

from gui.ai_worker import AiWorker
from gui.file_parser import parse_file
from gui.pdf_renderer import PdfRenderer
from gui.toc_panel import TocPanel
from gui.knowledge_graph import KnowledgeGraphPanel
from backend import knowledge_db
from backend.concept_extractor import extract_concepts, extract_concepts_for_text
from backend.config import CHAPTER_SUMMARY_PROMPT, SELECTION_SUMMARY_PROMPT
```

- [ ] **Step 2: Modify right panel in `_build_ui` — replace single QTextBrowser with QStackedWidget + search box**

Replace lines 136-153 (the right panel section) with:

```python
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

        # Stacked widget: explanation (index 0) ↔ knowledge graph (index 1)
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
```

- [ ] **Step 3: Add "总结本章" button to toolbar**

After line 84 (`toolbar.addWidget(self.toc_toggle_btn)`), add:

```python
        self.summary_btn = QPushButton("📝 总结本章")
        self.summary_btn.setFixedHeight(28)
        self.summary_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 12px; }"
        )
        self.summary_btn.setToolTip("对当前章节生成结构化总结")
        self.summary_btn.clicked.connect(self._summarize_chapter)
        self.summary_btn.hide()
        toolbar.addWidget(self.summary_btn)
```

- [ ] **Step 4: Add right-click context menu setup in `__init__`**

After line 51 (`self._build_ui()`), add:

```python
        self._setup_context_menu()

    def _setup_context_menu(self):
        """Set up right-click context menu for the reader."""
        self.reader.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.reader.customContextMenuRequested.connect(self._show_context_menu)
```

- [ ] **Step 5: Add new methods for right panel switching, context menu, search, highlights, bookmarks, summary**

Add after the `_build_ui` method, before the `_toggle_toc` method (insert at line 208 in the current file):

```python
    # ── Right panel switching ──

    def _switch_to_explain(self):
        """Show the explanation view in the right panel."""
        self.search_box.clear()
        self.right_stack.setCurrentIndex(0)

    def _switch_to_kg(self):
        """Show the knowledge graph view in the right panel."""
        self.right_stack.setCurrentIndex(1)

    def _on_search_concept(self):
        """Search box return — switch to KG and search."""
        text = self.search_box.text().strip()
        if not text:
            return
        self._switch_to_kg()
        # Trigger background extraction then display
        self._status_msg("🔍 正在分析概念关联...")
        self._run_in_thread(self._do_extract_and_show, text, self._on_kg_ready)

    def _on_kg_search(self, concept_name: str):
        """KG panel's own search/analyze button clicked."""
        self._status_msg("🔍 正在分析概念关联...")
        self._run_in_thread(self._do_extract_and_show, concept_name, self._on_kg_ready)

    def _do_extract_and_show(self, concept_name: str):
        """Background: extract concepts via RAG+LLM, return (name, relations)."""
        extract_concepts(concept_name)
        relations = knowledge_db.get_relations(concept_name, max_depth=2)
        return (concept_name, relations)

    def _on_kg_ready(self, result):
        """Callback: display extracted relations in KG panel."""
        concept_name, relations = result
        self.kg_panel.display_concept(concept_name)
        count = len([r for r in relations if r.get("_depth", 1) == 1])
        self._status_msg(f"✅ 找到 {count} 个关联概念")

    # ── Context menu ──

    def _show_context_menu(self, pos):
        menu = QMenu(self)

        # Highlight action
        highlight_action = menu.addAction("🖍️ 高亮选中文本\tCtrl+H")
        highlight_action.triggered.connect(self._add_highlight)

        # Bookmark action
        bookmark_action = menu.addAction("🔖 添加书签\tCtrl+D")
        bookmark_action.triggered.connect(self._add_bookmark)

        # Summarize selection
        summary_action = menu.addAction("📝 总结选中内容")
        summary_action.triggered.connect(self._summarize_selection)

        menu.addSeparator()

        # Link to concept
        link_action = menu.addAction("🔗 关联到概念...")
        link_action.triggered.connect(self._link_to_concept)

        menu.exec(self.reader.mapToGlobal(pos))

    # ── Highlights ──

    def _add_highlight(self):
        """Highlight the currently selected text."""
        cursor = self.reader.textCursor()
        if not cursor.hasSelection():
            QMessageBox.information(self, "提示", "请先选中要标注的文本")
            return

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        highlight_id = knowledge_db.add_highlight(
            self.current_file, start, end, color="#c0392b"
        )

        # Apply visual highlight
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#c0392b"))
        fmt.setForeground(QColor("#ffffff"))
        cursor.mergeCharFormat(fmt)

        self._status_msg(f"✅ 已添加高亮")

    def _load_highlights(self):
        """Restore highlights for the current file."""
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
        """Add a bookmark at the current position."""
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
        """Link the current highlight to a concept in the knowledge graph."""
        cursor = self.reader.textCursor()
        if not cursor.hasSelection():
            QMessageBox.information(self, "提示", "请先选中文本再关联概念")
            return

        start = cursor.selectionStart()
        # Find the highlight at this position
        highlights = knowledge_db.get_highlights(self.current_file)
        highlight_id = None
        for h in highlights:
            if h["start_pos"] <= start <= h["end_pos"]:
                highlight_id = h["id"]
                break

        if not highlight_id:
            QMessageBox.information(self, "提示", "请先高亮文本再关联概念")
            return

        # Simple concept picker — list existing concepts
        concepts = knowledge_db.list_concepts()
        if not concepts:
            QMessageBox.information(self, "提示", "知识图谱中暂无概念，请先在阅读中积累")
            return

        from PySide6.QtWidgets import QInputDialog
        names = [c["name"] for c in concepts]
        name, ok = QInputDialog.getItem(self, "关联到概念", "选择概念:", names, 0, False)
        if ok and name:
            knowledge_db.update_highlight_concept(highlight_id, name)
            self._status_msg(f"✅ 已关联到「{name}」")

    # ── Summarization ──

    def _summarize_chapter(self):
        """Summarize the current chapter (auto-detected from headings or sections)."""
        if not self.current_file:
            return

        text = self._get_chapter_text()
        if not text or len(text) < 50:
            QMessageBox.information(self, "提示", "当前章节内容不足，无法生成总结")
            return

        prompt = CHAPTER_SUMMARY_PROMPT.format(text=text[:4000])
        self._status_msg("📝 正在生成章节总结...")
        self._run_in_thread(self._do_summary, (self.current_file, "chapter", "auto", prompt), self._on_summary_done)

    def _summarize_selection(self):
        """Summarize the currently selected text."""
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
        self._run_in_thread(self._do_summary, (self.current_file, "selection", text[:50], prompt), self._on_summary_done)

    def _do_summary(self, args):
        """Background: run summary prompt through LLM, save to DB."""
        file_path, scope, scope_ref, prompt = args
        from backend.ollama_client import OllamaClient
        from backend.config import SYSTEM_PROMPT
        client = OllamaClient()
        result = client.chat(prompt, system_prompt=SYSTEM_PROMPT)
        client.close()
        knowledge_db.save_summary(file_path, scope, scope_ref, result)
        return result

    def _on_summary_done(self, result: str):
        """Display summary result in the explanation browser."""
        self._switch_to_explain()
        html = result.replace("\n", "<br>")
        self.explain_browser.setHtml(
            f'<div style="color: #cdd6f4; font-size: 14px; line-height: 1.7;">{html}</div>'
        )
        self._status_msg("✅ 总结完成")

    # ── Chapter detection ──

    def _get_chapter_text(self) -> str:
        """Return the text of the current chapter/section around the cursor."""
        if hasattr(self, 'pdf_renderer') and self.pdf_renderer.doc:
            return self.pdf_renderer.get_current_page_text()

        content = self.reader.toPlainText()
        if not content:
            return ""

        cursor = self.reader.textCursor()
        current_line_num = cursor.block().blockNumber()
        lines = content.split("\n")

        # Find chapter boundaries: lines starting with # or "第X章" or "第X节"
        chapter_starts = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or (
                stripped and (stripped[0].isdigit() or "第" in stripped[:3])
                and any(kw in stripped[:6] for kw in ["章", "节", "部分", "篇"])
            ):
                chapter_starts.append(i)

        if not chapter_starts:
            # Fallback: use text chunks separated by double newlines as sections
            sections = content.split("\n\n\n")
            if len(sections) > 1:
                # Find which section the cursor is in
                pos = 0
                for sec in sections:
                    sec_start = pos
                    sec_end = pos + len(sec)
                    cursor_pos_in_content = sum(len(l) + 1 for l in lines[:current_line_num])
                    if sec_start <= cursor_pos_in_content <= sec_end:
                        return sec[:4000]
                    pos = sec_end + 3
            return content[:4000]

        # Find the chapter containing the cursor
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

    # ── Utility ──

    def _status_msg(self, msg: str):
        """Update status label."""
        self.status_label.setText(msg)

    def _run_in_thread(self, func, arg, callback):
        """Run func(arg) in a QThread, call callback with result on finish."""
        from PySide6.QtCore import Signal, QThread

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
```

- [ ] **Step 6: Modify `_open_text` — restore highlights on file open**

After line 278 (`self.toc_panel.set_text_toc(lines)`) in the `_open_text` method, add:

```python
        # Restore highlights
        self._load_highlights()
        # Show summary button for text files
        self.summary_btn.show()
```

- [ ] **Step 7: Modify `_open_pdf` — show summary button**

After line 313 (`self._update_page_label()`) in the `_open_pdf` method, add:

```python
        self.summary_btn.show()
```

- [ ] **Step 8: Modify `_close_file` — hide summary button**

After line 391 (`self._toggle_page_nav(False)`) in the `_close_file` method, add:

```python
        self.summary_btn.hide()
```

- [ ] **Step 9: Modify `_trigger_analysis` — make it serial (explain → extract concepts in background)**

Replace lines 356-373 (the `_trigger_analysis` method) with:

```python
    def _trigger_analysis(self, text: str):
        """Send text to AI analysis (shared by PDF click and text cursor).
        Chain: explain concept → extract concept name → extract relations → save to knowledge.db.
        """
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
```

- [ ] **Step 10: Modify `_on_explain_done` — add concept extraction chain**

Replace lines 470-483 (the `_on_explain_done` method) with:

```python
    def _on_explain_done(self, response: str):
        """Handle successful explanation from background thread.
        Then trigger concept extraction in background (serial chain)."""
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
        """Background: detect primary concept → extract relations."""
        concept_name = extract_concepts_for_text(text)
        if concept_name:
            extract_concepts(concept_name)
            return knowledge_db.get_relations(concept_name)
        return None

    def _on_concept_chain_done(self, relations):
        """Concept extraction complete — silently update KG cache."""
        if relations:
            direct = [r for r in relations if r.get("_depth", 1) == 1]
            self._status_msg(f"✅ 分析完成 · 关联 {len(direct)} 个概念")
        else:
            self._status_msg("✅ 分析完成")
        self._last_analyzed_text = None
```

- [ ] **Step 11: Modify `_on_explain_error` — clear last analyzed text**

After line 492, add:

```python
        self._last_analyzed_text = None
```

- [ ] **Step 12: Verify the modified reader_tab.py has no syntax errors**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "import py_compile; py_compile.compile('D:\\Code\\Spark\\gui\\reader_tab.py', doraise=True); print('reader_tab.py OK')"
Expected: reader_tab.py OK
```

- [ ] **Step 13: Commit**

```bash
git add gui/reader_tab.py
git commit -m "feat: integrate knowledge graph panel, highlights, bookmarks, summaries into reader"
```

---

### Task 6: Summary Worker (`gui/summary_worker.py`)

**Files:**
- Create: `gui/summary_worker.py`

Note: The summary logic is already embedded in `reader_tab.py` via `_do_summary` / `_run_in_thread`. This standalone worker is for reuse by the chat tab or future callers. It's a thin wrapper.

- [ ] **Step 1: Create `gui/summary_worker.py`**

```python
"""
Summary worker — runs chapter/selection summarization in a QThread.
Reusable across tabs.
"""
import sys
import os
_SW_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_SW_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import QObject, Signal, Slot

from backend.ollama_client import OllamaClient
from backend.config import SYSTEM_PROMPT, CHAPTER_SUMMARY_PROMPT, SELECTION_SUMMARY_PROMPT
from backend import knowledge_db


class SummaryWorker(QObject):
    """Runs a summarization prompt in a background thread."""

    finished = Signal(str, str)  # (file_path, summary_text)
    error = Signal(str)

    def __init__(self, file_path: str, text: str, scope: str = "selection"):
        """
        Args:
            file_path: source file path (for DB storage)
            text: the text to summarize
            scope: 'chapter' or 'selection'
        """
        super().__init__()
        self.file_path = file_path
        self.text = text
        self.scope = scope

    @Slot()
    def run(self):
        try:
            prompt = (
                CHAPTER_SUMMARY_PROMPT if self.scope == "chapter"
                else SELECTION_SUMMARY_PROMPT
            ).format(text=self.text[:4000])

            client = OllamaClient()
            result = client.chat(prompt, system_prompt=SYSTEM_PROMPT)
            client.close()

            # Save to DB
            scope_ref = "auto" if self.scope == "chapter" else self.text[:50]
            knowledge_db.save_summary(self.file_path, self.scope, scope_ref, result)

            self.finished.emit(self.file_path, result)
        except Exception as e:
            self.error.emit(str(e))
```

- [ ] **Step 2: Verify import**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'D:\\Code\\Spark'); from gui.summary_worker import SummaryWorker; print('summary_worker OK')"
Expected: summary_worker OK
```

- [ ] **Step 3: Commit**

```bash
git add gui/summary_worker.py
git commit -m "feat: add summary worker — reusable QThread for chapter/selection summarization"
```

---

### Task 7: Chat Tab Concept Links (`gui/chat_tab.py`)

**Files:**
- Modify: `gui/chat_tab.py`

- [ ] **Step 1: Add knowledge graph navigation to chat tab**

Add these imports to the top of `gui/chat_tab.py` (after line 22):

```python
from backend import knowledge_db
```

And after `_on_chat_done`, add a method that makes concept names in the chat history show as clickable links:

In the `_load_messages` method, replace the current HTML generation (around lines 240-243) — find this block:

```python
            for msg in messages:
                role = msg["role"]
                content = msg["content"].replace("\n", "<br>")
                if role == "user":
                    html_parts.append(
                        f'<div style="text-align:right; margin:8px 0;">'
                        f'<span style="background:#2a1a1a; color:#f0e6d3; '
                        f'padding:6px 12px; border-radius:8px; display:inline-block; '
                        f'max-width:80%; font-size:14px;">{content}</span></div>'
                    )
                else:
                    html_parts.append(
                        f'<div style="margin:8px 0; padding:8px 12px; '
                        f'border-left:3px solid #c0392b; color:#cdd6f4; '
                        f'font-size:14px; line-height:1.7;">{content}</div>'
                    )
```

Replace with:

```python
            for msg in messages:
                role = msg["role"]
                content = msg["content"].replace("\n", "<br>")
                if role == "user":
                    html_parts.append(
                        f'<div style="text-align:right; margin:8px 0;">'
                        f'<span style="background:#2a1a1a; color:#f0e6d3; '
                        f'padding:6px 12px; border-radius:8px; display:inline-block; '
                        f'max-width:80%; font-size:14px;">{content}</span></div>'
                    )
                else:
                    # Highlight known concept names in AI responses
                    for c in knowledge_db.list_concepts():
                        name = c["name"]
                        if len(name) >= 2 and name in content:
                            content = content.replace(
                                name,
                                f'<a href="kg:{name}" style="color:#c0392b; '
                                f'text-decoration:underline; font-weight:500;">{name}</a>'
                            )
                    html_parts.append(
                        f'<div style="margin:8px 0; padding:8px 12px; '
                        f'border-left:3px solid #c0392b; color:#cdd6f4; '
                        f'font-size:14px; line-height:1.7;">{content}</div>'
                    )
```

- [ ] **Step 2: Handle concept link clicks in the message browser**

In `_build_ui`, after the message area (`self.msg_browser`) is configured (around line 100), add:

```python
        self.msg_browser.anchorClicked.connect(self._on_anchor_clicked)
```

And add the handler method:

```python
    def _on_anchor_clicked(self, url):
        """Handle clicks on concept links in chat messages."""
        link = url.toString()
        if link.startswith("kg:"):
            concept_name = link[3:]
            # Switch to reader tab and search the concept
            # Signal-based: emit to main window to switch tabs
            self.concept_clicked.emit(concept_name)
```

- [ ] **Step 3: Add the `concept_clicked` signal to ChatTab class**

After line 26 (`class ChatTab(QWidget):`), add:

```python
    concept_clicked = Signal(str)  # emitted when user clicks a concept link
```

Add the import for Signal (it should already be imported from PySide6.QtCore at line ~18 — verify).

- [ ] **Step 4: Verify no syntax errors**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "import py_compile; py_compile.compile('D:\\Code\\Spark\\gui\\chat_tab.py', doraise=True); print('chat_tab.py OK')"
Expected: chat_tab.py OK
```

- [ ] **Step 5: Commit**

```bash
git add gui/chat_tab.py
git commit -m "feat: link concept names in chat to knowledge graph"
```

---

### Task 8: Theme Styles for New Widgets (`gui/resources/theme.qss`)

**Files:**
- Modify: `gui/resources/theme.qss`

- [ ] **Step 1: Append knowledge graph and highlight styles**

Add to end of `gui/resources/theme.qss`:

```css
/* ── Knowledge Graph Panel ── */
QTreeWidget.kg-tree {
    background: transparent;
    border: none;
    font-size: 13px;
    color: #cdd6f4;
}

QTreeWidget.kg-tree::item {
    padding: 4px 0px;
    border-bottom: none;
}

QTreeWidget.kg-tree::item:hover {
    background: rgba(192, 57, 43, 0.1);
}

QTreeWidget.kg-tree::item:selected {
    background: rgba(192, 57, 43, 0.2);
    color: #f0e6d3;
}

/* ── Summary output ── */
.summary-output {
    color: #cdd6f4;
    font-size: 14px;
    line-height: 1.8;
    padding: 12px;
}

.summary-output h3 {
    color: #c0392b;
    font-size: 15px;
    margin-top: 12px;
}

/* ── Highlight tooltip ── */
.highlight-tooltip {
    background: #1e1e2a;
    color: #cdd6f4;
    border: 1px solid #c0392b;
    padding: 6px 10px;
    font-size: 12px;
}
```

- [ ] **Step 2: Commit**

```bash
git add gui/resources/theme.qss
git commit -m "style: add knowledge graph tree and summary styles to theme"
```

---

### Task 9: End-to-End Verification

- [ ] **Step 1: Run full import smoke test**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0,'D:\\Code\\Spark'); sys.stdout.reconfigure(encoding='utf-8',errors='replace')
print('1. knowledge_db...'); from backend import knowledge_db; print('  OK')
print('2. concept_extractor...'); from backend.concept_extractor import extract_concepts, extract_concepts_for_text; print('  OK')
print('3. knowledge_graph...'); from gui.knowledge_graph import KnowledgeGraphPanel; print('  OK')
print('4. summary_worker...'); from gui.summary_worker import SummaryWorker; print('  OK')
print('5. reader_tab...'); from gui.reader_tab import ReaderTab; print('  OK')
print('6. chat_tab...'); from gui.chat_tab import ChatTab; print('  OK')
print('All modules OK!')
"
Expected: All modules OK!
```

- [ ] **Step 2: Test knowledge DB CRUD operations**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0,'D:\\Code\\Spark'); sys.stdout.reconfigure(encoding='utf-8',errors='replace')
from backend import knowledge_db as db
# Test concept
cid = db.upsert_concept('矛盾', '唯物辩证法的核心范畴')
print('Concept ID:', cid)
assert db.get_concept('矛盾')['description'] == '唯物辩证法的核心范畴'
# Test relation
db.add_relation('矛盾', '对立统一', '包含', '矛盾是对立统一关系')
rels = db.get_relations('矛盾')
assert len(rels) == 1
assert rels[0]['target_name'] == '对立统一'
# Test highlight
db.add_highlight('/test/file.txt', 0, 10, color='#c0392b')
assert len(db.get_highlights('/test/file.txt')) == 1
# Test bookmark
db.add_bookmark('/test/file.pdf', page_number=5, label='重要')
assert len(db.get_bookmarks('/test/file.pdf')) == 1
# Test summary
db.save_summary('/test/file.txt', 'chapter', '第1章', '测试总结内容')
assert len(db.get_summaries('/test/file.txt')) == 1
# Test cache check
assert db.concept_has_relations('矛盾')
assert not db.concept_has_relations('不存在的概念')
print('All DB tests passed!')
"
Expected: All DB tests passed!
```

- [ ] **Step 3: Test concept extraction (requires Ollama + documents in vector store)**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0,'D:\\Code\\Spark'); sys.stdout.reconfigure(encoding='utf-8',errors='replace')
from backend.concept_extractor import extract_concepts, extract_concepts_for_text

# Test concept name detection
name = extract_concepts_for_text('矛盾是事物发展的根本动力，对立统一规律是唯物辩证法的实质和核心。')
print('Detected concept:', name)

# Test full extraction (requires docs in vector store)
if name:
    results = extract_concepts(name)
    print(f'Extracted {len(results)} relations:')
    for r in results:
        print(f'  {r[\"concept\"]} [{r[\"relation\"]}] — {r[\"explanation\"][:60]}')
print('Extraction test done!')
"
Expected: Should output detected concept name and extracted relations (if docs exist in vector store, otherwise empty list gracefully).
```

- [ ] **Step 4: Launch GUI and manually verify**

```
Run: D:\Code\Spark\backend\.venv\Scripts\python.exe gui\app.py
```

Manual checks:
1. Open a .txt or .md file → right panel shows explanation view (default)
2. Click a paragraph → explanation appears, then status shows "⚡ 正在分析知识关联..." → completes with "✅ 分析完成 · 关联 N 个概念"
3. Type a concept in search box → press Enter → KG panel shows with search results
4. Click "分析" button in KG panel → relations tree populates
5. Select text → right-click → "高亮选中文本" → text gets highlighted red
6. Right-click → "添加书签" → bookmark saved
7. Right-click → "总结选中内容" → summary appears in right panel
8. Click "📝 总结本章" toolbar button → chapter summary generates
9. Close and reopen the same file → highlights restored
10. Go to Q&A tab → ask a question about a known concept → concept name appears as clickable link

- [ ] **Step 5: Commit final verification**

```bash
git add -A
git commit -m "test: complete end-to-end verification of knowledge graph and reading enhancements"
```

---

## Verification Checklist

| # | Check | Method |
|---|-------|--------|
| 1 | All new modules import cleanly | `python -c "from backend.knowledge_db import ..."` |
| 2 | SQLite tables created automatically | Check `%APPDATA%/Spark/knowledge.db` exists after first import |
| 3 | Concept CRUD works | Insert + query + delete programmatically |
| 4 | Relation caching works | `concept_has_relations` returns True after extraction |
| 5 | Concept extraction pipeline | Ollama call succeeds, returns structured JSON |
| 6 | KG panel displays tree | GUI: search → tree with indented relations |
| 7 | Explain→extract chain fires automatically | GUI: click paragraph → status messages show progression |
| 8 | Highlights persist across file reopens | GUI: highlight text, close file, reopen → still highlighted |
| 9 | Bookmarks save and display | GUI: add bookmark, check DB row |
| 10 | Chapter summary generates | GUI: open file with chapters, click "总结本章" |
| 11 | Selection summary generates | GUI: select text, right-click → "总结选中内容" |
| 12 | Chat concept links clickable | GUI: Q&A about known concept, click link |
| 13 | No regression on existing features | GUI: tab switching, file open, PDF render, Q&A all work |
