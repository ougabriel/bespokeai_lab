#!/bin/bash
set -euo pipefail

cat <<'EOF' > /app/app/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR.parent / "config" / "runtime.yaml"


@dataclass(frozen=True)
class Settings:
    database_path: str
    job_runs_path: str
    api_host: str
    api_port: int


def load_settings(config_path: str | None = None) -> Settings:
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with target_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    return Settings(
        database_path=raw_config["database"]["path"],
        job_runs_path=raw_config["inputs"]["job_runs_path"],
        api_host=raw_config["api"]["host"],
        api_port=int(raw_config["api"]["port"]),
    )
EOF

cat <<'EOF' > /app/app/bootstrap.py
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
                attempt_number,
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
EOF

cat <<'EOF' > /app/app/reporting.py
from __future__ import annotations

import sqlite3


def build_daily_report(
    connection: sqlite3.Connection,
    tenant: str,
    report_date: str,
) -> dict[str, object] | None:
    row = connection.execute(
        """
        WITH ranked_runs AS (
            SELECT
                tenant,
                job_id,
                finished_at,
                runtime_seconds,
                TRIM(LOWER(status)) AS normalized_status,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant, job_id
                    ORDER BY finished_at DESC, attempt_number DESC
                ) AS run_rank
            FROM job_runs
        ),
        resolved_runs AS (
            SELECT
                tenant,
                job_id,
                normalized_status,
                finished_at,
                runtime_seconds
            FROM ranked_runs
            WHERE run_rank = 1
        )
        SELECT
            COALESCE(SUM(CASE WHEN normalized_status = 'success' THEN 1 ELSE 0 END), 0) AS successful_jobs,
            COALESCE(SUM(CASE WHEN normalized_status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_jobs,
            COALESCE(SUM(runtime_seconds), 0) AS total_runtime_seconds,
            COUNT(*) AS total_jobs
        FROM resolved_runs
        WHERE tenant = ? AND substr(finished_at, 1, 10) = ?
        """,
        (tenant, report_date),
    ).fetchone()

    if row is None or row["total_jobs"] == 0:
        return None

    total_jobs = int(row["total_jobs"])
    successful_jobs = int(row["successful_jobs"])

    return {
        "tenant": tenant,
        "report_date": report_date,
        "successful_jobs": successful_jobs,
        "failed_jobs": int(row["failed_jobs"]),
        "total_jobs": total_jobs,
        "total_runtime_seconds": int(row["total_runtime_seconds"]),
        "success_rate": round(successful_jobs / total_jobs, 3),
    }
EOF

cat <<'EOF' > /app/app/main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.config import load_settings
from app.db import get_connection
from app.reporting import build_daily_report

settings = load_settings()
app = FastAPI(title="Tenant Ops Metrics API")


@app.get("/health")
def health() -> dict[str, object]:
    connection = get_connection(settings.database_path)
    try:
        loaded_runs = connection.execute(
            "SELECT COUNT(*) AS row_count FROM job_runs"
        ).fetchone()["row_count"]
    finally:
        connection.close()

    return {
        "status": "ok",
        "loaded_runs": loaded_runs,
    }


@app.get("/reports/{tenant}/{report_date}")
def get_daily_report(tenant: str, report_date: str) -> dict[str, object]:
    connection = get_connection(settings.database_path)
    try:
        report = build_daily_report(connection, tenant, report_date)
    finally:
        connection.close()

    if report is None:
        raise HTTPException(status_code=404, detail="No runs found for tenant/date")

    return report
EOF

python /app/bin/bootstrap_data.py
