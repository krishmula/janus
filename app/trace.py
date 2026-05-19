"""Trace storage: SQLite persistence for agent runs and steps."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_conn: sqlite3.Connection | None = None


def _get_db_path() -> str:
    return os.environ.get("JANUS_DB_PATH", "artifacts/janus.db")


def init_db(db_path: str | None = None) -> None:
    """Open (or create) the database and ensure tables exist."""
    global _conn
    if db_path is None:
        db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if _conn is not None:
        _conn.close()
    _conn = sqlite3.connect(db_path)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id                TEXT PRIMARY KEY,
            goal                  TEXT NOT NULL,
            status                TEXT NOT NULL,
            final_result          TEXT,
            final_screenshot_path TEXT,
            created_at            TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS steps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT NOT NULL REFERENCES runs(run_id),
            step_number     INTEGER NOT NULL,
            action_type     TEXT NOT NULL,
            action_target   TEXT,
            status          TEXT NOT NULL,
            error           TEXT,
            latency_ms      REAL,
            screenshot_path TEXT,
            page_url        TEXT,
            page_title      TEXT,
            evaluation      TEXT,
            memory_snapshot TEXT,
            next_goal       TEXT
        );
    """)


def _ensure_conn() -> sqlite3.Connection:
    if _conn is None:
        init_db()
    assert _conn is not None
    return _conn


def insert_run(
    run_id: str,
    goal: str,
    status: str,
    final_result: dict[str, Any] | None = None,
    final_screenshot_path: str | None = None,
) -> None:
    conn = _ensure_conn()
    conn.execute(
        "INSERT INTO runs (run_id, goal, status, final_result, final_screenshot_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            run_id,
            goal,
            status,
            json.dumps(final_result) if final_result else None,
            final_screenshot_path,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def update_run_status(
    run_id: str,
    status: str,
    final_result: dict[str, Any] | None = None,
    final_screenshot_path: str | None = None,
) -> None:
    conn = _ensure_conn()
    conn.execute(
        "UPDATE runs SET status = ?, final_result = ?, final_screenshot_path = ? WHERE run_id = ?",
        (
            status,
            json.dumps(final_result) if final_result else None,
            final_screenshot_path,
            run_id,
        ),
    )
    conn.commit()


def get_run(run_id: str) -> dict[str, Any] | None:
    conn = _ensure_conn()
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def insert_step(
    run_id: str,
    step_number: int,
    action_type: str,
    action_target: str | None,
    status: str,
    error: str | None,
    latency_ms: float | None,
    screenshot_path: str | None,
    page_url: str | None,
    page_title: str | None,
    evaluation: str | None,
    memory_snapshot: str | None,
    next_goal: str | None,
) -> None:
    conn = _ensure_conn()
    conn.execute(
        """INSERT INTO steps
           (run_id, step_number, action_type, action_target, status, error,
            latency_ms, screenshot_path, page_url, page_title,
            evaluation, memory_snapshot, next_goal)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, step_number, action_type, action_target, status, error,
            latency_ms, screenshot_path, page_url, page_title,
            evaluation, memory_snapshot, next_goal,
        ),
    )
    conn.commit()


def get_steps(run_id: str) -> list[dict[str, Any]]:
    conn = _ensure_conn()
    rows = conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY step_number",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]
