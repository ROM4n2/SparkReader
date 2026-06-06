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
