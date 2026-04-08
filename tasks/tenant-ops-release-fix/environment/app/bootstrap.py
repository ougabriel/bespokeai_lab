from __future__ import annotations

import json
from datetime import datetime

from app.config import load_settings
from app.db import get_connection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS job_runs (
    job_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    runtime_seconds INTEGER NOT NULL
);
"""


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_row(raw_record: dict[str, object]) -> dict[str, object]:
    started_at = parse_timestamp(str(raw_record["started_at"]))
    finished_at = parse_timestamp(str(raw_record["finished_at"]))
    runtime_seconds = int((finished_at - started_at).total_seconds())

    return {
        "job_id": str(raw_record["job_id"]),
        "tenant": str(raw_record["tenant"]),
        "started_at": str(raw_record["started_at"]),
        "finished_at": str(raw_record["finished_at"]),
        "attempt_number": int(raw_record["attempt_number"]),
        "status": str(raw_record["status"]),
        "runtime_seconds": runtime_seconds,
    }


def bootstrap_database() -> None:
    settings = load_settings()
    connection = get_connection(settings.database_path)

    with connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute("DELETE FROM job_runs")

        with open(settings.job_runs_path, "r", encoding="utf-8") as handle:
            rows = [
                build_row(json.loads(line))
                for line in handle
                if line.strip()
            ]

        connection.executemany(
            """
            INSERT INTO job_runs (
                job_id,
                tenant,
                started_at,
                finished_at,
                attempt_no,
                status,
                runtime_seconds
            ) VALUES (
                :job_id,
                :tenant,
                :started_at,
                :finished_at,
                :attempt_number,
                :status,
                :runtime_seconds
            )
            """,
            rows,
        )
