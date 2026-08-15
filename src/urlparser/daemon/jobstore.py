"""
作业持久化：SQLite WAL（v4 M1 任务 E）

jobs 表：id/op/payload/status/result/error/created_at/updated_at。
重启恢复：running → failed（明确标记），queued 保留可重新调度。
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    TERMINAL = {SUCCEEDED, FAILED, CANCELLED}


@dataclass
class Job:
    id: str
    op: str = "parse"
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = JobStatus.QUEUED
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_row(self) -> tuple:
        return (
            self.id, self.op, json.dumps(self.payload, ensure_ascii=False),
            self.status,
            json.dumps(self.result, ensure_ascii=False) if self.result is not None else None,
            self.error, self.created_at, self.updated_at,
        )

    @classmethod
    def from_row(cls, row) -> "Job":
        job = cls(id=row[0], op=row[1], payload=json.loads(row[2] or "{}"),
                  status=row[3],
                  result=json.loads(row[4]) if row[4] else None,
                  error=row[5], created_at=row[6], updated_at=row[7])
        return job


class JobStore:
    """SQLite WAL 作业存储"""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            parent = os.path.dirname(self.db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass  # :memory: 不支持 WAL
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                op TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def add(self, job: Job):
        self._conn.execute(
            "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?)", job.to_row(),
        )
        self._conn.commit()

    def update(self, job: Job):
        self.add(job)

    def get(self, job_id: str) -> Optional[Job]:
        cur = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
        row = cur.fetchone()
        return Job.from_row(row) if row else None

    def list_all(self) -> List[Job]:
        cur = self._conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        return [Job.from_row(r) for r in cur.fetchall()]

    def recover(self) -> None:
        """重启恢复：running → failed；queued 保留"""
        self._conn.execute(
            "UPDATE jobs SET status=?, error=?, updated_at=? WHERE status=?",
            (JobStatus.FAILED, "daemon restarted before completion", time.time(),
             JobStatus.RUNNING),
        )
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
