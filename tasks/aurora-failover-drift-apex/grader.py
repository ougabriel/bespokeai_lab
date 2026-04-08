#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from apex_arena._types import GradingResult


ROOT = Path(__file__).resolve().parent
SCORE_SCRIPT = ROOT / "tests" / "score_task.py"
REPORT_PATH = Path("/logs/verifier/score_report.json")
DEFAULT_WEIGHTS = {
    "release_contract_repaired": 0.2,
    "observability_and_resilience_repaired": 0.2,
    "traffic_mesh_telemetry_repaired": 0.2,
    "first_failover_rollout": 0.2,
    "second_failover_convergence": 0.2,
}


def load_report(stdout: str) -> dict[str, object]:
    if REPORT_PATH.exists():
        try:
            return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    if stdout.strip():
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass

    return {}


def build_feedback(payload: dict[str, object], stderr: str, returncode: int) -> str:
    parts: list[str] = []
    subscores = payload.get("subscores", {})
    if isinstance(subscores, dict):
        ordered = [
            f"{name}={float(score):.3f}"
            for name, score in subscores.items()
            if isinstance(score, (int, float))
        ]
        if ordered:
            parts.append("subscores: " + ", ".join(ordered))

    details = payload.get("details", {})
    if isinstance(details, dict):
        fatal_error = details.get("fatal_error")
        if fatal_error:
            parts.append(f"fatal_error: {fatal_error}")
        objective_checks = details.get("objective_checks", {})
        if isinstance(objective_checks, dict):
            first = objective_checks.get("first_failover_rollout", {})
            second = objective_checks.get("second_failover_convergence", {})
            if isinstance(first, dict):
                stage_ratio = first.get("stage_ratio")
                if isinstance(stage_ratio, (int, float)):
                    parts.append(f"first_failover_stage_ratio={float(stage_ratio):.3f}")
            if isinstance(second, dict):
                stable = second.get("stable_end_state")
                if isinstance(stable, (int, float)):
                    parts.append(f"stable_end_state={float(stable):.3f}")

    if returncode != 0:
        parts.append(f"grader_returncode={returncode}")
    if stderr.strip():
        compact_stderr = " ".join(stderr.strip().split())
        parts.append(f"stderr={compact_stderr[:300]}")

    return " | ".join(parts) if parts else "No grader feedback captured."


def grade(transcript: str) -> GradingResult:
    del transcript

    if REPORT_PATH.exists():
        REPORT_PATH.unlink()

    result = subprocess.run(
        [sys.executable, str(SCORE_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    payload = load_report(result.stdout)

    score = payload.get("score", 0.0)
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0.0

    raw_subscores = payload.get("subscores", {})
    subscores = {}
    if isinstance(raw_subscores, dict):
        for name, value in raw_subscores.items():
            try:
                subscores[str(name)] = float(value)
            except (TypeError, ValueError):
                continue

    raw_weights = payload.get("weights", {})
    weights = {}
    if isinstance(raw_weights, dict):
        for name, value in raw_weights.items():
            try:
                weights[str(name)] = float(value)
            except (TypeError, ValueError):
                continue
    if not weights:
        weights = DEFAULT_WEIGHTS.copy()

    feedback = build_feedback(payload, result.stderr, result.returncode)

    return GradingResult(
        score=round(numeric_score, 3),
        subscores=subscores,
        weights=weights,
        feedback=feedback,
    )


if __name__ == "__main__":
    result = grade("")
    print(json.dumps(result.__dict__, default=lambda obj: obj.__dict__))
