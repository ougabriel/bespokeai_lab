from __future__ import annotations

import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
import requests

APP_DIR = Path("/app")
DB_PATH = APP_DIR / "state" / "tenant_ops.sqlite3"
BASE_URL = "http://127.0.0.1:8107"


def run_bootstrap() -> None:
    result = subprocess.run(
        ["python", "/app/bin/bootstrap_data.py"],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "bootstrap_data.py failed\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def start_server() -> subprocess.Popen[str]:
    process = subprocess.Popen(
        ["python", "/app/bin/run_server.py"],
        cwd="/app",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.time() + 20
    last_error: Exception | None = None

    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            raise AssertionError(
                "run_server.py exited before the API became ready\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        try:
            response = requests.get(f"{BASE_URL}/health", timeout=1)
            if response.status_code == 200:
                return process
        except Exception as exc:  # pragma: no cover - helpful for startup retries
            last_error = exc

        time.sleep(0.5)

    process.terminate()
    stdout, stderr = process.communicate(timeout=5)
    raise AssertionError(
        "Timed out waiting for the API to become ready\n"
        f"Last error: {last_error}\n"
        f"STDOUT:\n{stdout}\n"
        f"STDERR:\n{stderr}"
    )


@pytest.fixture()
def bootstrapped_database() -> Path:
    DB_PATH.unlink(missing_ok=True)
    run_bootstrap()
    return DB_PATH


@pytest.fixture()
def running_server(bootstrapped_database: Path) -> subprocess.Popen[str]:
    process = start_server()
    yield process
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def read_row_count() -> int:
    connection = sqlite3.connect(DB_PATH)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0])
    finally:
        connection.close()


def test_bootstrap_creates_database(bootstrapped_database: Path) -> None:
    assert bootstrapped_database.exists(), "The bootstrap script should create the sqlite database"
    assert read_row_count() == 15, "The seed data should be loaded into job_runs"


def test_bootstrap_is_idempotent(bootstrapped_database: Path) -> None:
    run_bootstrap()
    assert read_row_count() == 15, "Bootstrapping twice should not duplicate rows"


def test_health_endpoint(running_server: subprocess.Popen[str]) -> None:
    response = requests.get(f"{BASE_URL}/health", timeout=3)
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "loaded_runs": 15,
    }


def test_acme_daily_report(running_server: subprocess.Popen[str]) -> None:
    response = requests.get(f"{BASE_URL}/reports/acme/2026-02-03", timeout=3)
    assert response.status_code == 200
    assert response.json() == {
        "tenant": "acme",
        "report_date": "2026-02-03",
        "successful_jobs": 3,
        "failed_jobs": 2,
        "total_jobs": 5,
        "total_runtime_seconds": 137,
        "success_rate": 0.6,
    }


def test_zephyr_daily_report(running_server: subprocess.Popen[str]) -> None:
    response = requests.get(f"{BASE_URL}/reports/zephyr/2026-02-03", timeout=3)
    assert response.status_code == 200
    assert response.json() == {
        "tenant": "zephyr",
        "report_date": "2026-02-03",
        "successful_jobs": 2,
        "failed_jobs": 1,
        "total_jobs": 3,
        "total_runtime_seconds": 51,
        "success_rate": 0.667,
    }


def test_acme_follow_up_day_report(running_server: subprocess.Popen[str]) -> None:
    response = requests.get(f"{BASE_URL}/reports/acme/2026-02-04", timeout=3)
    assert response.status_code == 200
    assert response.json() == {
        "tenant": "acme",
        "report_date": "2026-02-04",
        "successful_jobs": 1,
        "failed_jobs": 1,
        "total_jobs": 2,
        "total_runtime_seconds": 38,
        "success_rate": 0.5,
    }


def test_missing_report_returns_404(running_server: subprocess.Popen[str]) -> None:
    response = requests.get(f"{BASE_URL}/reports/zephyr/2026-02-04", timeout=3)
    assert response.status_code == 404
