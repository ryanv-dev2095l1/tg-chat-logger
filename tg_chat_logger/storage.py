import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from tg_chat_logger.models import ParsedEvent


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    service TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    stacktrace TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_service ON events(service);
CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);
"""


class EventStorage:
    """Handles local SQLite persistence for parsed log events."""

    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Wal mode makes concurrent reads while daemon inserts much smoother
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        path = Path(self.db_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)

    def insert_event(self, event: ParsedEvent) -> bool:
        query = """
        INSERT OR IGNORE INTO events (
            channel_id, message_id, timestamp, level, service, summary, raw_payload, stacktrace
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        raw_str = json.dumps(event.raw_data) if isinstance(event.raw_data, dict) else str(event.raw_data)
        # print(f"DEBUG: inserting {event.channel_id}:{event.message_id}")
        with self._get_conn() as conn:
            cur = conn.execute(
                query,
                (
                    event.channel_id,
                    event.message_id,
                    event.timestamp.isoformat(),
                    event.level.upper(),
                    event.service,
                    event.summary,
                    raw_str,
                    event.stacktrace,
                ),
            )
            return cur.rowcount > 0

    def query_recent(
        self,
        limit: int = 50,
        service: Optional[str] = None,
        level: Optional[str] = None,
    ) -> List[dict]:
        clauses = []
        params: List[Any] = []
        if service:
            clauses.append("service = ?")
            params.append(service)
        if level:
            clauses.append("level = ?")
            params.append(level.upper())

        sql = "SELECT * FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def get_service_counts(self, since_hours: int = 24) -> Dict[str, int]:
        cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()
        sql = """
        SELECT service, COUNT(*) as cnt
        FROM events
        WHERE timestamp >= ?
        GROUP BY service
        ORDER BY cnt DESC
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, (cutoff,))
            return {row["service"]: row["cnt"] for row in cur.fetchall()}

    def purge_old_records(self, days: int = 30) -> int:
        # FIXME: runs slow on unindexed created_at if table grows over 1M records
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
            return cur.rowcount
