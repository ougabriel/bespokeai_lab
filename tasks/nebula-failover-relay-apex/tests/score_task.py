from __future__ import annotations

"""Functional verifier for the GitOps failover recovery task.

The scoring model follows the sample-task pattern: a small set of equal-weight
operational objectives, each backed by real functional evidence rather than a
large checklist product score.
"""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import requests
import yaml

APP_DIR = Path("/app")
LAB_ROOT = APP_DIR / "state" / "lab"
SEED_ROOT = APP_DIR / "data" / "lab_seed"
VERIFIER_DIR = Path("/logs/verifier")
BASE_URL = "http://127.0.0.1:8113"
FIRST_COMMIT = "2026.04.03-failover"
SECOND_COMMIT = "2026.04.03-failover-2"
EXPECTED_STAGES = [
    "ci",
    "registry",
    "image_updater",
    "promotion",
    "argocd",
    "resilience",
    "policy",
    "alerts",
    "analysis",
    "traffic",
    "mesh",
    "telemetry",
    "workload",
]
RELEASE_CHECKS = [
    "runner_config_migrated",
    "release_metadata_migrated",
    "release_tag_source_migrated",
    "release_bundle_renderer_migrated",
    "registry_source_of_truth_fixed",
    "updater_alignment_migrated",
    "application_alignment_migrated",
    "release_gate_alignment_migrated",
    "promotion_policy_migrated",
    "rollout_window_migrated",
]
OBSERVABILITY_CHECKS = [
    "autoscaling_policy_migrated",
    "availability_budget_migrated",
    "alert_route_migrated",
    "burn_rate_alert_migrated",
    "alert_renderer_migrated",
    "canary_analysis_migrated",
    "service_monitor_migrated",
]
TRAFFIC_CHECKS = [
    "traffic_policy_migrated",
    "mesh_policy_migrated",
    "mesh_renderer_migrated",
    "telemetry_policy_migrated",
    "telemetry_renderer_migrated",
]
DELIVERY_STAGES = ["ci", "registry", "image_updater", "promotion", "argocd"]
OBSERVABILITY_STAGES = ["resilience", "policy", "alerts", "analysis"]
TRAFFIC_STAGES = ["traffic", "mesh", "telemetry", "workload"]
WEIGHTS = {
    "release_contract_repaired": 0.2,
    "observability_and_resilience_repaired": 0.2,
    "traffic_mesh_telemetry_repaired": 0.2,
    "first_failover_rollout": 0.2,
    "second_failover_convergence": 0.2,
}
PROTECTED_HASHES = {
    "/app/app/alerts.py": "6fa172084ac7c565e9eb28fa4e71c977b52d4ddc74d5ec5bd077630f293b1bd7",
    "/app/app/analysis.py": "241413c1ce2ad9079e2060f223061a5721d23e3fce043adf671768b264b6cfcb",
    "/app/app/argocd.py": "f5efc2bc27aca2dbd95b3826d01f9224fcb91f6a086cae9dda7740bf0e48dfc2",
    "/app/app/bootstrap.py": "0ff5be8e2f5aa7ca6fb5ef2804a4fd09840103aacdc243f7652b0365e88a83f2",
    "/app/app/config.py": "8dfed16932a57845fa48e6e74fdc66b45b76922db88e720da61050e02c4625a0",
    "/app/app/contract.py": "8438bafaec88db2388b31165ae4faa09026aaff419b1f280091b9277eeb34cc3",
    "/app/app/image_updater.py": "dd3061f74002c3a4c9de3c71e9dac4957d868ea2f6f50b2d137b09c549d7a7db",
    "/app/app/main.py": "cd0ef7535e62cc5bf5fcd29da662f3bc2e35c03101f4ae23a249182aefe6133d",
    "/app/app/mesh.py": "bc5860f9b784e5b53f2ba51b76b881ef5b22a3d9ded5e7850a014e17b01c0696",
    "/app/app/pipeline.py": "b8fa4887b731128bba469b27350325a98241d370301126ba16fa949f73538628",
    "/app/app/policy.py": "88673a8e2711e3ef9b3c2bb7cbbb955a59616894fc03b49f507da83ee353ea03",
    "/app/app/promotion.py": "cadbea9a7fd1d12583acc7446013ce92cfed93eca99b8b191b8a8d2a5ead74d5",
    "/app/app/registry.py": "73eae6344e40f02092e9a494ae5fd9be24db9235716c1c58aa0e7e86b5c8aeea",
    "/app/app/resilience.py": "4a7331adb5b5c4b7b0ca284460f22956c122152f4a1b07429ef8fdda2c687f7b",
    "/app/app/rollout.py": "36d8ec238685aa8daced22a21d249d0f6fd1e65fd87a594b4206c693278c5133",
    "/app/app/telemetry.py": "1679ce2fd248f1c9e85d5ebc956be0d5ade87a122ab6c84b602eaa82c240f13f",
    "/app/app/tooling.py": "45620b5c03ce2eee710db293494412fe405941360a2b0d77b40f32f38ea8c634",
    "/app/app/traffic.py": "600687eb82a5e615ca8f61659457fc8931188926dbd70e3844d7e6fdbd7298d5",
    "/app/bin/bootstrap_data.py": "bb8a60ba64630e351bbe0890ff4844ed78ed9bfc19d72b64c0630df4ada23f13",
    "/app/bin/run_server.py": "2663d117a4d11e11d2d4915ca6990c7140b0f1a4c24dbcc1baaabcff42844826",
    "/app/bin/simulate_rollout.py": "9b26538732fa5426cf972d2beeaf059c368f8862e45248bf50c073784e8965fe",
}


