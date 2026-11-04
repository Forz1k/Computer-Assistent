"""SQLite: история диалога, память фактов, аудит действий.

Одно соединение на поток; все операции короткие. БД закрывается при shutdown.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL, role TEXT, content TEXT, meta TEXT
);
CREATE TABLE IF NOT EXISTS facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL, key TEXT UNIQUE, value TEXT
);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL, request_id TEXT, actor TEXT, action TEXT, args TEXT, result TEXT, confirmed INTEGER
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- сообщения ----
    def add_message(self, role: str, content: str, meta: dict[str, Any] | None = None) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages(ts,role,content,meta) VALUES(?,?,?,?)",
                (time.time(), role, content, json.dumps(meta or {}, ensure_ascii=False)))
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def recent_messages(self, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts,role,content,meta FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [{"ts": r[0], "role": r[1], "content": r[2], "meta": json.loads(r[3] or "{}")}
                for r in reversed(rows)]

    # ---- факты (память) ----
    def remember(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO facts(ts,key,value) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
                (time.time(), key.lower().strip(), value))
            self._conn.commit()

    def recall(self, query: str) -> list[dict[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key,value FROM facts WHERE key LIKE ? OR value LIKE ? LIMIT 20",
                (f"%{query.lower()}%", f"%{query.lower()}%")).fetchall()
        return [{"key": k, "value": v} for k, v in rows]

    # ---- аудит ----
    def log_audit(self, request_id: str, actor: str, action: str, args: dict[str, Any],
                  result: str, confirmed: bool) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit(ts,request_id,actor,action,args,result,confirmed) "
                "VALUES(?,?,?,?,?,?,?)",
                (time.time(), request_id, actor, action,
                 json.dumps(args, ensure_ascii=False)[:2000], result[:2000], 1 if confirmed else 0))
            self._conn.commit()

    def audit_tail(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts,request_id,actor,action,args,result,confirmed FROM audit "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": r[0], "request_id": r[1], "actor": r[2], "action": r[3],
                 "args": r[4], "result": r[5], "confirmed": bool(r[6])} for r in rows]
