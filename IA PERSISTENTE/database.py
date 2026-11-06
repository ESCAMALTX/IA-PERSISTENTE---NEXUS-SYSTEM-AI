"""Memoria persistente en SQLite: conversaciones, incidentes y logs."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    diagnosis TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_id ON logs(id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------- logs
def add_log(level: str, source: str, message: str) -> dict[str, Any]:
    level = level.upper()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO logs (level, source, message, created_at) VALUES (?,?,?,?)",
            (level, source, message, now()),
        )
        log_id = cur.lastrowid
    return {"id": log_id, "level": level, "source": source, "message": message,
            "created_at": now()}


def recent_logs(limit: int = 100) -> list[dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# -------------------------------------------------------- conversations
def create_conversation(title: str | None = None) -> int:
    ts = now()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?,?,?)",
            (title or "Nueva conversación", ts, ts),
        )
        return int(cur.lastrowid)


def add_message(conversation_id: int, role: str, content: str) -> dict[str, Any]:
    ts = now()
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Conversación {conversation_id} no existe")
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?,?,?,?)",
            (conversation_id, role, content, ts),
        )
        # La primera pregunta del usuario da título a la conversación.
        if role == "user":
            conn.execute(
                "UPDATE conversations SET updated_at = ?, "
                "title = CASE WHEN title IS NULL OR title = 'Nueva conversación' "
                "THEN ? ELSE title END WHERE id = ?",
                (ts, content[:60], conversation_id),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (ts, conversation_id),
            )
        msg_id = cur.lastrowid
    return {"id": msg_id, "conversation_id": conversation_id, "role": role,
            "content": content, "created_at": ts}


def get_messages(conversation_id: int, limit: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id"
    params: tuple[Any, ...] = (conversation_id,)
    if limit:
        query = (
            "SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?) ORDER BY id"
        )
        params = (conversation_id, limit)
    with _lock, _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) "
            "AS message_count FROM conversations c ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_conversation(conversation_id: int) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


def latest_conversation_id() -> int | None:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id FROM conversations ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    return int(row["id"]) if row else None


# ------------------------------------------------------------ incidents
def create_incident(kind: str, severity: str, message: str,
                    details: dict[str, Any] | None = None,
                    diagnosis: str | None = None) -> dict[str, Any]:
    ts = now()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO incidents (kind, severity, message, details, diagnosis, "
            "status, created_at) VALUES (?,?,?,?,?,'open',?)",
            (kind, severity, message,
             json.dumps(details, ensure_ascii=False) if details else None,
             diagnosis, ts),
        )
        incident_id = cur.lastrowid
    return {"id": incident_id, "kind": kind, "severity": severity,
            "message": message, "details": details, "diagnosis": diagnosis,
            "status": "open", "created_at": ts, "resolved_at": None}


def last_incident_of(kind: str) -> dict[str, Any] | None:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)
        ).fetchone()
    return dict(row) if row else None


def set_incident_diagnosis(incident_id: int, diagnosis: str) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE incidents SET diagnosis = ? WHERE id = ?", (diagnosis, incident_id)
        )


def resolve_incident(incident_id: int) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE incidents SET status = 'resolved', resolved_at = ? "
            "WHERE id = ? AND status = 'open'",
            (now(), incident_id),
        )


def list_incidents(limit: int = 100) -> list[dict[str, Any]]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        if item["details"]:
            try:
                item["details"] = json.loads(item["details"])
            except json.JSONDecodeError:
                pass
        out.append(item)
    return out


# ---------------------------------------------------------------- stats
def memory_stats() -> dict[str, int]:
    with _lock, _connect() as conn:
        conversations = conn.execute("SELECT COUNT(*) c FROM conversations").fetchone()["c"]
        messages = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        incidents = conn.execute("SELECT COUNT(*) c FROM incidents").fetchone()["c"]
        open_incidents = conn.execute(
            "SELECT COUNT(*) c FROM incidents WHERE status = 'open'"
        ).fetchone()["c"]
        logs = conn.execute("SELECT COUNT(*) c FROM logs").fetchone()["c"]
    return {"conversations": conversations, "messages": messages,
            "incidents": incidents, "open_incidents": open_incidents, "logs": logs}
