from __future__ import annotations

from app.config import Settings
from app.fs import load_yaml


def release_contract(settings: Settings) -> dict[str, object]:
    lane_map = load_yaml(settings.lab_root / "ops" / "topology" / "lane-map.yaml")["lane_map"]
    lane_name = lane_map["active_lane"]
    active_lane = lane_map["lanes"][lane_name]
    release_profiles = load_yaml(settings.lab_root / "ops" / "reference" / "release-profiles.yaml")[
        "release_profiles"
    ]["profiles"]
    resilience_profiles = load_yaml(
        settings.lab_root / "ops" / "reference" / "resilience-profiles.yaml"
    )["resilience_profiles"]["profiles"]
    promotion_profiles = load_yaml(
        settings.lab_root / "ops" / "reference" / "promotion-profiles.yaml"
    )["promotion_profiles"]["profiles"]
    observability_profiles = load_yaml(
        settings.lab_root / "ops" / "reference" / "observability-profiles.yaml"
    )["observability_profiles"]["profiles"]
    traffic_profiles = load_yaml(settings.lab_root / "ops" / "reference" / "traffic-profiles.yaml")[
        "traffic_profiles"
    ]["profiles"]
    release_profile = release_profiles[active_lane["release_profile"]]
    resilience_profile = resilience_profiles[active_lane["resilience_profile"]]
    promotion_profile = promotion_profiles[active_lane["promotion_profile"]]
    observability_profile = observability_profiles[active_lane["observability_profile"]]
    traffic_profile = traffic_profiles[active_lane["traffic_profile"]]
    service = load_yaml(
        settings.lab_root / "app-repo" / "services" / settings.service_name / "service-catalog.yaml"
    )["service"]

    return {
        "lane_name": lane_name,
        "service": service["name"],
        "tracked_service": service["tracked_service"],
        "traffic_service": service["traffic_service"],
        "contract_label": f"{lane_name}.{promotion_profile['channel']}.{service['name']}",
        "image_repository": f"{release_profile['registry_host']}/{service['image_repo']}",
        "required_runner_profile": release_profile["required_runner_profile"],
        "target_branch": release_profile["target_branch"],
        "tag_source": release_profile["tag_source"],
        "write_back_target": release_profile["write_back_target"],
        "write_back_branch": release_profile["write_back_branch"],
        "min_replicas": resilience_profile["min_replicas"],
        "max_replicas": resilience_profile["max_replicas"],
        "cpu_target_utilization": resilience_profile["cpu_target_utilization"],
        "memory_target_utilization": resilience_profile["memory_target_utilization"],
        "min_available": resilience_profile["min_available"],
        "prod_overlay": promotion_profile["prod_overlay"],
        "prod_project": promotion_profile["prod_project"],
        "sync_policy": promotion_profile["sync_policy"],
        "promotion_channel": promotion_profile["channel"],
        "promotion_mode": promotion_profile["mode"],
        "rollout_hold_minutes": promotion_profile["hold_minutes"],
        "rollback_on_slo_breach": promotion_profile["rollback_on_slo_breach"],
        "analysis_template": observability_profile["analysis_template"],
        "analysis_window_minutes": observability_profile["analysis_window_minutes"],
        "analysis_success_rate_slo": observability_profile["success_rate_slo"],
        "metric_source": observability_profile["metric_source"],
        "burn_rate_short_window": observability_profile["burn_rate_short_window"],
        "burn_rate_long_window": observability_profile["burn_rate_long_window"],
        "error_budget_burn_rate": observability_profile["error_budget_burn_rate"],
        "monitor_namespace": observability_profile["monitor_namespace"],
        "monitor_interval": observability_profile["monitor_interval"],
        "telemetry_provider": observability_profile["telemetry_provider"],
        "trace_sampling_percent": observability_profile["trace_sampling_percent"],
        "alert_receiver": observability_profile["alert_receiver"],
        "alert_severity": observability_profile["alert_severity"],
        "gateway_host": traffic_profile["gateway_host"],
        "gateway_class": traffic_profile["gateway_class"],
        "route_prefix": traffic_profile["route_prefix"],
        "progressive_steps": traffic_profile["progressive_steps"],
        "propagation_header": traffic_profile["propagation_header"],
        "mesh_service_host": f"{service['traffic_service']}.prod.svc.cluster.local",
        "health_path": service["health_path"],
        "live_path": f"prod/{service['name']}",
        "registry_auth_secret": "cluster/live/secrets/registry-robot.yaml",
    }
