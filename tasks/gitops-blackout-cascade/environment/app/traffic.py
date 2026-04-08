from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_yaml, load_json, load_yaml


def update_traffic(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    traffic = load_yaml(gitops_root / contract["prod_overlay"] / "traffic-policy.yaml")["traffic"]
    promotion_intent = load_json(settings.lab_root / "artifacts" / "promotion_intent.json", {})
    policy_gate = load_json(settings.lab_root / "artifacts" / "policy_gate.json", {})
    analysis_report = load_json(settings.lab_root / "artifacts" / "analysis_report.json", {})

    if (
        promotion_intent.get("commit_sha") != commit_sha
        or promotion_intent.get("target_overlay") != contract["prod_overlay"]
        or promotion_intent.get("channel") != contract["promotion_channel"]
    ):
        return {
            "status": "failed",
            "message": "The traffic handoff never received the promoted hotfix intent for the prod overlay.",
        }

    if (
        policy_gate.get("commit_sha") != commit_sha
        or policy_gate.get("lane") != contract["lane_name"]
        or policy_gate.get("progressive_steps") != contract["progressive_steps"]
    ):
        return {
            "status": "failed",
            "message": "The prod traffic cutover never received the active delivery-policy profile.",
        }

    if (
        analysis_report.get("commit_sha") != commit_sha
        or analysis_report.get("template") != contract["analysis_template"]
        or analysis_report.get("metric_source") != contract["metric_source"]
        or analysis_report.get("status") != "Healthy"
    ):
        return {
            "status": "failed",
            "message": "The prod traffic cutover never received a healthy canary analysis result.",
        }

    if traffic.get("gateway_host") != contract["gateway_host"]:
        return {
            "status": "failed",
            "message": "The prod traffic policy is still pointing at the old gateway host from before the lane cutover.",
        }

    if traffic.get("gateway_class") != contract["gateway_class"]:
        return {
            "status": "failed",
            "message": "The prod traffic policy is still bound to the wrong gateway class.",
        }

    if traffic.get("route_prefix") != contract["route_prefix"]:
        return {
            "status": "failed",
            "message": "The prod traffic policy is still advertising the legacy route prefix.",
        }

    if traffic.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The prod traffic policy still points at the wrong backend service name.",
        }

    if traffic.get("analysis_template") != contract["analysis_template"]:
        return {
            "status": "failed",
            "message": "The canary traffic analysis template is still pinned to the migration profile.",
        }

    if traffic.get("progressive_steps") != contract["progressive_steps"]:
        return {
            "status": "failed",
            "message": "The progressive traffic steps still do not match the prod rollout lane.",
        }

    route_path = settings.lab_root / "cluster" / "live" / "routes" / f"{settings.service_name}.yaml"
    route = load_yaml(route_path)
    route["route"].update(
        {
            "gateway_host": contract["gateway_host"],
            "gateway_class": contract["gateway_class"],
            "route_prefix": contract["route_prefix"],
            "service": contract["traffic_service"],
            "analysis_template": contract["analysis_template"],
            "progressive_steps": contract["progressive_steps"],
            "live_commit": commit_sha,
            "status": "Healthy",
        }
    )
    dump_yaml(route_path, route)

    return {
        "status": "success",
        "message": f"Shifted prod traffic for {settings.service_name} onto commit {commit_sha}.",
    }
