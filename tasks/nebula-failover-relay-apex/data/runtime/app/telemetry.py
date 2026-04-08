from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, dump_yaml, load_json, load_yaml
from app.tooling import run_json_tool


def verify_telemetry(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    analysis_report = load_json(settings.lab_root / "artifacts" / "analysis_report.json", {})
    route = load_yaml(settings.lab_root / "cluster" / "live" / "routes" / f"{settings.service_name}.yaml")["route"]
    mesh = load_yaml(settings.lab_root / "cluster" / "live" / "mesh" / f"{settings.service_name}.yaml")["mesh"]

    if (
        analysis_report.get("commit_sha") != commit_sha
        or analysis_report.get("template") != contract["analysis_template"]
        or analysis_report.get("metric_source") != contract["metric_source"]
        or analysis_report.get("status") != "Healthy"
    ):
        return {
            "status": "failed",
            "message": "The telemetry handoff never received a healthy canary-analysis report.",
        }

    if route.get("live_commit") != commit_sha or route.get("status") != "Healthy":
        return {
            "status": "failed",
            "message": "The telemetry handoff never received a healthy live-route cutover.",
        }

    if mesh.get("live_commit") != commit_sha or mesh.get("status") != "Healthy":
        return {
            "status": "failed",
            "message": "The telemetry handoff never received a healthy mesh-policy cutover.",
        }

    telemetry_path = gitops_root / contract["prod_overlay"] / "telemetry-policy.yaml"
    if not telemetry_path.exists():
        return {
            "status": "failed",
            "message": "The prod telemetry handoff policy is missing from the active overlay.",
        }

    telemetry = load_yaml(telemetry_path)["telemetry"]
    if telemetry.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still points at the wrong prod service.",
        }

    if telemetry.get("namespace") != contract["monitor_namespace"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still targets the migration observability namespace.",
        }

    if telemetry.get("provider") != contract["telemetry_provider"]:
        return {
            "status": "failed",
            "message": "The telemetry policy is still pinned to the old telemetry provider.",
        }

    if telemetry.get("metric_source") != contract["metric_source"]:
        return {
            "status": "failed",
            "message": "The telemetry policy is still wired to the wrong metrics backend.",
        }

    if telemetry.get("gateway_class") != contract["gateway_class"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still advertises the wrong gateway class.",
        }

    if telemetry.get("route_prefix") != contract["route_prefix"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still exports the legacy route prefix.",
        }

    if telemetry.get("lane") != contract["lane_name"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still labels traffic with the wrong lane.",
        }

    if telemetry.get("trace_sampling_percent") != contract["trace_sampling_percent"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still uses the migration sampling rate.",
        }

    if telemetry.get("propagation_header") != contract["propagation_header"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still uses the legacy propagation header.",
        }

    if telemetry.get("propagation_value") != contract["lane_name"]:
        return {
            "status": "failed",
            "message": "The telemetry policy still propagates the wrong lane value.",
        }

    tool_ok, rendered_telemetry, tool_error = run_json_tool(
        gitops_root / "tools" / "render_telemetry_policy.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or rendered_telemetry is None:
        return {
            "status": "failed",
            "message": tool_error or "The telemetry policy renderer failed.",
        }

    if (
        rendered_telemetry.get("service") != contract["traffic_service"]
        or rendered_telemetry.get("namespace") != contract["monitor_namespace"]
        or rendered_telemetry.get("provider") != contract["telemetry_provider"]
        or rendered_telemetry.get("metric_source") != contract["metric_source"]
        or rendered_telemetry.get("gateway_class") != contract["gateway_class"]
        or rendered_telemetry.get("route_prefix") != contract["route_prefix"]
        or rendered_telemetry.get("lane") != contract["lane_name"]
        or rendered_telemetry.get("trace_sampling_percent") != contract["trace_sampling_percent"]
        or rendered_telemetry.get("propagation", {}).get("header") != contract["propagation_header"]
        or rendered_telemetry.get("propagation", {}).get("value") != contract["lane_name"]
    ):
        return {
            "status": "failed",
            "message": "The telemetry policy renderer is still emitting the migration-era lane contract.",
        }

    dump_json(
        settings.lab_root / "artifacts" / "telemetry_handoff.json",
        {
            "commit_sha": commit_sha,
            "lane": contract["lane_name"],
            "metric_source": contract["metric_source"],
            "provider": contract["telemetry_provider"],
            "status": "Healthy",
            "rendered": rendered_telemetry,
        },
    )

    dump_yaml(
        settings.lab_root / "cluster" / "live" / "telemetry" / f"{settings.service_name}.yaml",
        {
            "telemetry": {
                "service": contract["traffic_service"],
                "namespace": contract["monitor_namespace"],
                "provider": contract["telemetry_provider"],
                "metric_source": contract["metric_source"],
                "gateway_class": contract["gateway_class"],
                "route_prefix": contract["route_prefix"],
                "lane": contract["lane_name"],
                "trace_sampling_percent": contract["trace_sampling_percent"],
                "propagation_header": contract["propagation_header"],
                "propagation_value": contract["lane_name"],
                "live_commit": commit_sha,
                "status": "Healthy",
            }
        },
    )

    return {
        "status": "success",
        "message": f"Validated telemetry handoff for {settings.service_name} commit {commit_sha}.",
    }
