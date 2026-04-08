from __future__ import annotations

from datetime import UTC, datetime

from app.alerts import verify_alerting
from app.argocd import sync_application
from app.analysis import verify_analysis
from app.config import load_settings
from app.fs import dump_json, load_json, load_yaml
from app.image_updater import update_gitops_manifests
from app.mesh import verify_mesh
from app.pipeline import run_ci
from app.policy import verify_policy
from app.promotion import promote_release
from app.registry import apply_secret_drift, push_image
from app.resilience import verify_resilience
from app.telemetry import verify_telemetry
from app.traffic import update_traffic


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def execute_rollout(commit_sha: str) -> dict[str, object]:
    settings = load_settings()
    if not settings.lab_root.exists():
        raise RuntimeError("The lab has not been bootstrapped yet. Run bootstrap_data.py first.")

    apply_secret_drift(settings)

    report: dict[str, object] = {
        "service": settings.service_name,
        "commit_sha": commit_sha,
        "status": "degraded",
        "started_at": _timestamp(),
        "stages": {},
    }

    ci_stage, artifact_repository = run_ci(settings, commit_sha)
    report["stages"]["ci"] = ci_stage
    if ci_stage["status"] != "success" or artifact_repository is None:
        return _persist_report(settings, report)

    registry_stage = push_image(settings, artifact_repository, commit_sha)
    report["stages"]["registry"] = registry_stage
    if registry_stage["status"] != "success":
        return _persist_report(settings, report)

    updater_stage = update_gitops_manifests(settings, commit_sha)
    report["stages"]["image_updater"] = updater_stage
    if updater_stage["status"] != "success":
        return _persist_report(settings, report)

    promotion_stage = promote_release(settings, commit_sha)
    report["stages"]["promotion"] = promotion_stage
    if promotion_stage["status"] != "success":
        return _persist_report(settings, report)

    argocd_stage = sync_application(settings, commit_sha)
    report["stages"]["argocd"] = argocd_stage
    if argocd_stage["status"] != "success":
        return _persist_report(settings, report)

    resilience_stage = verify_resilience(settings, commit_sha)
    report["stages"]["resilience"] = resilience_stage
    if resilience_stage["status"] != "success":
        return _persist_report(settings, report)

    policy_stage = verify_policy(settings, commit_sha)
    report["stages"]["policy"] = policy_stage
    if policy_stage["status"] != "success":
        return _persist_report(settings, report)

    alerts_stage = verify_alerting(settings, commit_sha)
    report["stages"]["alerts"] = alerts_stage
    if alerts_stage["status"] != "success":
        return _persist_report(settings, report)

    analysis_stage = verify_analysis(settings, commit_sha)
    report["stages"]["analysis"] = analysis_stage
    if analysis_stage["status"] != "success":
        return _persist_report(settings, report)

    traffic_stage = update_traffic(settings, commit_sha)
    report["stages"]["traffic"] = traffic_stage
    if traffic_stage["status"] != "success":
        return _persist_report(settings, report)

    mesh_stage = verify_mesh(settings, commit_sha)
    report["stages"]["mesh"] = mesh_stage
    if mesh_stage["status"] != "success":
        return _persist_report(settings, report)

    telemetry_stage = verify_telemetry(settings, commit_sha)
    report["stages"]["telemetry"] = telemetry_stage
    if telemetry_stage["status"] != "success":
        return _persist_report(settings, report)

    deployment = load_yaml(
        settings.lab_root / "cluster" / "live" / "deployments" / f"{settings.service_name}.yaml"
    )["deployment"]
    if (
        deployment.get("live_commit") == commit_sha
        and deployment.get("status") == "Healthy"
        and deployment.get("sync_status") == "Synced"
    ):
        workload_stage = {
            "status": "success",
            "message": f"Live workload now serves commit {commit_sha}.",
        }
        report["status"] = "healthy"
    else:
        workload_stage = {
            "status": "failed",
            "message": "The deployment never converged on the requested commit.",
        }
    report["stages"]["workload"] = workload_stage
    report["deployed_image"] = deployment.get("image")

    return _persist_report(settings, report)


def _persist_report(settings, report: dict[str, object]) -> dict[str, object]:
    report["finished_at"] = _timestamp()
    artifacts_dir = settings.lab_root / "artifacts"
    last_rollout_path = artifacts_dir / "last_rollout.json"
    history_path = artifacts_dir / "rollout_history.json"

    history = load_json(history_path, [])
    history.append(report)
    dump_json(last_rollout_path, report)
    dump_json(history_path, history)
    return report
