"""
Knowledge database — SQLite-backed concept graph, highlights, bookmarks, summaries.
Auto-creates DB at %APPDATA%/Spark/knowledge.db on first use.
"""
import os
import sqlite3
import threading
from pathlib import Path


def _get_db_path() -> str:
    app_dir = Path(os.environ.get("APPDATA", Path.home() / ".local")) / "Spark"
    app_dir.mkdir(parents=True, exist_ok=True)
    return str(app_dir / "knowledge.db")


_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection. Each thread gets its own."""
    conn = getattr(_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(_get_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    _init_schema(conn)
    return conn


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
    """Delete a concept and its relations (CASCADE)."""
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
        "INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, explanation) "
        "VALUES (?, ?, ?, ?)",
        (source_id, target_id, relation_type, explanation),
    )
    conn.commit()


def get_relations(source_name: str, max_depth: int = 1) -> list[dict]:
    """Get all relations for a concept. For max_depth > 1, includes second-level."""
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
        for r in list(results):
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
        "SELECT COUNT(*) as cnt FROM relations r JOIN concepts c ON r.source_id = c.id "
        "WHERE c.name = ?",
        (name,),
    ).fetchone()
    return row["cnt"] > 0


# ── Highlights ──

def add_highlight(file_path: str, start_pos: int, end_pos: int,
                  color: str = "#c0392b", concept_name: str = None,
                  note: str = "") -> int:
    """Add a text highlight. Returns its ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO highlights (file_path, start_pos, end_pos, color, concept_name, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
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
    conn.execute(
        "UPDATE highlights SET concept_name = ? WHERE id = ?",
        (concept_name, highlight_id),
    )
    conn.commit()


# ── Bookmarks ──

def add_bookmark(file_path: str, page_number: int = None,
                 line_number: int = None, label: str = "") -> int:
    """Add a bookmark. Returns its ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO bookmarks (file_path, page_number, line_number, label) "
        "VALUES (?, ?, ?, ?)",
        (file_path, page_number, line_number, label),
    )
    conn.commit()
    return cur.lastrowid


def get_bookmarks(file_path: str) -> list[dict]:
    """Get all bookmarks for a file."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM bookmarks WHERE file_path = ? "
        "ORDER BY COALESCE(page_number, line_number)",
        (file_path,),
    ).fetchall()
    return [dict(r) for r in rows]


def remove_bookmark(bookmark_id: int):
    """Remove a bookmark by ID."""
    conn = _get_connection()
    conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
    conn.commit()


# ── Summaries ──

def save_summary(file_path: str, scope: str, scope_ref: str,
                 content: str) -> int:
    """Save a summary. scope is 'chapter' or 'selection'. Returns ID."""
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO summaries (file_path, scope, scope_ref, content) "
        "VALUES (?, ?, ?, ?)",
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
    """Close this thread's database connection."""
    conn = getattr(_local, 'conn', None)
    if conn:
        conn.close()
        _local.conn = None
