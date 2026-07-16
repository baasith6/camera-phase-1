"""Persistent local state: connector credentials + durable upload queue (SQLite)."""
import os
import sqlite3
import time
from dataclasses import dataclass


@dataclass
class QueueJob:
    id: int
    clip_path: str
    camera_id: str
    duration_sec: float
    trigger: str
    retries: int
    last_error: str | None
    state: str  # pending | uploading | done | failed


class LocalStore:
    def __init__(self, state_dir: str):
        os.makedirs(state_dir, exist_ok=True)
        self.path = os.path.join(state_dir, "connector.sqlite")
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._init()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS creds (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS upload_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clip_path TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                duration_sec REAL NOT NULL,
                trigger TEXT NOT NULL,
                retries INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                state TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL
            );
            """
        )
        self._conn.commit()

    # ---- credentials ----
    def get_cred(self, key: str) -> str | None:
        cur = self._conn.execute("SELECT value FROM creds WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_cred(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO creds(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    # ---- queue ----
    def enqueue(self, clip_path: str, camera_id: str, duration_sec: float, trigger: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO upload_queue(clip_path, camera_id, duration_sec, trigger, created_at) VALUES(?,?,?,?,?)",
            (clip_path, camera_id, duration_sec, trigger, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def next_pending(self) -> QueueJob | None:
        cur = self._conn.execute(
            "SELECT id, clip_path, camera_id, duration_sec, trigger, retries, last_error, state "
            "FROM upload_queue WHERE state IN ('pending','uploading') ORDER BY id ASC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        return QueueJob(*row)

    def mark(self, job_id: int, state: str, error: str | None = None, inc_retry: bool = False) -> None:
        if inc_retry:
            self._conn.execute(
                "UPDATE upload_queue SET state=?, last_error=?, retries=retries+1 WHERE id=?",
                (state, error, job_id),
            )
        else:
            self._conn.execute(
                "UPDATE upload_queue SET state=?, last_error=? WHERE id=?",
                (state, error, job_id),
            )
        self._conn.commit()

    def pending_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM upload_queue WHERE state IN ('pending','uploading')")
        return int(cur.fetchone()[0])
