from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import Settings

_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence REAL NOT NULL,
    needs_human_review INTEGER NOT NULL,
    sources_json TEXT NOT NULL,
    validation_passed INTEGER NOT NULL,
    validation_errors_json TEXT NOT NULL,
    repair_attempted INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_logging_db(settings: Settings) -> None:
    """Create the SQLite file and `runs` table if they do not exist."""

    with _connect(settings.logs_db_path) as conn:
        conn.executescript(_RUNS_DDL)
        conn.commit()


def fetch_recent_runs(settings: Settings, limit: int = 100) -> list[dict[str, Any]]:
    """Return recent run rows as plain dicts (for JSON responses)."""

    with _connect(settings.logs_db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, timestamp, question, answer, confidence, needs_human_review,
                   sources_json, validation_passed, validation_errors_json,
                   repair_attempted, latency_ms
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        row["needs_human_review"] = bool(row["needs_human_review"])
        row["validation_passed"] = bool(row["validation_passed"])
        row["repair_attempted"] = bool(row["repair_attempted"])
    return rows


def insert_run(
    settings: Settings,
    *,
    timestamp: str,
    question: str,
    answer: str,
    confidence: float,
    needs_human_review: bool,
    sources: list[dict[str, Any]],
    validation_passed: bool,
    validation_errors: list[str],
    repair_attempted: bool,
    latency_ms: int,
) -> int:
    """Insert a completed query run; returns the new row id."""

    payload = (
        timestamp,
        question,
        answer,
        confidence,
        1 if needs_human_review else 0,
        json.dumps(sources),
        1 if validation_passed else 0,
        json.dumps(validation_errors),
        1 if repair_attempted else 0,
        latency_ms,
    )
    with _connect(settings.logs_db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                timestamp, question, answer, confidence, needs_human_review,
                sources_json, validation_passed, validation_errors_json,
                repair_attempted, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        conn.commit()
        return int(cur.lastrowid)
