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
            "SELECT COUNT(*) AS row_count FROM task_runs"
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