def load_yaml(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_section(path: Path, *keys: str) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = load_yaml(path)
    if not isinstance(payload, dict):
        return {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def load_json(path: Path, default: object | None = None) -> object:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
    )


def parse_json_output(result: subprocess.CompletedProcess[str]) -> dict[str, object] | None:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def start_server() -> subprocess.Popen[str]:
    process = subprocess.Popen(
        ["python", "/app/bin/run_server.py"],
        cwd="/app",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            raise RuntimeError(
                "run_server.py exited before the API became ready\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        try:
            response = requests.get(f"{BASE_URL}/health", timeout=1)
            if response.status_code == 200:
                return process
        except requests.RequestException:
            pass

        time.sleep(0.5)

    process.terminate()
    stdout, stderr = process.communicate(timeout=5)
    raise RuntimeError(
        "Timed out waiting for the API to become ready\n"
        f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


def stop_server(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def release_contract() -> dict[str, object]:
    lane_map = load_yaml(LAB_ROOT / "ops" / "topology" / "lane-map.yaml")["lane_map"]
    lane_name = lane_map["active_lane"]
    lane = lane_map["lanes"][lane_name]
    release_profile = load_yaml(LAB_ROOT / "ops" / "reference" / "release-profiles.yaml")[
        "release_profiles"
    ]["profiles"][lane["release_profile"]]
    resilience_profile = load_yaml(LAB_ROOT / "ops" / "reference" / "resilience-profiles.yaml")[
        "resilience_profiles"
    ]["profiles"][lane["resilience_profile"]]
    promotion_profile = load_yaml(LAB_ROOT / "ops" / "reference" / "promotion-profiles.yaml")[
        "promotion_profiles"
    ]["profiles"][lane["promotion_profile"]]
    observability_profile = load_yaml(
        LAB_ROOT / "ops" / "reference" / "observability-profiles.yaml"
    )["observability_profiles"]["profiles"][lane["observability_profile"]]
    traffic_profile = load_yaml(LAB_ROOT / "ops" / "reference" / "traffic-profiles.yaml")[
        "traffic_profiles"
    ]["profiles"][lane["traffic_profile"]]
    service = load_yaml(LAB_ROOT / "app-repo" / "services" / "nebula-relay" / "service-catalog.yaml")[
        "service"
    ]

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


def expected_secret() -> dict[str, object]:
    broker = load_yaml(SEED_ROOT / "ops" / "identity" / "registry-broker.yaml")["broker"]
    profile = broker["profiles"][broker["active_profile"]]
    return {
        "name": broker["secret_name"],
        "username": profile["username"],
        "token": "-".join(profile["token_parts"]),
        "scopes": profile["scopes"],
    }


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_integrity() -> tuple[bool, dict[str, bool]]:
    checks: dict[str, bool] = {}
    for path, expected_hash in PROTECTED_HASHES.items():
        checks[path] = sha256(path) == expected_hash
    return all(checks.values()), checks


def stage_ratio(report: dict[str, object] | None) -> float:
    if not report:
        return 0.0
    stages = report.get("stages", {})
    successes = 0
    for stage_name in EXPECTED_STAGES:
        if stages.get(stage_name, {}).get("status") == "success":
            successes += 1
    return successes / len(EXPECTED_STAGES)


def stage_group_complete(report: dict[str, object] | None, stage_names: list[str]) -> bool:
    if not report:
        return False
    stages = report.get("stages", {})
    return all(stages.get(stage_name, {}).get("status") == "success" for stage_name in stage_names)


def stage_group_ratio(report: dict[str, object] | None, stage_names: list[str]) -> float:
    if not report:
        return 0.0
    stages = report.get("stages", {})
    successes = 0
    for stage_name in stage_names:
        if stages.get(stage_name, {}).get("status") == "success":
            successes += 1
    return successes / len(stage_names)


def rollout_complete(report: dict[str, object] | None) -> bool:
    return bool(report) and report.get("status") == "healthy" and stage_group_complete(report, EXPECTED_STAGES)


def checks_complete(names: list[str], raw_checks: dict[str, float]) -> bool:
    return all(raw_checks.get(name, 0.0) == 1.0 for name in names)


def checks_ratio(names: list[str], raw_checks: dict[str, float]) -> float:
    if not names:
        return 0.0
    return sum(raw_checks.get(name, 0.0) for name in names) / len(names)


def bool_ratio(values: list[bool]) -> float:
    if not values:
        return 0.0
    return sum(1.0 if value else 0.0 for value in values) / len(values)


def stable_end_state() -> tuple[float, dict[str, bool]]:
    checks: dict[str, bool] = {}
    contract = release_contract()
    gitops_root = LAB_ROOT / contract["write_back_target"]
    expected = expected_secret()

    last_report = load_json(LAB_ROOT / "artifacts" / "last_rollout.json", {})
    last_stages = last_report.get("stages", {})
    checks["last_report_is_second_commit"] = (
        last_report.get("commit_sha") == SECOND_COMMIT
        and last_report.get("status") == "healthy"
        and all(last_stages.get(name, {}).get("status") == "success" for name in EXPECTED_STAGES)
    )

    promotion_intent = load_json(LAB_ROOT / "artifacts" / "promotion_intent.json", {})
    checks["promotion_intent_tracks_second_commit"] = (
        promotion_intent.get("commit_sha") == SECOND_COMMIT
        and promotion_intent.get("target_overlay") == contract["prod_overlay"]
        and promotion_intent.get("channel") == contract["promotion_channel"]
        and promotion_intent.get("analysis_template") == contract["analysis_template"]
    )

    policy_gate = load_json(LAB_ROOT / "artifacts" / "policy_gate.json", {})
    checks["policy_gate_tracks_second_commit"] = (
        policy_gate.get("commit_sha") == SECOND_COMMIT
        and policy_gate.get("lane") == contract["lane_name"]
        and policy_gate.get("require_analysis") is True
        and policy_gate.get("progressive_steps") == contract["progressive_steps"]
    )

    resilience_gate = load_json(LAB_ROOT / "artifacts" / "resilience_gate.json", {})
    checks["resilience_gate_tracks_second_commit"] = (
        resilience_gate.get("commit_sha") == SECOND_COMMIT
        and resilience_gate.get("lane") == contract["lane_name"]
        and resilience_gate.get("status") == "Ready"
    )

    alert_policy = load_json(LAB_ROOT / "artifacts" / "alert_policy.json", {})
    checks["alert_policy_tracks_second_commit"] = (
        alert_policy.get("commit_sha") == SECOND_COMMIT
        and alert_policy.get("metric_source") == contract["metric_source"]
        and alert_policy.get("receiver") == contract["alert_receiver"]
        and alert_policy.get("status") == "Armed"
    )

    analysis_report = load_json(LAB_ROOT / "artifacts" / "analysis_report.json", {})
    checks["analysis_report_tracks_second_commit"] = (
        analysis_report.get("commit_sha") == SECOND_COMMIT
        and analysis_report.get("template") == contract["analysis_template"]
        and analysis_report.get("metric_source") == contract["metric_source"]
        and analysis_report.get("status") == "Healthy"
    )

    telemetry_handoff = load_json(LAB_ROOT / "artifacts" / "telemetry_handoff.json", {})
    checks["telemetry_handoff_tracks_second_commit"] = (
        telemetry_handoff.get("commit_sha") == SECOND_COMMIT
        and telemetry_handoff.get("lane") == contract["lane_name"]
        and telemetry_handoff.get("metric_source") == contract["metric_source"]
        and telemetry_handoff.get("provider") == contract["telemetry_provider"]
        and telemetry_handoff.get("status") == "Healthy"
    )

    values = load_yaml(gitops_root / contract["prod_overlay"] / "values.yaml")
    checks["gitops_tag_advanced"] = values.get("image") == {
        "repository": contract["image_repository"],
        "tag": SECOND_COMMIT,
    }

    deployment_path = LAB_ROOT / "cluster" / "live" / "deployments" / "nebula-relay.yaml"
    deployment = load_yaml(deployment_path)["deployment"] if deployment_path.exists() else {}
    checks["live_deployment_converged"] = deployment == {
        "service": "nebula-relay",
        "namespace": "prod",
        "image": f"{contract['image_repository']}:{SECOND_COMMIT}",
        "status": "Healthy",
        "sync_status": "Synced",
        "live_commit": SECOND_COMMIT,
        "source_path": contract["prod_overlay"],
    }

    route_path = LAB_ROOT / "cluster" / "live" / "routes" / "nebula-relay.yaml"
    route = load_yaml(route_path)["route"] if route_path.exists() else {}
    checks["live_route_converged"] = route == {
        "service": contract["traffic_service"],
        "gateway_host": contract["gateway_host"],
        "gateway_class": contract["gateway_class"],
        "route_prefix": contract["route_prefix"],
        "analysis_template": contract["analysis_template"],
        "progressive_steps": contract["progressive_steps"],
        "live_commit": SECOND_COMMIT,
        "status": "Healthy",
    }

    mesh_path = LAB_ROOT / "cluster" / "live" / "mesh" / "nebula-relay.yaml"
    mesh = load_yaml(mesh_path)["mesh"] if mesh_path.exists() else {}
    checks["live_mesh_converged"] = mesh == {
        "gateway_host": contract["gateway_host"],
        "gateway_class": contract["gateway_class"],
        "route_prefix": contract["route_prefix"],
        "service": contract["traffic_service"],
        "service_host": contract["mesh_service_host"],
        "live_commit": SECOND_COMMIT,
        "status": "Healthy",
    }

    telemetry_path = LAB_ROOT / "cluster" / "live" / "telemetry" / "nebula-relay.yaml"
    telemetry = load_yaml(telemetry_path)["telemetry"] if telemetry_path.exists() else {}
    checks["live_telemetry_converged"] = telemetry == {
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
        "live_commit": SECOND_COMMIT,
        "status": "Healthy",
    }

    live_secret = load_yaml(LAB_ROOT / "cluster" / "live" / "secrets" / "registry-robot.yaml")
    checks["live_secret_matches_expected"] = live_secret == expected

    return (1.0 if all(checks.values()) else 0.0), checks


def write_outputs(score: float, subscores: dict[str, float], details: dict[str, object]) -> None:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    (VERIFIER_DIR / "reward.txt").write_text(f"{score:.3f}\n", encoding="utf-8")
    payload = {
        "score": round(score, 3),
        "weights": WEIGHTS,
        "subscores": subscores,
        "details": details,
    }
    (VERIFIER_DIR / "score_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> None:
    details: dict[str, object] = {}
    raw_checks: dict[str, float] = {}
    objective_scores: dict[str, float] = {name: 0.0 for name in WEIGHTS}
    server: subprocess.Popen[str] | None = None

    try:
        first_bootstrap = run_command(["python", "/app/bin/bootstrap_data.py"])
        second_bootstrap = run_command(["python", "/app/bin/bootstrap_data.py"])
        first_bootstrap_json = parse_json_output(first_bootstrap)
        second_bootstrap_json = parse_json_output(second_bootstrap)
        details["bootstrap"] = {
            "first_returncode": first_bootstrap.returncode,
            "second_returncode": second_bootstrap.returncode,
            "first_stdout": first_bootstrap.stdout,
            "first_stderr": first_bootstrap.stderr,
            "second_stdout": second_bootstrap.stdout,
            "second_stderr": second_bootstrap.stderr,
        }
        raw_checks["bootstrap_idempotent"] = 1.0 if (
            first_bootstrap.returncode == 0
            and second_bootstrap.returncode == 0
            and first_bootstrap_json
            and second_bootstrap_json
            and load_json(LAB_ROOT / "artifacts" / "rollout_history.json", None) == []
        ) else 0.0

        contract = release_contract()
        gitops_root = LAB_ROOT / contract["write_back_target"]
        details["release_contract"] = contract

        runner = load_yaml(LAB_ROOT / "app-repo" / "ci" / "runner.yaml")["runner"]
        release_plan = load_yaml(LAB_ROOT / "app-repo" / "ci" / "release-plan.yaml")["release_plan"]
        raw_checks["runner_config_migrated"] = 1.0 if (
            runner.get("docker_host") == "unix:///var/run/docker.sock"
            and runner.get("expected_socket") == "unix:///var/run/docker.sock"
            and runner.get("profile") == release_plan.get("required_runner_profile") == contract["required_runner_profile"]
        ) else 0.0
        details["runner"] = runner
        details["release_plan"] = release_plan

        release_metadata = load_yaml(LAB_ROOT / "app-repo" / "services" / "nebula-relay" / "release.yaml")
        raw_checks["release_metadata_migrated"] = 1.0 if (
            release_plan.get("target_branch") == contract["target_branch"]
            and release_metadata.get("branch") == contract["target_branch"]
            and release_plan.get("artifact_repository") == contract["image_repository"]
            and release_metadata.get("artifact_repository") == contract["image_repository"]
        ) else 0.0
        raw_checks["release_tag_source_migrated"] = 1.0 if (
            release_plan.get("tag_source") == contract["tag_source"]
        ) else 0.0
        details["release_metadata"] = release_metadata

        release_contract_manifest = load_section(
            LAB_ROOT / "app-repo" / "services" / "nebula-relay" / "release-contract.yaml",
            "contract",
        )
        raw_checks["release_contract_manifest_identity_aligned"] = 1.0 if (
            release_contract_manifest.get("service") == contract["service"]
            and release_contract_manifest.get("tracked_service") == contract["tracked_service"]
            and release_contract_manifest.get("traffic_service") == contract["traffic_service"]
            and release_contract_manifest.get("lane") == contract["lane_name"]
        ) else 0.0
        raw_checks["release_contract_manifest_delivery_aligned"] = 1.0 if (
            release_contract_manifest.get("target_branch") == contract["target_branch"]
            and release_contract_manifest.get("write_back_branch") == contract["write_back_branch"]
            and release_contract_manifest.get("target_overlay") == contract["prod_overlay"]
            and release_contract_manifest.get("image_repository") == contract["image_repository"]
        ) else 0.0
        raw_checks["release_contract_manifest_runtime_aligned"] = 1.0 if (
            release_contract_manifest.get("health_path") == contract["health_path"]
            and release_contract_manifest.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["release_contract_manifest_migrated"] = 1.0 if (
            raw_checks["release_contract_manifest_identity_aligned"] == 1.0
            and raw_checks["release_contract_manifest_delivery_aligned"] == 1.0
            and raw_checks["release_contract_manifest_runtime_aligned"] == 1.0
        ) else 0.0
        details["release_contract_manifest"] = release_contract_manifest

        release_baton = load_section(
            LAB_ROOT / "app-repo" / "services" / "nebula-relay" / "release-baton.yaml",
            "baton",
        )
        raw_checks["release_baton_identity_aligned"] = 1.0 if (
            release_baton.get("service") == contract["service"]
            and release_baton.get("tracked_service") == contract["tracked_service"]
            and release_baton.get("lane") == contract["lane_name"]
        ) else 0.0
        raw_checks["release_baton_delivery_aligned"] = 1.0 if (
            release_baton.get("write_back_target") == contract["write_back_target"]
            and release_baton.get("write_back_branch") == contract["write_back_branch"]
            and release_baton.get("target_overlay") == contract["prod_overlay"]
        ) else 0.0
        raw_checks["release_baton_contract_aligned"] = 1.0 if (
            release_baton.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["release_baton_migrated"] = 1.0 if (
            raw_checks["release_baton_identity_aligned"] == 1.0
            and raw_checks["release_baton_delivery_aligned"] == 1.0
            and raw_checks["release_baton_contract_aligned"] == 1.0
        ) else 0.0
        details["release_baton"] = release_baton

        release_attestation = load_section(
            LAB_ROOT / "app-repo" / "services" / "nebula-relay" / "release-attestation.yaml",
            "attestation",
        )
        raw_checks["release_attestation_identity_aligned"] = 1.0 if (
            release_attestation.get("service") == contract["service"]
            and release_attestation.get("lane") == contract["lane_name"]
        ) else 0.0
        raw_checks["release_attestation_delivery_aligned"] = 1.0 if (
            release_attestation.get("target_branch") == contract["target_branch"]
            and release_attestation.get("write_back_target") == contract["write_back_target"]
            and release_attestation.get("write_back_branch") == contract["write_back_branch"]
            and release_attestation.get("image_repository") == contract["image_repository"]
        ) else 0.0
        raw_checks["release_attestation_contract_aligned"] = 1.0 if (
            release_attestation.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["release_attestation_migrated"] = 1.0 if (
            raw_checks["release_attestation_identity_aligned"] == 1.0
            and raw_checks["release_attestation_delivery_aligned"] == 1.0
            and raw_checks["release_attestation_contract_aligned"] == 1.0
        ) else 0.0
        details["release_attestation"] = release_attestation

        release_bundle_tool = LAB_ROOT / "app-repo" / "ci" / "scripts" / "render_release_bundle.py"
        release_bundle_result = run_command(
            [
                "python",
                str(release_bundle_tool),
                "--lab-root",
                str(LAB_ROOT),
                "--service",
                contract["service"],
                "--commit-sha",
                SECOND_COMMIT,
            ]
        )
        release_bundle = parse_json_output(release_bundle_result) or {}
        raw_checks["release_bundle_core_aligned"] = 1.0 if (
            release_bundle_result.returncode == 0
            and release_bundle.get("service") == contract["service"]
            and release_bundle.get("commit_sha") == SECOND_COMMIT
            and release_bundle.get("channel") == contract["promotion_channel"]
            and release_bundle.get("tag_source") == contract["tag_source"]
            and release_bundle.get("image_repository") == contract["image_repository"]
        ) else 0.0
        raw_checks["release_bundle_handoff_aligned"] = 1.0 if (
            release_bundle_result.returncode == 0
            and release_bundle.get("target_branch") == contract["target_branch"]
            and release_bundle.get("write_back_branch") == contract["write_back_branch"]
            and release_bundle.get("tracked_service") == contract["tracked_service"]
            and release_bundle.get("traffic_service") == contract["traffic_service"]
            and release_bundle.get("target_overlay") == contract["prod_overlay"]
            and release_bundle.get("health_path") == contract["health_path"]
        ) else 0.0
        raw_checks["release_bundle_contract_aligned"] = 1.0 if (
            release_bundle_result.returncode == 0
            and release_bundle.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["release_bundle_renderer_migrated"] = 1.0 if (
            raw_checks["release_bundle_core_aligned"] == 1.0
            and raw_checks["release_bundle_handoff_aligned"] == 1.0
            and raw_checks["release_bundle_contract_aligned"] == 1.0
        ) else 0.0
        details["release_bundle_renderer"] = {
            "returncode": release_bundle_result.returncode,
            "stdout": release_bundle_result.stdout,
            "stderr": release_bundle_result.stderr,
            "payload": release_bundle,
        }

        release_attestation_tool = LAB_ROOT / "app-repo" / "ci" / "scripts" / "render_release_attestation.py"
        release_attestation_result = run_command(
            [
                "python",
                str(release_attestation_tool),
                "--lab-root",
                str(LAB_ROOT),
                "--service",
                contract["service"],
                "--commit-sha",
                SECOND_COMMIT,
            ]
        )
        rendered_release_attestation = parse_json_output(release_attestation_result) or {}
        raw_checks["release_attestation_renderer_identity_aligned"] = 1.0 if (
            release_attestation_result.returncode == 0
            and rendered_release_attestation.get("service") == contract["service"]
            and rendered_release_attestation.get("lane") == contract["lane_name"]
            and rendered_release_attestation.get("tracked_service") == contract["tracked_service"]
            and rendered_release_attestation.get("commit_sha") == SECOND_COMMIT
        ) else 0.0
        raw_checks["release_attestation_renderer_delivery_aligned"] = 1.0 if (
            release_attestation_result.returncode == 0
            and rendered_release_attestation.get("target_branch") == contract["target_branch"]
            and rendered_release_attestation.get("write_back_target") == contract["write_back_target"]
            and rendered_release_attestation.get("write_back_branch") == contract["write_back_branch"]
            and rendered_release_attestation.get("image_repository") == contract["image_repository"]
        ) else 0.0
        raw_checks["release_attestation_renderer_contract_aligned"] = 1.0 if (
            release_attestation_result.returncode == 0
            and rendered_release_attestation.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["release_attestation_renderer_migrated"] = 1.0 if (
            raw_checks["release_attestation_renderer_identity_aligned"] == 1.0
            and raw_checks["release_attestation_renderer_delivery_aligned"] == 1.0
            and raw_checks["release_attestation_renderer_contract_aligned"] == 1.0
        ) else 0.0
        details["release_attestation_renderer"] = {
            "returncode": release_attestation_result.returncode,
            "stdout": release_attestation_result.stdout,
            "stderr": release_attestation_result.stderr,
            "payload": rendered_release_attestation,
        }

        expected = expected_secret()
        source_secret = load_yaml(SEED_ROOT / "ops" / "source-of-truth" / "registry-robot.yaml")
        raw_checks["registry_source_of_truth_fixed"] = 1.0 if source_secret == expected else 0.0
        details["expected_secret"] = expected
        details["source_secret"] = source_secret

        updater = load_section(LAB_ROOT / "controllers" / "image-updater.yaml", "updater")
        raw_checks["updater_alignment_migrated"] = 1.0 if (
            updater.get("tracked_service") == contract["tracked_service"]
            and updater.get("auth_secret") == contract["registry_auth_secret"]
            and updater.get("write_back_target") == contract["write_back_target"]
            and updater.get("write_back_branch") == contract["write_back_branch"]
            and updater.get("manifest_path") == f"{contract['prod_overlay']}/values.yaml"
        ) else 0.0
        details["image_updater"] = updater

        application = load_section(gitops_root / "apps" / "nebula-relay" / "application.yaml", "application")
        values = load_yaml(gitops_root / contract["prod_overlay"] / "values.yaml")
        raw_checks["application_alignment_migrated"] = 1.0 if (
            application.get("project") == contract["prod_project"]
            and application.get("source_path") == contract["prod_overlay"]
            and application.get("sync_policy") == contract["sync_policy"]
            and values.get("image", {}).get("repository") == contract["image_repository"]
            and values.get("service", {}).get("live_path") == contract["live_path"]
        ) else 0.0
        details["application"] = application
        details["prod_values"] = values

        release_gate = load_section(gitops_root / contract["prod_overlay"] / "release-gate.yaml", "gate")
        raw_checks["release_gate_alignment_migrated"] = 1.0 if (
            contract["promotion_channel"] in release_gate.get("allowed_channels", [])
            and release_gate.get("promotion_mode") == contract["promotion_mode"]
        ) else 0.0
        details["release_gate"] = release_gate

        autoscaling_path = gitops_root / contract["prod_overlay"] / "autoscaling-policy.yaml"
        availability_path = gitops_root / contract["prod_overlay"] / "availability-budget.yaml"
        autoscaling = load_section(autoscaling_path, "autoscaling")
        availability_budget = load_section(availability_path, "budget", "availability_budget")
        raw_checks["autoscaling_policy_migrated"] = 1.0 if (
            autoscaling.get("service") == contract["traffic_service"]
            and autoscaling.get("min_replicas") == contract["min_replicas"]
            and autoscaling.get("max_replicas") == contract["max_replicas"]
            and autoscaling.get("cpu_target_utilization") == contract["cpu_target_utilization"]
            and autoscaling.get("memory_target_utilization") == contract["memory_target_utilization"]
        ) else 0.0
        raw_checks["availability_budget_migrated"] = 1.0 if (
            availability_budget.get("service") == contract["traffic_service"]
            and availability_budget.get("lane") == contract["lane_name"]
            and availability_budget.get("min_available") == contract["min_available"]
        ) else 0.0
        details["autoscaling"] = autoscaling
        details["availability_budget"] = availability_budget

        promotion_policy = load_section(gitops_root / contract["prod_overlay"] / "promotion-policy.yaml", "promotion")
        raw_checks["promotion_policy_migrated"] = 1.0 if (
            promotion_policy.get("target_branch") == contract["write_back_branch"]
            and promotion_policy.get("target_overlay") == contract["prod_overlay"]
            and promotion_policy.get("channel") == contract["promotion_channel"]
            and promotion_policy.get("analysis_template") == contract["analysis_template"]
            and promotion_policy.get("strategy") == contract["promotion_mode"]
            and promotion_policy.get("freeze") is False
        ) else 0.0
        details["promotion_policy"] = promotion_policy

        rollout_window = load_section(gitops_root / contract["prod_overlay"] / "rollout-window.yaml", "window")
        raw_checks["rollout_window_migrated"] = 1.0 if (
            rollout_window.get("lane") == contract["lane_name"]
            and rollout_window.get("freeze") is False
            and rollout_window.get("require_analysis") is True
            and rollout_window.get("hold_minutes") == contract["rollout_hold_minutes"]
            and rollout_window.get("rollback_on_slo_breach") is contract["rollback_on_slo_breach"]
            and rollout_window.get("progressive_steps") == contract["progressive_steps"]
        ) else 0.0
        details["rollout_window"] = rollout_window

        delivery_contract = load_section(
            gitops_root / contract["prod_overlay"] / "delivery-contract.yaml",
            "contract",
        )
        raw_checks["delivery_contract_operating_aligned"] = 1.0 if (
            delivery_contract.get("lane") == contract["lane_name"]
            and delivery_contract.get("channel") == contract["promotion_channel"]
            and delivery_contract.get("mode") == contract["promotion_mode"]
            and delivery_contract.get("target_overlay") == contract["prod_overlay"]
        ) else 0.0
        raw_checks["delivery_contract_signal_aligned"] = 1.0 if (
            delivery_contract.get("analysis_template") == contract["analysis_template"]
            and delivery_contract.get("metric_source") == contract["metric_source"]
            and delivery_contract.get("monitor_namespace") == contract["monitor_namespace"]
        ) else 0.0
        raw_checks["delivery_contract_network_aligned"] = 1.0 if (
            delivery_contract.get("gateway_host") == contract["gateway_host"]
            and delivery_contract.get("gateway_class") == contract["gateway_class"]
            and delivery_contract.get("route_prefix") == contract["route_prefix"]
            and delivery_contract.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["delivery_contract_migrated"] = 1.0 if (
            raw_checks["delivery_contract_operating_aligned"] == 1.0
            and raw_checks["delivery_contract_signal_aligned"] == 1.0
            and raw_checks["delivery_contract_network_aligned"] == 1.0
        ) else 0.0
        details["delivery_contract"] = delivery_contract

        observability_handoff = load_section(
            gitops_root / contract["prod_overlay"] / "observability-handoff.yaml",
            "handoff",
        )
        raw_checks["observability_handoff_identity_aligned"] = 1.0 if (
            observability_handoff.get("service") == contract["traffic_service"]
            and observability_handoff.get("lane") == contract["lane_name"]
        ) else 0.0
        raw_checks["observability_handoff_signal_aligned"] = 1.0 if (
            observability_handoff.get("analysis_template") == contract["analysis_template"]
            and observability_handoff.get("metric_source") == contract["metric_source"]
            and observability_handoff.get("monitor_namespace") == contract["monitor_namespace"]
        ) else 0.0
        raw_checks["observability_handoff_alerting_aligned"] = 1.0 if (
            observability_handoff.get("receiver") == contract["alert_receiver"]
            and observability_handoff.get("severity") == contract["alert_severity"]
            and observability_handoff.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["observability_handoff_migrated"] = 1.0 if (
            raw_checks["observability_handoff_identity_aligned"] == 1.0
            and raw_checks["observability_handoff_signal_aligned"] == 1.0
            and raw_checks["observability_handoff_alerting_aligned"] == 1.0
        ) else 0.0
        details["observability_handoff"] = observability_handoff

        analysis_handoff = load_section(
            gitops_root / contract["prod_overlay"] / "analysis-handoff.yaml",
            "handoff",
        )
        raw_checks["analysis_handoff_identity_aligned"] = 1.0 if (
            analysis_handoff.get("service") == contract["traffic_service"]
            and analysis_handoff.get("lane") == contract["lane_name"]
        ) else 0.0
        raw_checks["analysis_handoff_analysis_aligned"] = 1.0 if (
            analysis_handoff.get("analysis_template") == contract["analysis_template"]
            and analysis_handoff.get("window_minutes") == contract["analysis_window_minutes"]
            and analysis_handoff.get("success_rate_slo") == contract["analysis_success_rate_slo"]
            and analysis_handoff.get("metric_source") == contract["metric_source"]
        ) else 0.0
        raw_checks["analysis_handoff_contract_aligned"] = 1.0 if (
            analysis_handoff.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["analysis_handoff_migrated"] = 1.0 if (
            raw_checks["analysis_handoff_identity_aligned"] == 1.0
            and raw_checks["analysis_handoff_analysis_aligned"] == 1.0
            and raw_checks["analysis_handoff_contract_aligned"] == 1.0
        ) else 0.0
        details["analysis_handoff"] = analysis_handoff

        alert_route = load_section(gitops_root / contract["prod_overlay"] / "alert-route.yaml", "alert_route")
        raw_checks["alert_route_migrated"] = 1.0 if (
            alert_route.get("receiver") == contract["alert_receiver"]
            and alert_route.get("severity") == contract["alert_severity"]
            and alert_route.get("service") == contract["traffic_service"]
            and alert_route.get("metric_source") == contract["metric_source"]
        ) else 0.0
        details["alert_route"] = alert_route

        burn_rate_path = gitops_root / contract["prod_overlay"] / "burn-rate-alert.yaml"
        burn_rate_alert = load_section(burn_rate_path, "burn_rate_alert", "burn_rate")
        raw_checks["burn_rate_alert_migrated"] = 1.0 if (
            burn_rate_alert.get("service") == contract["traffic_service"]
            and burn_rate_alert.get("metric_source") == contract["metric_source"]
            and burn_rate_alert.get("short_window") == contract["burn_rate_short_window"]
            and burn_rate_alert.get("long_window") == contract["burn_rate_long_window"]
            and burn_rate_alert.get("max_burn_rate") == contract["error_budget_burn_rate"]
            and burn_rate_alert.get("receiver") == contract["alert_receiver"]
            and burn_rate_alert.get("severity") == contract["alert_severity"]
        ) else 0.0
        details["burn_rate_alert"] = burn_rate_alert

        alert_tool = gitops_root / "tools" / "render_alert_policy.py"
        alert_result = run_command(
            [
                "python",
                str(alert_tool),
                "--lab-root",
                str(LAB_ROOT),
                "--service",
                contract["service"],
                "--commit-sha",
                SECOND_COMMIT,
            ]
        )
        rendered_alert = parse_json_output(alert_result) or {}
        raw_checks["alert_renderer_core_aligned"] = 1.0 if (
            alert_result.returncode == 0
            and rendered_alert.get("service") == contract["traffic_service"]
            and rendered_alert.get("receiver") == contract["alert_receiver"]
            and rendered_alert.get("severity") == contract["alert_severity"]
            and rendered_alert.get("metric_source") == contract["metric_source"]
        ) else 0.0
        raw_checks["alert_renderer_burn_rate_aligned"] = 1.0 if (
            alert_result.returncode == 0
            and rendered_alert.get("burn_rate", {}).get("short_window") == contract["burn_rate_short_window"]
            and rendered_alert.get("burn_rate", {}).get("long_window") == contract["burn_rate_long_window"]
            and rendered_alert.get("burn_rate", {}).get("max_burn_rate") == contract["error_budget_burn_rate"]
        ) else 0.0
        raw_checks["alert_renderer_contract_aligned"] = 1.0 if (
            alert_result.returncode == 0
            and rendered_alert.get("analysis_template") == contract["analysis_template"]
            and rendered_alert.get("monitor_namespace") == contract["monitor_namespace"]
            and rendered_alert.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["alert_renderer_migrated"] = 1.0 if (
            raw_checks["alert_renderer_core_aligned"] == 1.0
            and raw_checks["alert_renderer_burn_rate_aligned"] == 1.0
            and raw_checks["alert_renderer_contract_aligned"] == 1.0
        ) else 0.0
        details["alert_renderer"] = {
            "returncode": alert_result.returncode,
            "stdout": alert_result.stdout,
            "stderr": alert_result.stderr,
            "payload": rendered_alert,
        }

        analysis_handoff_tool = gitops_root / "tools" / "render_analysis_handoff.py"
        analysis_handoff_result = run_command(
            [
                "python",
                str(analysis_handoff_tool),
                "--lab-root",
                str(LAB_ROOT),
                "--service",
                contract["service"],
                "--commit-sha",
                SECOND_COMMIT,
            ]
        )
        rendered_analysis_handoff = parse_json_output(analysis_handoff_result) or {}
        raw_checks["analysis_handoff_renderer_identity_aligned"] = 1.0 if (
            analysis_handoff_result.returncode == 0
            and rendered_analysis_handoff.get("service") == contract["traffic_service"]
            and rendered_analysis_handoff.get("lane") == contract["lane_name"]
            and rendered_analysis_handoff.get("commit_sha") == SECOND_COMMIT
        ) else 0.0
        raw_checks["analysis_handoff_renderer_analysis_aligned"] = 1.0 if (
            analysis_handoff_result.returncode == 0
            and rendered_analysis_handoff.get("analysis_template") == contract["analysis_template"]
            and rendered_analysis_handoff.get("window_minutes") == contract["analysis_window_minutes"]
            and rendered_analysis_handoff.get("success_rate_slo") == contract["analysis_success_rate_slo"]
            and rendered_analysis_handoff.get("metric_source") == contract["metric_source"]
        ) else 0.0
        raw_checks["analysis_handoff_renderer_contract_aligned"] = 1.0 if (
            analysis_handoff_result.returncode == 0
            and rendered_analysis_handoff.get("receiver") == contract["alert_receiver"]
            and rendered_analysis_handoff.get("severity") == contract["alert_severity"]
            and rendered_analysis_handoff.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["analysis_handoff_renderer_migrated"] = 1.0 if (
            raw_checks["analysis_handoff_renderer_identity_aligned"] == 1.0
            and raw_checks["analysis_handoff_renderer_analysis_aligned"] == 1.0
            and raw_checks["analysis_handoff_renderer_contract_aligned"] == 1.0
        ) else 0.0
        details["analysis_handoff_renderer"] = {
            "returncode": analysis_handoff_result.returncode,
            "stdout": analysis_handoff_result.stdout,
            "stderr": analysis_handoff_result.stderr,
            "payload": rendered_analysis_handoff,
        }

        canary_analysis = load_section(gitops_root / contract["prod_overlay"] / "canary-analysis.yaml", "analysis")
        raw_checks["canary_analysis_migrated"] = 1.0 if (
            canary_analysis.get("template") == contract["analysis_template"]
            and canary_analysis.get("window_minutes") == contract["analysis_window_minutes"]
            and canary_analysis.get("success_rate_slo") == contract["analysis_success_rate_slo"]
            and canary_analysis.get("metric_source") == contract["metric_source"]
        ) else 0.0
        details["canary_analysis"] = canary_analysis

        service_monitor = load_section(gitops_root / contract["prod_overlay"] / "service-monitor.yaml", "monitor")
        raw_checks["service_monitor_migrated"] = 1.0 if (
            service_monitor.get("service") == contract["traffic_service"]
            and service_monitor.get("namespace") == contract["monitor_namespace"]
            and service_monitor.get("path") == contract["health_path"]
            and service_monitor.get("interval") == contract["monitor_interval"]
        ) else 0.0
        details["service_monitor"] = service_monitor

        telemetry_path = gitops_root / contract["prod_overlay"] / "telemetry-policy.yaml"
        telemetry_policy = load_section(telemetry_path, "telemetry")
        raw_checks["telemetry_policy_migrated"] = 1.0 if (
            telemetry_policy.get("service") == contract["traffic_service"]
            and telemetry_policy.get("namespace") == contract["monitor_namespace"]
            and telemetry_policy.get("provider") == contract["telemetry_provider"]
            and telemetry_policy.get("metric_source") == contract["metric_source"]
            and telemetry_policy.get("gateway_class") == contract["gateway_class"]
            and telemetry_policy.get("route_prefix") == contract["route_prefix"]
            and telemetry_policy.get("lane") == contract["lane_name"]
            and telemetry_policy.get("trace_sampling_percent") == contract["trace_sampling_percent"]
            and telemetry_policy.get("propagation_header") == contract["propagation_header"]
            and telemetry_policy.get("propagation_value") == contract["lane_name"]
        ) else 0.0
        details["telemetry_policy"] = telemetry_policy

        telemetry_handoff_manifest = load_section(
            gitops_root / contract["prod_overlay"] / "telemetry-handoff.yaml",
            "handoff",
        )
        raw_checks["telemetry_handoff_service_aligned"] = 1.0 if (
            telemetry_handoff_manifest.get("service") == contract["traffic_service"]
            and telemetry_handoff_manifest.get("service_host") == contract["mesh_service_host"]
        ) else 0.0
        raw_checks["telemetry_handoff_signal_aligned"] = 1.0 if (
            telemetry_handoff_manifest.get("provider") == contract["telemetry_provider"]
            and telemetry_handoff_manifest.get("metric_source") == contract["metric_source"]
        ) else 0.0
        raw_checks["telemetry_handoff_route_aligned"] = 1.0 if (
            telemetry_handoff_manifest.get("gateway_class") == contract["gateway_class"]
            and telemetry_handoff_manifest.get("route_prefix") == contract["route_prefix"]
            and telemetry_handoff_manifest.get("propagation_header") == contract["propagation_header"]
            and telemetry_handoff_manifest.get("propagation_value") == contract["lane_name"]
            and telemetry_handoff_manifest.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["telemetry_handoff_manifest_migrated"] = 1.0 if (
            raw_checks["telemetry_handoff_service_aligned"] == 1.0
            and raw_checks["telemetry_handoff_signal_aligned"] == 1.0
            and raw_checks["telemetry_handoff_route_aligned"] == 1.0
        ) else 0.0
        details["telemetry_handoff_manifest"] = telemetry_handoff_manifest

        telemetry_tool = gitops_root / "tools" / "render_telemetry_policy.py"
        telemetry_result = run_command(
            [
                "python",
                str(telemetry_tool),
                "--lab-root",
                str(LAB_ROOT),
                "--service",
                contract["service"],
                "--commit-sha",
                SECOND_COMMIT,
            ]
        )
        telemetry_render = parse_json_output(telemetry_result) or {}
        raw_checks["telemetry_renderer_core_aligned"] = 1.0 if (
            telemetry_result.returncode == 0
            and telemetry_render.get("service") == contract["traffic_service"]
            and telemetry_render.get("namespace") == contract["monitor_namespace"]
            and telemetry_render.get("provider") == contract["telemetry_provider"]
            and telemetry_render.get("metric_source") == contract["metric_source"]
            and telemetry_render.get("gateway_class") == contract["gateway_class"]
            and telemetry_render.get("route_prefix") == contract["route_prefix"]
            and telemetry_render.get("lane") == contract["lane_name"]
            and telemetry_render.get("trace_sampling_percent") == contract["trace_sampling_percent"]
            and telemetry_render.get("service_host") == contract["mesh_service_host"]
            and telemetry_render.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["telemetry_renderer_propagation_aligned"] = 1.0 if (
            telemetry_result.returncode == 0
            and telemetry_render.get("propagation", {}).get("header") == contract["propagation_header"]
            and telemetry_render.get("propagation", {}).get("value") == contract["lane_name"]
        ) else 0.0
        raw_checks["telemetry_renderer_migrated"] = 1.0 if (
            raw_checks["telemetry_renderer_core_aligned"] == 1.0
            and raw_checks["telemetry_renderer_propagation_aligned"] == 1.0
        ) else 0.0
        details["telemetry_renderer"] = {
            "returncode": telemetry_result.returncode,
            "stdout": telemetry_result.stdout,
            "stderr": telemetry_result.stderr,
            "payload": telemetry_render,
        }

        traffic_policy = load_section(gitops_root / contract["prod_overlay"] / "traffic-policy.yaml", "traffic")
        raw_checks["traffic_policy_migrated"] = 1.0 if (
            traffic_policy.get("gateway_host") == contract["gateway_host"]
            and traffic_policy.get("gateway_class") == contract["gateway_class"]
            and traffic_policy.get("route_prefix") == contract["route_prefix"]
            and traffic_policy.get("service") == contract["traffic_service"]
            and traffic_policy.get("analysis_template") == contract["analysis_template"]
            and traffic_policy.get("progressive_steps") == contract["progressive_steps"]
        ) else 0.0
        details["traffic_policy"] = traffic_policy

        traffic_intent = load_section(
            gitops_root / contract["prod_overlay"] / "traffic-intent.yaml",
            "intent",
        )
        raw_checks["traffic_intent_core_aligned"] = 1.0 if (
            traffic_intent.get("service") == contract["traffic_service"]
            and traffic_intent.get("lane") == contract["lane_name"]
            and traffic_intent.get("gateway_host") == contract["gateway_host"]
            and traffic_intent.get("gateway_class") == contract["gateway_class"]
            and traffic_intent.get("route_prefix") == contract["route_prefix"]
        ) else 0.0
        raw_checks["traffic_intent_progressive_aligned"] = 1.0 if (
            traffic_intent.get("progressive_steps") == contract["progressive_steps"]
            and traffic_intent.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["traffic_intent_migrated"] = 1.0 if (
            raw_checks["traffic_intent_core_aligned"] == 1.0
            and raw_checks["traffic_intent_progressive_aligned"] == 1.0
        ) else 0.0
        details["traffic_intent"] = traffic_intent

        route_contract = load_section(
            gitops_root / contract["prod_overlay"] / "route-contract.yaml",
            "contract",
        )
        raw_checks["route_contract_identity_aligned"] = 1.0 if (
            route_contract.get("service") == contract["traffic_service"]
            and route_contract.get("lane") == contract["lane_name"]
        ) else 0.0
        raw_checks["route_contract_route_aligned"] = 1.0 if (
            route_contract.get("gateway_host") == contract["gateway_host"]
            and route_contract.get("gateway_class") == contract["gateway_class"]
            and route_contract.get("route_prefix") == contract["route_prefix"]
            and route_contract.get("live_path") == contract["live_path"]
        ) else 0.0
        raw_checks["route_contract_contract_aligned"] = 1.0 if (
            route_contract.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["route_contract_migrated"] = 1.0 if (
            raw_checks["route_contract_identity_aligned"] == 1.0
            and raw_checks["route_contract_route_aligned"] == 1.0
            and raw_checks["route_contract_contract_aligned"] == 1.0
        ) else 0.0
        details["route_contract"] = route_contract

        virtual_service_path = gitops_root / contract["prod_overlay"] / "virtual-service.yaml"
        destination_rule_path = gitops_root / contract["prod_overlay"] / "destination-rule.yaml"
        virtual_service = load_section(virtual_service_path, "virtual_service")
        destination_rule = load_section(destination_rule_path, "destination_rule")
        raw_checks["mesh_policy_migrated"] = 1.0 if (
            virtual_service.get("gateway_host") == contract["gateway_host"]
            and virtual_service.get("gateway_class") == contract["gateway_class"]
            and virtual_service.get("route_prefix") == contract["route_prefix"]
            and virtual_service.get("service") == contract["traffic_service"]
            and virtual_service.get("progressive_steps") == contract["progressive_steps"]
            and destination_rule.get("host") == contract["mesh_service_host"]
            and destination_rule.get("subsets") == [
                {"name": "stable", "lane": contract["lane_name"], "track": "stable"},
                {"name": "canary", "lane": contract["lane_name"], "track": contract["promotion_channel"]},
            ]
        ) else 0.0
        details["virtual_service"] = virtual_service
        details["destination_rule"] = destination_rule

        mesh_intent = load_section(
            gitops_root / contract["prod_overlay"] / "mesh-intent.yaml",
            "intent",
        )
        raw_checks["mesh_intent_core_aligned"] = 1.0 if (
            mesh_intent.get("service") == contract["traffic_service"]
            and mesh_intent.get("lane") == contract["lane_name"]
            and mesh_intent.get("service_host") == contract["mesh_service_host"]
            and mesh_intent.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["mesh_intent_subsets_aligned"] = 1.0 if (
            mesh_intent.get("subsets") == [
                {"name": "stable", "lane": contract["lane_name"], "track": "stable"},
                {"name": "canary", "lane": contract["lane_name"], "track": contract["promotion_channel"]},
            ]
        ) else 0.0
        raw_checks["mesh_intent_migrated"] = 1.0 if (
            raw_checks["mesh_intent_core_aligned"] == 1.0
            and raw_checks["mesh_intent_subsets_aligned"] == 1.0
        ) else 0.0
        details["mesh_intent"] = mesh_intent

        workload_intent = load_section(
            gitops_root / contract["prod_overlay"] / "workload-intent.yaml",
            "intent",
        )
        raw_checks["workload_intent_identity_aligned"] = 1.0 if (
            workload_intent.get("service") == contract["service"]
            and workload_intent.get("lane") == contract["lane_name"]
            and workload_intent.get("namespace") == "prod"
        ) else 0.0
        raw_checks["workload_intent_runtime_aligned"] = 1.0 if (
            workload_intent.get("image_repository") == contract["image_repository"]
            and workload_intent.get("health_path") == contract["health_path"]
            and workload_intent.get("live_path") == contract["live_path"]
        ) else 0.0
        raw_checks["workload_intent_contract_aligned"] = 1.0 if (
            workload_intent.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["workload_intent_migrated"] = 1.0 if (
            raw_checks["workload_intent_identity_aligned"] == 1.0
            and raw_checks["workload_intent_runtime_aligned"] == 1.0
            and raw_checks["workload_intent_contract_aligned"] == 1.0
        ) else 0.0
        details["workload_intent"] = workload_intent

        mesh_tool = gitops_root / "tools" / "render_mesh_policy.py"
        mesh_result = run_command(
            [
                "python",
                str(mesh_tool),
                "--lab-root",
                str(LAB_ROOT),
                "--service",
                contract["service"],
                "--commit-sha",
                SECOND_COMMIT,
            ]
        )
        rendered_mesh = parse_json_output(mesh_result) or {}
        raw_checks["mesh_renderer_route_aligned"] = 1.0 if (
            mesh_result.returncode == 0
            and rendered_mesh.get("gateway_host") == contract["gateway_host"]
            and rendered_mesh.get("gateway_class") == contract["gateway_class"]
            and rendered_mesh.get("route_prefix") == contract["route_prefix"]
            and rendered_mesh.get("service") == contract["traffic_service"]
            and rendered_mesh.get("service_host") == contract["mesh_service_host"]
            and rendered_mesh.get("contract_label") == contract["contract_label"]
        ) else 0.0
        raw_checks["mesh_renderer_subsets_aligned"] = 1.0 if (
            mesh_result.returncode == 0
            and rendered_mesh.get("subsets") == [
                {"name": "stable", "lane": contract["lane_name"], "track": "stable"},
                {"name": "canary", "lane": contract["lane_name"], "track": contract["promotion_channel"]},
            ]
        ) else 0.0
        raw_checks["mesh_renderer_migrated"] = 1.0 if (
            raw_checks["mesh_renderer_route_aligned"] == 1.0
            and raw_checks["mesh_renderer_subsets_aligned"] == 1.0
        ) else 0.0
        details["mesh_renderer"] = {
            "returncode": mesh_result.returncode,
            "stdout": mesh_result.stdout,
            "stderr": mesh_result.stderr,
            "payload": rendered_mesh,
        }

        server = start_server()
        health_response = requests.get(f"{BASE_URL}/health", timeout=3)
        details["health_response"] = {
            "status_code": health_response.status_code,
            "body": (
                health_response.json()
                if health_response.headers.get("content-type", "").startswith("application/json")
                else health_response.text
            ),
        }
        raw_checks["health_api_ready"] = 1.0 if health_response.status_code == 200 else 0.0

        runtime_ok, runtime_checks = runtime_integrity()
        details["runtime_integrity"] = runtime_checks
        details["runtime_intact"] = runtime_ok

        first_rollout = run_command(["python", "/app/bin/simulate_rollout.py", "--commit-sha", FIRST_COMMIT])
        first_report = parse_json_output(first_rollout)
        second_rollout = run_command(["python", "/app/bin/simulate_rollout.py", "--commit-sha", SECOND_COMMIT])
        second_report = parse_json_output(second_rollout)
        details["first_rollout"] = {
            "returncode": first_rollout.returncode,
            "stdout": first_rollout.stdout,
            "stderr": first_rollout.stderr,
            "report": first_report,
        }
        details["second_rollout"] = {
            "returncode": second_rollout.returncode,
            "stdout": second_rollout.stdout,
            "stderr": second_rollout.stderr,
            "report": second_report,
        }

        stable_ratio, stable_checks = stable_end_state()
        raw_checks["stable_end_state"] = stable_ratio
        details["stable_checks"] = stable_checks

        release_objective_checks = {
            "bootstrap_idempotent": raw_checks["bootstrap_idempotent"],
            "release_contract_checks": checks_ratio(RELEASE_CHECKS, raw_checks),
            "release_contract_identity": raw_checks.get("release_contract_manifest_identity_aligned", 0.0),
            "release_contract_delivery": raw_checks.get("release_contract_manifest_delivery_aligned", 0.0),
            "release_contract_runtime": raw_checks.get("release_contract_manifest_runtime_aligned", 0.0),
            "release_contract_manifest_complete": raw_checks.get("release_contract_manifest_migrated", 0.0),
            "release_bundle_alignment": bool_ratio(
                [
                    raw_checks.get("release_bundle_core_aligned", 0.0) == 1.0,
                    raw_checks.get("release_bundle_handoff_aligned", 0.0) == 1.0,
                    raw_checks.get("release_bundle_contract_aligned", 0.0) == 1.0,
                ]
            ),
            "release_baton_identity": raw_checks.get("release_baton_identity_aligned", 0.0),
            "release_baton_delivery": raw_checks.get("release_baton_delivery_aligned", 0.0),
            "release_baton_contract": raw_checks.get("release_baton_contract_aligned", 0.0),
            "release_baton_complete": raw_checks.get("release_baton_migrated", 0.0),
            "release_attestation_identity": raw_checks.get("release_attestation_identity_aligned", 0.0),
            "release_attestation_delivery": raw_checks.get("release_attestation_delivery_aligned", 0.0),
            "release_attestation_contract": raw_checks.get("release_attestation_contract_aligned", 0.0),
            "release_attestation_complete": raw_checks.get("release_attestation_migrated", 0.0),
            "release_attestation_renderer_identity": raw_checks.get("release_attestation_renderer_identity_aligned", 0.0),
            "release_attestation_renderer_delivery": raw_checks.get("release_attestation_renderer_delivery_aligned", 0.0),
            "release_attestation_renderer_contract": raw_checks.get("release_attestation_renderer_contract_aligned", 0.0),
            "release_attestation_renderer_complete": raw_checks.get("release_attestation_renderer_migrated", 0.0),
            "delivery_stages": stage_group_ratio(first_report, DELIVERY_STAGES),
        }
        observability_objective_checks = {
            "observability_checks": checks_ratio(OBSERVABILITY_CHECKS, raw_checks),
            "delivery_contract_operating": raw_checks.get("delivery_contract_operating_aligned", 0.0),
            "delivery_contract_signal": raw_checks.get("delivery_contract_signal_aligned", 0.0),
            "delivery_contract_network": raw_checks.get("delivery_contract_network_aligned", 0.0),
            "observability_handoff_identity": raw_checks.get("observability_handoff_identity_aligned", 0.0),
            "observability_handoff_signal": raw_checks.get("observability_handoff_signal_aligned", 0.0),
            "observability_handoff_alerting": raw_checks.get("observability_handoff_alerting_aligned", 0.0),
            "observability_handoff_complete": raw_checks.get("observability_handoff_migrated", 0.0),
            "analysis_handoff_identity": raw_checks.get("analysis_handoff_identity_aligned", 0.0),
            "analysis_handoff_analysis": raw_checks.get("analysis_handoff_analysis_aligned", 0.0),
            "analysis_handoff_contract": raw_checks.get("analysis_handoff_contract_aligned", 0.0),
            "analysis_handoff_complete": raw_checks.get("analysis_handoff_migrated", 0.0),
            "analysis_handoff_renderer_identity": raw_checks.get("analysis_handoff_renderer_identity_aligned", 0.0),
            "analysis_handoff_renderer_analysis": raw_checks.get("analysis_handoff_renderer_analysis_aligned", 0.0),
            "analysis_handoff_renderer_contract": raw_checks.get("analysis_handoff_renderer_contract_aligned", 0.0),
            "analysis_handoff_renderer_complete": raw_checks.get("analysis_handoff_renderer_migrated", 0.0),
            "alert_renderer_core": raw_checks.get("alert_renderer_core_aligned", 0.0),
            "alert_renderer_burn_rate": raw_checks.get("alert_renderer_burn_rate_aligned", 0.0),
            "alert_renderer_contract": raw_checks.get("alert_renderer_contract_aligned", 0.0),
            "alert_renderer_complete": raw_checks.get("alert_renderer_migrated", 0.0),
            "observability_stages": stage_group_ratio(second_report, OBSERVABILITY_STAGES),
            "derived_artifacts": bool_ratio(
                [
                    stable_checks.get("resilience_gate_tracks_second_commit", False),
                    stable_checks.get("alert_policy_tracks_second_commit", False),
                    stable_checks.get("analysis_report_tracks_second_commit", False),
                ]
            ),
        }
        traffic_objective_checks = {
            "traffic_checks": checks_ratio(TRAFFIC_CHECKS, raw_checks),
            "traffic_intent_core": raw_checks.get("traffic_intent_core_aligned", 0.0),
            "traffic_intent_progressive": raw_checks.get("traffic_intent_progressive_aligned", 0.0),
            "traffic_intent_complete": raw_checks.get("traffic_intent_migrated", 0.0),
            "mesh_intent_core": raw_checks.get("mesh_intent_core_aligned", 0.0),
            "mesh_intent_subsets": raw_checks.get("mesh_intent_subsets_aligned", 0.0),
            "mesh_intent_complete": raw_checks.get("mesh_intent_migrated", 0.0),
            "route_contract_identity": raw_checks.get("route_contract_identity_aligned", 0.0),
            "route_contract_route": raw_checks.get("route_contract_route_aligned", 0.0),
            "route_contract_contract": raw_checks.get("route_contract_contract_aligned", 0.0),
            "route_contract_complete": raw_checks.get("route_contract_migrated", 0.0),
            "workload_intent_identity": raw_checks.get("workload_intent_identity_aligned", 0.0),
            "workload_intent_runtime": raw_checks.get("workload_intent_runtime_aligned", 0.0),
            "workload_intent_contract": raw_checks.get("workload_intent_contract_aligned", 0.0),
            "workload_intent_complete": raw_checks.get("workload_intent_migrated", 0.0),
            "telemetry_handoff_service": raw_checks.get("telemetry_handoff_service_aligned", 0.0),
            "telemetry_handoff_signal": raw_checks.get("telemetry_handoff_signal_aligned", 0.0),
            "telemetry_handoff_route": raw_checks.get("telemetry_handoff_route_aligned", 0.0),
            "telemetry_handoff_complete": raw_checks.get("telemetry_handoff_manifest_migrated", 0.0),
            "mesh_renderer_route": raw_checks.get("mesh_renderer_route_aligned", 0.0),
            "mesh_renderer_subsets": raw_checks.get("mesh_renderer_subsets_aligned", 0.0),
            "mesh_renderer_complete": raw_checks.get("mesh_renderer_migrated", 0.0),
            "telemetry_renderer_core": raw_checks.get("telemetry_renderer_core_aligned", 0.0),
            "telemetry_renderer_propagation": raw_checks.get("telemetry_renderer_propagation_aligned", 0.0),
            "traffic_stages": stage_group_ratio(second_report, TRAFFIC_STAGES),
            "live_state": bool_ratio(
                [
                    stable_checks.get("live_route_converged", False),
                    stable_checks.get("live_mesh_converged", False),
                    stable_checks.get("live_telemetry_converged", False),
                    stable_checks.get("telemetry_handoff_tracks_second_commit", False),
                ]
            ),
        }

        first_rollout_ok = rollout_complete(first_report)
        second_rollout_ok = rollout_complete(second_report)

        release_core_score = (
            raw_checks["bootstrap_idempotent"]
            + checks_ratio(RELEASE_CHECKS, raw_checks)
            + bool_ratio(
                [
                    raw_checks.get("release_contract_manifest_identity_aligned", 0.0) == 1.0,
                    raw_checks.get("release_contract_manifest_delivery_aligned", 0.0) == 1.0,
                    raw_checks.get("release_contract_manifest_runtime_aligned", 0.0) == 1.0,
                    raw_checks.get("release_contract_manifest_migrated", 0.0) == 1.0,
                ]
            )
            + bool_ratio(
                [
                    raw_checks.get("release_bundle_core_aligned", 0.0) == 1.0,
                    raw_checks.get("release_bundle_handoff_aligned", 0.0) == 1.0,
                    raw_checks.get("release_bundle_contract_aligned", 0.0) == 1.0,
                ]
            )
            + stage_group_ratio(first_report, DELIVERY_STAGES)
        ) / 5
        release_handoff_score = (
            raw_checks.get("release_baton_identity_aligned", 0.0)
            + raw_checks.get("release_baton_delivery_aligned", 0.0)
            + raw_checks.get("release_baton_contract_aligned", 0.0)
            + raw_checks.get("release_baton_migrated", 0.0)
        ) / 4
        release_attestation_score = (
            raw_checks.get("release_attestation_identity_aligned", 0.0)
            + raw_checks.get("release_attestation_delivery_aligned", 0.0)
            + raw_checks.get("release_attestation_contract_aligned", 0.0)
            + raw_checks.get("release_attestation_migrated", 0.0)
            + raw_checks.get("release_attestation_renderer_identity_aligned", 0.0)
            + raw_checks.get("release_attestation_renderer_delivery_aligned", 0.0)
            + raw_checks.get("release_attestation_renderer_contract_aligned", 0.0)
            + raw_checks.get("release_attestation_renderer_migrated", 0.0)
        ) / 8

        observability_core_score = (
            checks_ratio(OBSERVABILITY_CHECKS, raw_checks)
            + bool_ratio(
                [
                    raw_checks.get("delivery_contract_operating_aligned", 0.0) == 1.0,
                    raw_checks.get("delivery_contract_signal_aligned", 0.0) == 1.0,
                    raw_checks.get("delivery_contract_network_aligned", 0.0) == 1.0,
                ]
            )
            + bool_ratio(
                [
                    raw_checks.get("alert_renderer_core_aligned", 0.0) == 1.0,
                    raw_checks.get("alert_renderer_burn_rate_aligned", 0.0) == 1.0,
                    raw_checks.get("alert_renderer_contract_aligned", 0.0) == 1.0,
                    raw_checks.get("alert_renderer_migrated", 0.0) == 1.0,
                ]
            )
            + stage_group_ratio(second_report, OBSERVABILITY_STAGES)
            + bool_ratio(
                [
                    stable_checks.get("resilience_gate_tracks_second_commit", False),
                    stable_checks.get("alert_policy_tracks_second_commit", False),
                    stable_checks.get("analysis_report_tracks_second_commit", False),
                ]
            )
        ) / 5
        observability_handoff_score = (
            raw_checks.get("observability_handoff_identity_aligned", 0.0)
            + raw_checks.get("observability_handoff_signal_aligned", 0.0)
            + raw_checks.get("observability_handoff_alerting_aligned", 0.0)
            + raw_checks.get("observability_handoff_migrated", 0.0)
        ) / 4
        analysis_handoff_score = (
            raw_checks.get("analysis_handoff_identity_aligned", 0.0)
            + raw_checks.get("analysis_handoff_analysis_aligned", 0.0)
            + raw_checks.get("analysis_handoff_contract_aligned", 0.0)
            + raw_checks.get("analysis_handoff_migrated", 0.0)
            + raw_checks.get("analysis_handoff_renderer_identity_aligned", 0.0)
            + raw_checks.get("analysis_handoff_renderer_analysis_aligned", 0.0)
            + raw_checks.get("analysis_handoff_renderer_contract_aligned", 0.0)
            + raw_checks.get("analysis_handoff_renderer_migrated", 0.0)
        ) / 8

        traffic_core_score = (
            checks_ratio(TRAFFIC_CHECKS, raw_checks)
            + bool_ratio(
                [
                    raw_checks.get("telemetry_handoff_service_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_signal_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_route_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_manifest_migrated", 0.0) == 1.0,
                ]
            )
            + bool_ratio(
                [
                    raw_checks.get("mesh_renderer_route_aligned", 0.0) == 1.0,
                    raw_checks.get("mesh_renderer_subsets_aligned", 0.0) == 1.0,
                    raw_checks.get("mesh_renderer_migrated", 0.0) == 1.0,
                ]
            )
            + bool_ratio(
                [
                    raw_checks.get("telemetry_renderer_core_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_renderer_propagation_aligned", 0.0) == 1.0,
                ]
            )
            + stage_group_ratio(second_report, TRAFFIC_STAGES)
            + bool_ratio(
                [
                    stable_checks.get("live_route_converged", False),
                    stable_checks.get("live_mesh_converged", False),
                    stable_checks.get("live_telemetry_converged", False),
                    stable_checks.get("telemetry_handoff_tracks_second_commit", False),
                ]
            )
        ) / 6
        traffic_handoff_score = (
            raw_checks.get("traffic_intent_core_aligned", 0.0)
            + raw_checks.get("traffic_intent_progressive_aligned", 0.0)
            + raw_checks.get("traffic_intent_migrated", 0.0)
            + raw_checks.get("mesh_intent_core_aligned", 0.0)
            + raw_checks.get("mesh_intent_subsets_aligned", 0.0)
            + raw_checks.get("mesh_intent_migrated", 0.0)
        ) / 6
        route_workload_score = (
            raw_checks.get("route_contract_identity_aligned", 0.0)
            + raw_checks.get("route_contract_route_aligned", 0.0)
            + raw_checks.get("route_contract_contract_aligned", 0.0)
            + raw_checks.get("route_contract_migrated", 0.0)
            + raw_checks.get("workload_intent_identity_aligned", 0.0)
            + raw_checks.get("workload_intent_runtime_aligned", 0.0)
            + raw_checks.get("workload_intent_contract_aligned", 0.0)
            + raw_checks.get("workload_intent_migrated", 0.0)
        ) / 8

        first_rollout_base_score = (
            stage_ratio(first_report)
            + bool_ratio(
                [
                    raw_checks.get("release_bundle_core_aligned", 0.0) == 1.0,
                    raw_checks.get("release_bundle_handoff_aligned", 0.0) == 1.0,
                    raw_checks.get("release_bundle_contract_aligned", 0.0) == 1.0,
                ]
            )
            + bool_ratio(
                [
                    raw_checks.get("release_contract_manifest_identity_aligned", 0.0) == 1.0,
                    raw_checks.get("release_contract_manifest_delivery_aligned", 0.0) == 1.0,
                    raw_checks.get("release_contract_manifest_runtime_aligned", 0.0) == 1.0,
                    raw_checks.get("release_contract_manifest_migrated", 0.0) == 1.0,
                ]
            )
            + raw_checks.get("delivery_contract_operating_aligned", 0.0)
        ) / 4

        second_rollout_base_score = (
            (1.0 if second_rollout_ok else stage_ratio(second_report))
            + raw_checks["health_api_ready"]
            + stable_ratio
            + bool_ratio(
                [
                    raw_checks.get("delivery_contract_signal_aligned", 0.0) == 1.0,
                    raw_checks.get("delivery_contract_network_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_service_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_signal_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_route_aligned", 0.0) == 1.0,
                    raw_checks.get("telemetry_handoff_manifest_migrated", 0.0) == 1.0,
                    raw_checks.get("mesh_renderer_route_aligned", 0.0) == 1.0,
                    raw_checks.get("mesh_renderer_subsets_aligned", 0.0) == 1.0,
                    raw_checks.get("mesh_renderer_migrated", 0.0) == 1.0,
                    raw_checks.get("telemetry_renderer_propagation_aligned", 0.0) == 1.0,
                ]
            )
        ) / 4

        objective_scores["release_contract_repaired"] = (
            (
                0.2 * release_core_score
                + 0.25 * release_handoff_score
                + 0.55 * release_attestation_score
            )
            if runtime_ok
            else 0.0
        )
        objective_scores["observability_and_resilience_repaired"] = (
            (
                0.2 * observability_core_score
                + 0.25 * observability_handoff_score
                + 0.55 * analysis_handoff_score
            )
            if runtime_ok
            else 0.0
        )
        objective_scores["traffic_mesh_telemetry_repaired"] = (
            (
                0.2 * traffic_core_score
                + 0.25 * traffic_handoff_score
                + 0.55 * route_workload_score
            )
            if runtime_ok
            else 0.0
        )
        objective_scores["first_failover_rollout"] = (
            (
                0.2 * first_rollout_base_score
                + 0.25 * release_handoff_score
                + 0.55 * release_attestation_score
            )
            if runtime_ok
            else 0.0
        )
        objective_scores["second_failover_convergence"] = (
            (
                0.15 * second_rollout_base_score
                + 0.35 * ((observability_handoff_score + analysis_handoff_score) / 2)
                + 0.5 * ((traffic_handoff_score + route_workload_score) / 2)
            )
            if runtime_ok
            else 0.0
        )

        details["objective_group_scores"] = {
            "release_core": release_core_score,
            "release_handoff": release_handoff_score,
            "release_attestation": release_attestation_score,
            "observability_core": observability_core_score,
            "observability_handoff": observability_handoff_score,
            "analysis_handoff": analysis_handoff_score,
            "traffic_core": traffic_core_score,
            "traffic_handoff": traffic_handoff_score,
            "route_workload": route_workload_score,
            "first_rollout_base": first_rollout_base_score,
            "second_rollout_base": second_rollout_base_score,
        }

        details["objective_checks"] = {
            "release_contract_repaired": release_objective_checks,
            "observability_and_resilience_repaired": observability_objective_checks,
            "traffic_mesh_telemetry_repaired": traffic_objective_checks,
            "first_failover_rollout": {
                "rollout_complete": first_rollout_ok,
                "stage_ratio": stage_ratio(first_report),
                "release_bundle_core_aligned": raw_checks.get("release_bundle_core_aligned", 0.0),
                "release_bundle_handoff_aligned": raw_checks.get("release_bundle_handoff_aligned", 0.0),
                "release_bundle_contract_aligned": raw_checks.get("release_bundle_contract_aligned", 0.0),
                "release_contract_manifest_identity_aligned": raw_checks.get("release_contract_manifest_identity_aligned", 0.0),
                "release_contract_manifest_delivery_aligned": raw_checks.get("release_contract_manifest_delivery_aligned", 0.0),
                "release_contract_manifest_runtime_aligned": raw_checks.get("release_contract_manifest_runtime_aligned", 0.0),
                "release_contract_manifest_migrated": raw_checks.get("release_contract_manifest_migrated", 0.0),
                "release_baton_identity_aligned": raw_checks.get("release_baton_identity_aligned", 0.0),
                "release_baton_delivery_aligned": raw_checks.get("release_baton_delivery_aligned", 0.0),
                "release_baton_contract_aligned": raw_checks.get("release_baton_contract_aligned", 0.0),
                "release_baton_migrated": raw_checks.get("release_baton_migrated", 0.0),
                "release_attestation_identity_aligned": raw_checks.get("release_attestation_identity_aligned", 0.0),
                "release_attestation_delivery_aligned": raw_checks.get("release_attestation_delivery_aligned", 0.0),
                "release_attestation_contract_aligned": raw_checks.get("release_attestation_contract_aligned", 0.0),
                "release_attestation_migrated": raw_checks.get("release_attestation_migrated", 0.0),
                "release_attestation_renderer_identity_aligned": raw_checks.get("release_attestation_renderer_identity_aligned", 0.0),
                "release_attestation_renderer_delivery_aligned": raw_checks.get("release_attestation_renderer_delivery_aligned", 0.0),
                "release_attestation_renderer_contract_aligned": raw_checks.get("release_attestation_renderer_contract_aligned", 0.0),
                "release_attestation_renderer_migrated": raw_checks.get("release_attestation_renderer_migrated", 0.0),
                "delivery_contract_operating_aligned": raw_checks.get("delivery_contract_operating_aligned", 0.0),
            },
            "second_failover_convergence": {
                "health_api_ready": raw_checks["health_api_ready"],
                "rollout_complete": 1.0 if second_rollout_ok else 0.0,
                "second_rollout_stage_ratio": stage_ratio(second_report),
                "stable_end_state": stable_ratio,
                "delivery_contract_signal_aligned": raw_checks.get("delivery_contract_signal_aligned", 0.0),
                "delivery_contract_network_aligned": raw_checks.get("delivery_contract_network_aligned", 0.0),
                "observability_handoff_identity_aligned": raw_checks.get("observability_handoff_identity_aligned", 0.0),
                "observability_handoff_signal_aligned": raw_checks.get("observability_handoff_signal_aligned", 0.0),
                "observability_handoff_alerting_aligned": raw_checks.get("observability_handoff_alerting_aligned", 0.0),
                "observability_handoff_migrated": raw_checks.get("observability_handoff_migrated", 0.0),
                "analysis_handoff_identity_aligned": raw_checks.get("analysis_handoff_identity_aligned", 0.0),
                "analysis_handoff_analysis_aligned": raw_checks.get("analysis_handoff_analysis_aligned", 0.0),
                "analysis_handoff_contract_aligned": raw_checks.get("analysis_handoff_contract_aligned", 0.0),
                "analysis_handoff_migrated": raw_checks.get("analysis_handoff_migrated", 0.0),
                "analysis_handoff_renderer_identity_aligned": raw_checks.get("analysis_handoff_renderer_identity_aligned", 0.0),
                "analysis_handoff_renderer_analysis_aligned": raw_checks.get("analysis_handoff_renderer_analysis_aligned", 0.0),
                "analysis_handoff_renderer_contract_aligned": raw_checks.get("analysis_handoff_renderer_contract_aligned", 0.0),
                "analysis_handoff_renderer_migrated": raw_checks.get("analysis_handoff_renderer_migrated", 0.0),
                "traffic_intent_core_aligned": raw_checks.get("traffic_intent_core_aligned", 0.0),
                "traffic_intent_progressive_aligned": raw_checks.get("traffic_intent_progressive_aligned", 0.0),
                "traffic_intent_migrated": raw_checks.get("traffic_intent_migrated", 0.0),
                "mesh_intent_core_aligned": raw_checks.get("mesh_intent_core_aligned", 0.0),
                "mesh_intent_subsets_aligned": raw_checks.get("mesh_intent_subsets_aligned", 0.0),
                "mesh_intent_migrated": raw_checks.get("mesh_intent_migrated", 0.0),
                "route_contract_identity_aligned": raw_checks.get("route_contract_identity_aligned", 0.0),
                "route_contract_route_aligned": raw_checks.get("route_contract_route_aligned", 0.0),
                "route_contract_contract_aligned": raw_checks.get("route_contract_contract_aligned", 0.0),
                "route_contract_migrated": raw_checks.get("route_contract_migrated", 0.0),
                "workload_intent_identity_aligned": raw_checks.get("workload_intent_identity_aligned", 0.0),
                "workload_intent_runtime_aligned": raw_checks.get("workload_intent_runtime_aligned", 0.0),
                "workload_intent_contract_aligned": raw_checks.get("workload_intent_contract_aligned", 0.0),
                "workload_intent_migrated": raw_checks.get("workload_intent_migrated", 0.0),
                "telemetry_handoff_service_aligned": raw_checks.get("telemetry_handoff_service_aligned", 0.0),
                "telemetry_handoff_signal_aligned": raw_checks.get("telemetry_handoff_signal_aligned", 0.0),
                "telemetry_handoff_route_aligned": raw_checks.get("telemetry_handoff_route_aligned", 0.0),
                "telemetry_handoff_manifest_migrated": raw_checks.get("telemetry_handoff_manifest_migrated", 0.0),
                "mesh_renderer_route_aligned": raw_checks.get("mesh_renderer_route_aligned", 0.0),
                "mesh_renderer_subsets_aligned": raw_checks.get("mesh_renderer_subsets_aligned", 0.0),
                "mesh_renderer_migrated": raw_checks.get("mesh_renderer_migrated", 0.0),
                "telemetry_renderer_propagation_aligned": raw_checks.get("telemetry_renderer_propagation_aligned", 0.0),
            },
        }
        details["raw_checks"] = raw_checks

    except Exception as exc:  # pragma: no cover - verifier fallback
        details["fatal_error"] = str(exc)
    finally:
        stop_server(server)

    score = 0.0
    for key, weight in WEIGHTS.items():
        score += weight * objective_scores[key]
    write_outputs(round(score, 3), objective_scores, details)


if __name__ == "__main__":
    main()
