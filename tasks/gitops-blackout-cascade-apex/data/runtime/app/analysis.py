from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_json, load_yaml


def verify_analysis(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    promotion_intent = load_json(settings.lab_root / "artifacts" / "promotion_intent.json", {})
    policy_gate = load_json(settings.lab_root / "artifacts" / "policy_gate.json", {})
    alert_policy = load_json(settings.lab_root / "artifacts" / "alert_policy.json", {})

    if (
        promotion_intent.get("commit_sha") != commit_sha
        or promotion_intent.get("target_overlay") != contract["prod_overlay"]
        or promotion_intent.get("analysis_template") != contract["analysis_template"]
    ):
        return {
            "status": "failed",
            "message": "The canary analysis never received the correct promoted hotfix handoff.",
        }

    if (
        policy_gate.get("commit_sha") != commit_sha
        or policy_gate.get("lane") != contract["lane_name"]
        or policy_gate.get("analysis_template") != contract["analysis_template"]
        or policy_gate.get("require_analysis") is not True
    ):
        return {
            "status": "failed",
            "message": "The canary analysis never received a valid prod delivery-policy approval.",
        }

    if (
        alert_policy.get("commit_sha") != commit_sha
        or alert_policy.get("metric_source") != contract["metric_source"]
        or alert_policy.get("receiver") != contract["alert_receiver"]
        or alert_policy.get("status") != "Armed"
    ):
        return {
            "status": "failed",
            "message": "The canary analysis never received a valid prod alerting handoff.",
        }

    analysis = load_yaml(gitops_root / contract["prod_overlay"] / "canary-analysis.yaml")["analysis"]
    if analysis.get("template") != contract["analysis_template"]:
        return {
            "status": "failed",
            "message": "The canary analysis template is still pinned to the migration profile.",
        }

    if analysis.get("window_minutes") != contract["analysis_window_minutes"]:
        return {
            "status": "failed",
            "message": "The canary analysis window is still using the old migration timing.",
        }

    if analysis.get("success_rate_slo") != contract["analysis_success_rate_slo"]:
        return {
            "status": "failed",
            "message": "The canary success-rate target is still using the wrong prod threshold.",
        }

    if analysis.get("metric_source") != contract["metric_source"]:
        return {
            "status": "failed",
            "message": "The canary analysis is still reading from the wrong metric source.",
        }

    monitor = load_yaml(gitops_root / contract["prod_overlay"] / "service-monitor.yaml")["monitor"]
    if monitor.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The prod service monitor still points at the wrong backend service.",
        }

    if monitor.get("namespace") != contract["monitor_namespace"]:
        return {
            "status": "failed",
            "message": "The prod service monitor is still targeting the old observability namespace.",
        }

    if monitor.get("path") != contract["health_path"]:
        return {
            "status": "failed",
            "message": "The prod service monitor is still scraping the legacy health endpoint.",
        }

    if monitor.get("interval") != contract["monitor_interval"]:
        return {
            "status": "failed",
            "message": "The prod service monitor interval is still set to the migration cadence.",
        }

    dump_json(
        settings.lab_root / "artifacts" / "analysis_report.json",
        {
            "commit_sha": commit_sha,
            "service": settings.service_name,
            "metric_source": contract["metric_source"],
            "status": "Healthy",
            "template": contract["analysis_template"],
        },
    )

    return {
        "status": "success",
        "message": f"Verified canary analysis and monitoring for {settings.service_name} commit {commit_sha}.",
    }
