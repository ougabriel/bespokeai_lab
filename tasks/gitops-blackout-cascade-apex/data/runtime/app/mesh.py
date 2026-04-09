from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_yaml, load_json, load_yaml
from app.tooling import run_json_tool


def verify_mesh(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    analysis_report = load_json(settings.lab_root / "artifacts" / "analysis_report.json", {})
    route = load_yaml(settings.lab_root / "cluster" / "live" / "routes" / f"{settings.service_name}.yaml")["route"]

    if (
        analysis_report.get("commit_sha") != commit_sha
        or analysis_report.get("template") != contract["analysis_template"]
        or analysis_report.get("status") != "Healthy"
    ):
        return {
            "status": "failed",
            "message": "The prod mesh policy never received a healthy canary analysis handoff.",
        }

    if route.get("live_commit") != commit_sha or route.get("status") != "Healthy":
        return {
            "status": "failed",
            "message": "The prod mesh policy never received a healthy live route cutover.",
        }

    virtual_service_path = gitops_root / contract["prod_overlay"] / "virtual-service.yaml"
    destination_rule_path = gitops_root / contract["prod_overlay"] / "destination-rule.yaml"
    if not virtual_service_path.exists() or not destination_rule_path.exists():
        return {
            "status": "failed",
            "message": "The prod service-mesh handoff is missing the required mesh policy resources.",
        }

    virtual_service = load_yaml(virtual_service_path)["virtual_service"]
    mesh_intent = load_yaml(gitops_root / contract["prod_overlay"] / "mesh-intent.yaml")["intent"]
    if virtual_service.get("gateway_host") != contract["gateway_host"]:
        return {
            "status": "failed",
            "message": "The virtual service is still targeting the wrong gateway host.",
        }

    if virtual_service.get("gateway_class") != contract["gateway_class"]:
        return {
            "status": "failed",
            "message": "The virtual service is still bound to the wrong gateway class.",
        }

    if virtual_service.get("route_prefix") != contract["route_prefix"]:
        return {
            "status": "failed",
            "message": "The virtual service is still using the legacy route prefix.",
        }

    if virtual_service.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The virtual service still points at the wrong backend service.",
        }

    if virtual_service.get("progressive_steps") != contract["progressive_steps"]:
        return {
            "status": "failed",
            "message": "The virtual service still uses the wrong progressive-delivery steps.",
        }

    destination_rule = load_yaml(destination_rule_path)["destination_rule"]
    if destination_rule.get("host") != contract["mesh_service_host"]:
        return {
            "status": "failed",
            "message": "The destination rule host is still pinned to the old service endpoint.",
        }

    expected_subsets = [
        {"name": "stable", "lane": contract["lane_name"], "track": "stable"},
        {"name": "canary", "lane": contract["lane_name"], "track": contract["promotion_channel"]},
    ]
    if (
        mesh_intent.get("service") != contract["service"]
        or mesh_intent.get("lane") != contract["lane_name"]
        or mesh_intent.get("service_host") != contract["mesh_service_host"]
        or mesh_intent.get("subsets") != expected_subsets
        or mesh_intent.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The durable mesh intent is still out of sync with the active prod lane.",
        }

    if destination_rule.get("subsets") != expected_subsets:
        return {
            "status": "failed",
            "message": "The destination rule subsets still do not match the active prod lane.",
        }

    tool_ok, rendered_mesh, tool_error = run_json_tool(
        gitops_root / "tools" / "render_mesh_policy.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or rendered_mesh is None:
        return {
            "status": "failed",
            "message": tool_error or "The mesh policy renderer failed.",
        }

    if (
        rendered_mesh.get("gateway_host") != contract["gateway_host"]
        or rendered_mesh.get("service_host") != contract["mesh_service_host"]
        or rendered_mesh.get("subsets") != expected_subsets
        or rendered_mesh.get("contract_label") != contract["contract_label"]
    ):
        return {
            "status": "failed",
            "message": "The mesh policy renderer is still emitting the old lane wiring.",
        }

    dump_yaml(
        settings.lab_root / "cluster" / "live" / "mesh" / f"{settings.service_name}.yaml",
        {
            "mesh": {
                "gateway_host": contract["gateway_host"],
                "gateway_class": contract["gateway_class"],
                "route_prefix": contract["route_prefix"],
                "service": contract["traffic_service"],
                "service_host": contract["mesh_service_host"],
                "live_commit": commit_sha,
                "status": "Healthy",
            }
        },
    )

    return {
        "status": "success",
        "message": f"Validated service-mesh policy for {settings.service_name} commit {commit_sha}.",
    }
