"""
SQLite helpers for ingestion records and chat history.
This module uses the standard sqlite3 package without an ORM.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)


def _get_connection() -> sqlite3.Connection:
    """Open a SQLite connection and create the data folder if needed."""
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the project tables when they are missing."""
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ingested_entities (
                name        TEXT PRIMARY KEY,
                type        TEXT NOT NULL,
                url         TEXT,
                chunk_count INTEGER DEFAULT 0,
                ingested_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                metadata    TEXT,
                created_at  TEXT NOT NULL
            );
        """)
        conn.commit()
        logger.info("Database initialized")
    finally:
        conn.close()


# Ingestion tracking

def record_ingestion(name: str, entity_type: str, url: str, chunk_count: int) -> None:
    """Store or update the ingestion record for one entity."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ingested_entities (name, type, url, chunk_count, ingested_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, entity_type, url, chunk_count, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def is_ingested(name: str) -> bool:
    """Return whether an entity is already recorded as ingested."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM ingested_entities WHERE name = ?", (name,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_ingestion_stats() -> dict:
    """Return entity and chunk counts for status displays."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM ingested_entities").fetchone()[0]
        people = conn.execute(
            "SELECT COUNT(*) FROM ingested_entities WHERE type = 'person'"
        ).fetchone()[0]
        places = conn.execute(
            "SELECT COUNT(*) FROM ingested_entities WHERE type = 'place'"
        ).fetchone()[0]
        total_chunks = conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) FROM ingested_entities"
        ).fetchone()[0]
        return {
            "total_entities": total,
            "people": people,
            "places": places,
            "total_chunks": total_chunks,
        }
    finally:
        conn.close()


def clear_ingestion_records() -> None:
    """Remove every ingestion record from SQLite."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM ingested_entities")
        conn.commit()
    finally:
        conn.close()


# Chat history

def save_message(session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
    """Persist one chat message for a session."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO chat_history (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                json.dumps(metadata) if metadata else None,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(session_id: str, limit: int = 20) -> list[dict]:
    """Load recent messages for one session, oldest first."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT role, content, metadata, created_at
            FROM chat_history
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()

        messages = []
        for row in reversed(rows):
            msg = {"role": row["role"], "content": row["content"]}
            if row["metadata"]:
                msg["metadata"] = json.loads(row["metadata"])
            messages.append(msg)
        return messages
    finally:
        conn.close()


def clear_chat_history(session_id: str) -> None:
    """Delete all saved messages for one session."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def reset_all() -> None:
    """Recreate all database tables from scratch."""
    conn = _get_connection()
    try:
        conn.executescript("""
            DROP TABLE IF EXISTS ingested_entities;
            DROP TABLE IF EXISTS chat_history;
        """)
        conn.commit()
    finally:
        conn.close()
    init_db()
