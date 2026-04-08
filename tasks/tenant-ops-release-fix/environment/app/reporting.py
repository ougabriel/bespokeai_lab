from __future__ import annotations

import sqlite3


def build_daily_report(
    connection: sqlite3.Connection,
    tenant: str,
    report_date: str,
) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS successful_jobs,
            COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_jobs,
            COALESCE(SUM(runtime_seconds), 0) AS total_runtime_seconds,
            COUNT(*) AS total_jobs
        FROM job_runs
        WHERE tenant = ? AND substr(started_at, 1, 10) = ?
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
