from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_json, load_yaml
from app.tooling import run_json_tool


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

    observability_handoff = load_yaml(
        gitops_root / contract["prod_overlay"] / "observability-handoff.yaml"
    )["handoff"]
    if (
        observability_handoff.get("service") != contract["service"]
        or observability_handoff.get("lane") != contract["lane_name"]
        or observability_handoff.get("analysis_template") != contract["analysis_template"]
        or observability_handoff.get("metric_source") != contract["metric_source"]
        or observability_handoff.get("monitor_namespace") != contract["monitor_namespace"]
        or observability_handoff.get("receiver") != contract["alert_receiver"]
        or observability_handoff.get("severity") != contract["alert_severity"]
        or observability_handoff.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The observability handoff still carries the wrong prod contract metadata.",
        }

    analysis_handoff = load_yaml(gitops_root / contract["prod_overlay"] / "analysis-handoff.yaml")["handoff"]
    if (
        analysis_handoff.get("service") != contract["service"]
        or analysis_handoff.get("lane") != contract["lane_name"]
        or analysis_handoff.get("analysis_template") != contract["analysis_template"]
        or analysis_handoff.get("window_minutes") != contract["analysis_window_minutes"]
        or analysis_handoff.get("success_rate_slo") != contract["analysis_success_rate_slo"]
        or analysis_handoff.get("metric_source") != contract["metric_source"]
        or analysis_handoff.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The analysis handoff still points at the migration-era analysis contract.",
        }

    monitor_handoff_path = gitops_root / contract["prod_overlay"] / "monitor-handoff.yaml"
    if not monitor_handoff_path.exists():
        return {
            "status": "failed",
            "message": "The monitor handoff is missing from the active prod overlay.",
        }

    monitor_handoff = load_yaml(monitor_handoff_path)["handoff"]
    if (
        monitor_handoff.get("service") != contract["service"]
        or monitor_handoff.get("lane") != contract["lane_name"]
        or monitor_handoff.get("namespace") != contract["monitor_namespace"]
        or monitor_handoff.get("path") != contract["health_path"]
        or monitor_handoff.get("interval") != contract["monitor_interval"]
        or monitor_handoff.get("analysis_template") != contract["analysis_template"]
        or monitor_handoff.get("receiver") != contract["alert_receiver"]
        or monitor_handoff.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The monitor handoff still carries the wrong prod observability contract.",
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

    tool_ok, rendered_handoff, tool_error = run_json_tool(
        gitops_root / "tools" / "render_analysis_handoff.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or rendered_handoff is None:
        return {
            "status": "failed",
            "message": tool_error or "The analysis handoff renderer failed.",
        }

    if (
        rendered_handoff.get("service") != contract["service"]
        or rendered_handoff.get("lane") != contract["lane_name"]
        or rendered_handoff.get("analysis_template") != contract["analysis_template"]
        or rendered_handoff.get("window_minutes") != contract["analysis_window_minutes"]
        or rendered_handoff.get("success_rate_slo") != contract["analysis_success_rate_slo"]
        or rendered_handoff.get("metric_source") != contract["metric_source"]
        or rendered_handoff.get("receiver") != contract["alert_receiver"]
        or rendered_handoff.get("severity") != contract["alert_severity"]
        or rendered_handoff.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The analysis handoff renderer is still emitting the wrong prod analysis contract.",
        }

    tool_ok, rendered_monitor_handoff, monitor_error = run_json_tool(
        gitops_root / "tools" / "render_monitor_handoff.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or rendered_monitor_handoff is None:
        return {
            "status": "failed",
            "message": monitor_error or "The monitor handoff renderer failed.",
        }

    if (
        rendered_monitor_handoff.get("service") != contract["service"]
        or rendered_monitor_handoff.get("lane") != contract["lane_name"]
        or rendered_monitor_handoff.get("namespace") != contract["monitor_namespace"]
        or rendered_monitor_handoff.get("path") != contract["health_path"]
        or rendered_monitor_handoff.get("interval") != contract["monitor_interval"]
        or rendered_monitor_handoff.get("analysis_template") != contract["analysis_template"]
        or rendered_monitor_handoff.get("receiver") != contract["alert_receiver"]
        or rendered_monitor_handoff.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The monitor handoff renderer is still emitting the wrong prod monitor contract.",
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
    dump_json(
        settings.lab_root / "artifacts" / "monitor_handoff.json",
        {
            "commit_sha": commit_sha,
            "lane": contract["lane_name"],
            "namespace": contract["monitor_namespace"],
            "path": contract["health_path"],
            "interval": contract["monitor_interval"],
            "receiver": contract["alert_receiver"],
            "status": "Healthy",
        },
    )

    return {
        "status": "success",
        "message": f"Verified canary analysis and monitoring for {settings.service_name} commit {commit_sha}.",
    }
