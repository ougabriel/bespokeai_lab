from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_json, load_yaml
from app.tooling import run_json_tool


def verify_alerting(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    policy_gate = load_json(settings.lab_root / "artifacts" / "policy_gate.json", {})

    if (
        policy_gate.get("commit_sha") != commit_sha
        or policy_gate.get("lane") != contract["lane_name"]
        or policy_gate.get("analysis_template") != contract["analysis_template"]
    ):
        return {
            "status": "failed",
            "message": "The prod alerting policy never received the active delivery-policy handoff.",
        }

    alert_route = load_yaml(gitops_root / contract["prod_overlay"] / "alert-route.yaml")["alert_route"]
    if alert_route.get("receiver") != contract["alert_receiver"]:
        return {
            "status": "failed",
            "message": "The canary alert route is still wired to the wrong escalation target.",
        }

    if alert_route.get("severity") != contract["alert_severity"]:
        return {
            "status": "failed",
            "message": "The canary alert route is still publishing at the wrong severity tier.",
        }

    if alert_route.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The canary alert route is still targeting the wrong prod service.",
        }

    if alert_route.get("metric_source") != contract["metric_source"]:
        return {
            "status": "failed",
            "message": "The canary alert route is still watching the wrong metrics backend.",
        }

    burn_rate_path = gitops_root / contract["prod_overlay"] / "burn-rate-alert.yaml"
    if not burn_rate_path.exists():
        return {
            "status": "failed",
            "message": "The prod burn-rate alert policy was never created for the active lane.",
        }

    burn_rate = load_yaml(burn_rate_path)["burn_rate_alert"]
    if burn_rate.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert still points at the wrong service.",
        }

    if burn_rate.get("metric_source") != contract["metric_source"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert is still reading from the wrong metrics backend.",
        }

    if burn_rate.get("short_window") != contract["burn_rate_short_window"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert short window still uses the migration threshold.",
        }

    if burn_rate.get("long_window") != contract["burn_rate_long_window"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert long window still uses the migration threshold.",
        }

    if burn_rate.get("max_burn_rate") != contract["error_budget_burn_rate"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert still uses the wrong error-budget burn threshold.",
        }

    if burn_rate.get("receiver") != contract["alert_receiver"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert is still wired to the wrong pager target.",
        }

    if burn_rate.get("severity") != contract["alert_severity"]:
        return {
            "status": "failed",
            "message": "The prod burn-rate alert is still publishing at the wrong severity.",
        }

    tool_ok, rendered_policy, tool_error = run_json_tool(
        gitops_root / "tools" / "render_alert_policy.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or rendered_policy is None:
        return {
            "status": "failed",
            "message": tool_error or "The alert policy renderer failed.",
        }

    if (
        rendered_policy.get("receiver") != contract["alert_receiver"]
        or rendered_policy.get("metric_source") != contract["metric_source"]
        or rendered_policy.get("burn_rate", {}).get("short_window") != contract["burn_rate_short_window"]
        or rendered_policy.get("burn_rate", {}).get("long_window") != contract["burn_rate_long_window"]
        or rendered_policy.get("burn_rate", {}).get("max_burn_rate") != contract["error_budget_burn_rate"]
    ):
        return {
            "status": "failed",
            "message": "The alert policy renderer is still emitting the migration-era paging profile.",
        }

    dump_json(
        settings.lab_root / "artifacts" / "alert_policy.json",
        {
            "commit_sha": commit_sha,
            "metric_source": contract["metric_source"],
            "receiver": contract["alert_receiver"],
            "service": settings.service_name,
            "status": "Armed",
            "rendered": rendered_policy,
        },
    )

    return {
        "status": "success",
        "message": f"Validated alert routing and burn-rate policy for {settings.service_name} commit {commit_sha}.",
    }
