from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, dump_yaml, load_json, load_yaml
from app.tooling import run_json_tool


def update_traffic(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    traffic = load_yaml(gitops_root / contract["prod_overlay"] / "traffic-policy.yaml")["traffic"]
    traffic_intent = load_yaml(gitops_root / contract["prod_overlay"] / "traffic-intent.yaml")["intent"]
    gateway_intent_path = gitops_root / contract["prod_overlay"] / "gateway-intent.yaml"
    if not gateway_intent_path.exists():
        return {
            "status": "failed",
            "message": "The durable gateway intent is missing from the active prod overlay.",
        }

    gateway_intent = load_yaml(gateway_intent_path)["intent"]
    route_contract = load_yaml(gitops_root / contract["prod_overlay"] / "route-contract.yaml")["contract"]
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

    if (
        traffic_intent.get("service") != contract["service"]
        or traffic_intent.get("lane") != contract["lane_name"]
        or traffic_intent.get("gateway_host") != contract["gateway_host"]
        or traffic_intent.get("gateway_class") != contract["gateway_class"]
        or traffic_intent.get("route_prefix") != contract["route_prefix"]
        or traffic_intent.get("progressive_steps") != contract["progressive_steps"]
        or traffic_intent.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The durable traffic intent still does not match the active prod contract.",
        }

    if (
        gateway_intent.get("service") != contract["service"]
        or gateway_intent.get("lane") != contract["lane_name"]
        or gateway_intent.get("gateway_host") != contract["gateway_host"]
        or gateway_intent.get("gateway_class") != contract["gateway_class"]
        or gateway_intent.get("route_prefix") != contract["route_prefix"]
        or gateway_intent.get("live_path") != contract["live_path"]
        or gateway_intent.get("propagation_header") != contract["propagation_header"]
        or gateway_intent.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The durable gateway intent still does not match the active edge contract.",
        }

    if (
        route_contract.get("service") != contract["service"]
        or route_contract.get("lane") != contract["lane_name"]
        or route_contract.get("gateway_host") != contract["gateway_host"]
        or route_contract.get("gateway_class") != contract["gateway_class"]
        or route_contract.get("route_prefix") != contract["route_prefix"]
        or route_contract.get("live_path") != contract["live_path"]
        or route_contract.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The route contract still carries stale prod lane metadata.",
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

    tool_ok, rendered_gateway_intent, gateway_error = run_json_tool(
        gitops_root / "tools" / "render_gateway_intent.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or rendered_gateway_intent is None:
        return {
            "status": "failed",
            "message": gateway_error or "The gateway intent renderer failed.",
        }

    if (
        rendered_gateway_intent.get("service") != contract["service"]
        or rendered_gateway_intent.get("lane") != contract["lane_name"]
        or rendered_gateway_intent.get("gateway_host") != contract["gateway_host"]
        or rendered_gateway_intent.get("gateway_class") != contract["gateway_class"]
        or rendered_gateway_intent.get("route_prefix") != contract["route_prefix"]
        or rendered_gateway_intent.get("live_path") != contract["live_path"]
        or rendered_gateway_intent.get("propagation_header") != contract["propagation_header"]
        or rendered_gateway_intent.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The gateway intent renderer is still emitting the wrong prod edge contract.",
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
    dump_json(
        settings.lab_root / "artifacts" / "gateway_intent.json",
        {
            "commit_sha": commit_sha,
            "lane": contract["lane_name"],
            "gateway_host": contract["gateway_host"],
            "gateway_class": contract["gateway_class"],
            "route_prefix": contract["route_prefix"],
            "live_path": contract["live_path"],
            "propagation_header": contract["propagation_header"],
            "status": "Healthy",
        },
    )

    return {
        "status": "success",
        "message": f"Shifted prod traffic for {settings.service_name} onto commit {commit_sha}.",
    }
