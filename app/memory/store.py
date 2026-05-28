import hashlib
import secrets
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings


class SQLiteStore:
    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def get_history(self, session_id: str, limit: int | None = None) -> list[dict[str, str]]:
        settings = get_settings()
        row_limit = limit or settings.max_history_messages
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, row_limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def append_exchange(self, session_id: str, user_message: str, assistant_message: str) -> None:
        with self._lock, self._connect() as connection:
            self._ensure_session(connection, session_id, user_message)
            connection.executemany(
                """
                INSERT INTO messages (session_id, role, content, token_count)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (session_id, "user", user_message, estimate_tokens(user_message)),
                    (session_id, "assistant", assistant_message, estimate_tokens(assistant_message)),
                ],
            )
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = CURRENT_TIMESTAMP,
                    message_count = message_count + 2
                WHERE id = ?
                """,
                (session_id,),
            )

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, updated_at, title, stage, message_count
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            session = connection.execute(
                """
                SELECT id, created_at, updated_at, title, stage, message_count
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            if session is None:
                return None
            messages = connection.execute(
                """
                SELECT role, content, token_count, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        payload = dict(session)
        payload["messages"] = [dict(row) for row in messages]
        return payload

    def delete_session(self, session_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    def create_api_key(self, label: str) -> str:
        raw_key = "sk-" + secrets.token_urlsafe(32)
        key_hash = hash_api_key(raw_key)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_keys (key_hash, label)
                VALUES (?, ?)
                """,
                (key_hash, label[:120]),
            )
        return raw_key

    def validate_api_key(self, raw_key: str) -> dict[str, Any] | None:
        if not raw_key.startswith("sk-"):
            return None
        key_hash = hash_api_key(raw_key)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT key_hash, label, created_at, last_used_at, is_active
                FROM api_keys
                WHERE key_hash = ? AND is_active = 1
                """,
                (key_hash,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_hash = ?",
                (key_hash,),
            )
        return dict(row)

    def list_api_keys(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT key_hash, label, created_at, last_used_at, is_active
                FROM api_keys
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke_api_key(self, key_hash: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE api_keys SET is_active = 0 WHERE key_hash = ?",
                (key_hash,),
            )
            return cursor.rowcount > 0

    def count_rate_events(self, scope: str, identifier: str, since: datetime) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM rate_events
                WHERE scope = ? AND identifier = ? AND created_at >= ?
                """,
                (scope, identifier, since.isoformat()),
            ).fetchone()
        return int(row["count"])

    def record_rate_event(
        self,
        scope: str,
        identifier: str,
        endpoint: str,
        estimated_tokens: int,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rate_events (scope, identifier, endpoint, estimated_tokens, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (scope, identifier, endpoint, estimated_tokens, now_utc().isoformat()),
            )
            self._prune_rate_events(connection)

    def log_usage(
        self,
        endpoint: str,
        session_id: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        ip_address: str,
    ) -> None:
        total_tokens = prompt_tokens + completion_tokens
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_log (
                    session_id, endpoint, prompt_tokens, completion_tokens,
                    total_tokens, model, ip_address
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, endpoint, prompt_tokens, completion_tokens, total_tokens, model, ip_address),
            )

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            for statement in schema_statements():
                connection.execute(statement)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _ensure_session(self, connection: sqlite3.Connection, session_id: str, first_message: str) -> None:
        title = make_title(first_message)
        connection.execute(
            """
            INSERT INTO sessions (id, title)
            VALUES (?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (session_id, title),
        )

    def save_document(
        self,
        document_id: str,
        filename: str,
        content_type: str,
        text_content: str,
        char_count: int,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (id, filename, content_type, text_content, char_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document_id, filename, content_type, text_content, char_count),
            )

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, filename, content_type, char_count, created_at FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_document_text(self, document_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT text_content FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            if row is None:
                return None
            return row["text_content"]

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, filename, content_type, char_count, created_at
                FROM documents ORDER BY created_at DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_document(self, document_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return cursor.rowcount > 0

    def _prune_rate_events(self, connection: sqlite3.Connection) -> None:
        cutoff = now_utc() - timedelta(days=2)
        connection.execute("DELETE FROM rate_events WHERE created_at < ?", (cutoff.isoformat(),))


def schema_statements() -> Iterable[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT,
            stage TEXT DEFAULT 'chat',
            ip_address TEXT,
            message_count INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            token_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)",
        """
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            endpoint TEXT NOT NULL,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            model TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_log(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_usage_ip ON usage_log(ip_address)",
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            key_hash TEXT PRIMARY KEY,
            label TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            identifier TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            estimated_tokens INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_rate_events_lookup ON rate_events(scope, identifier, created_at)",
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            text_content TEXT NOT NULL,
            char_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def estimate_tokens(value: str) -> int:
    return max(1, len(value) // 4)


def make_title(value: str) -> str:
    compact = " ".join(value.split())
    if len(compact) <= 60:
        return compact or "Untitled session"
    prefix = compact[:60].rsplit(" ", 1)[0]
    return prefix or compact[:60]


def now_utc() -> datetime:
    return datetime.now(UTC)


store = SQLiteStore()
