from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_yaml
from app.tooling import run_json_tool


def run_ci(settings: Settings, commit_sha: str) -> tuple[dict[str, object], str | None]:
    runner_path = settings.lab_root / "app-repo" / "ci" / "runner.yaml"
    plan_path = settings.lab_root / "app-repo" / "ci" / "release-plan.yaml"
    release_path = settings.lab_root / "app-repo" / "services" / settings.service_name / "release.yaml"
    release_contract_path = settings.lab_root / "app-repo" / "services" / settings.service_name / "release-contract.yaml"
    release_baton_path = settings.lab_root / "app-repo" / "services" / settings.service_name / "release-baton.yaml"
    release_attestation_path = settings.lab_root / "app-repo" / "services" / settings.service_name / "release-attestation.yaml"
    release_witness_path = settings.lab_root / "app-repo" / "services" / settings.service_name / "release-witness.yaml"

    runner_config = load_yaml(runner_path)["runner"]
    release_plan = load_yaml(plan_path)["release_plan"]
    release_config = load_yaml(release_path)
    contract = release_contract(settings)
    expected_socket = runner_config.get("expected_socket")
    actual_socket = runner_config.get("docker_host")
    if actual_socket != expected_socket:
        return (
            {
                "status": "failed",
                "message": f"Runner is still targeting {actual_socket!r} instead of the local Docker socket.",
            },
            None,
        )

    if (
        runner_config.get("profile") != release_plan.get("required_runner_profile")
        or runner_config.get("profile") != contract.get("required_runner_profile")
    ):
        return (
            {
                "status": "failed",
                "message": "The release lane is still pinned to the old runner profile after the migration.",
            },
            None,
        )

    if (
        release_plan.get("target_branch") != contract.get("target_branch")
        or release_config.get("branch") != contract.get("target_branch")
    ):
        return (
            {
                "status": "failed",
                "message": "The service release metadata is still pointing at the pre-cutover branch mapping.",
            },
            None,
        )

    if release_plan.get("tag_source") != contract.get("tag_source"):
        return (
            {
                "status": "failed",
                "message": "The release lane is still emitting the old migration-era tag source instead of commit-based tags.",
            },
            None,
        )

    expected_repository = contract["image_repository"]
    artifact_repository = release_config["artifact_repository"]
    if (
        release_plan.get("artifact_repository") != expected_repository
        or artifact_repository != expected_repository
    ):
        return (
            {
                "status": "failed",
                "message": "The release lane still advertises the pre-cutover publish target instead of the internal production registry.",
            },
            None,
        )

    if (
        not release_contract_path.exists()
        or not release_baton_path.exists()
        or not release_attestation_path.exists()
        or not release_witness_path.exists()
    ):
        return (
            {
                "status": "failed",
                "message": "The durable release handoff manifests are still missing from the active lane.",
            },
            None,
        )

    release_manifest = load_yaml(release_contract_path)["contract"]
    if (
        release_manifest.get("service") != contract["service"]
        or release_manifest.get("tracked_service") != contract["tracked_service"]
        or release_manifest.get("traffic_service") != contract["traffic_service"]
        or release_manifest.get("lane") != contract["lane_name"]
        or release_manifest.get("target_branch") != contract["target_branch"]
        or release_manifest.get("write_back_branch") != contract["write_back_branch"]
        or release_manifest.get("target_overlay") != contract["prod_overlay"]
        or release_manifest.get("image_repository") != contract["image_repository"]
        or release_manifest.get("health_path") != contract["health_path"]
        or release_manifest.get("contract_label") != contract["contract_label"]
    ):
        return (
            {
                "status": "failed",
                "message": "The release contract manifest is still carrying migration-era lane metadata.",
            },
            None,
        )

    baton = load_yaml(release_baton_path)["baton"]
    if (
        baton.get("service") != contract["service"]
        or baton.get("tracked_service") != contract["tracked_service"]
        or baton.get("lane") != contract["lane_name"]
        or baton.get("write_back_target") != contract["write_back_target"]
        or baton.get("write_back_branch") != contract["write_back_branch"]
        or baton.get("target_overlay") != contract["prod_overlay"]
        or baton.get("contract_label") != contract["contract_label"]
    ):
        return (
            {
                "status": "failed",
                "message": "The release baton still points at the pre-cutover prod lane.",
            },
            None,
        )

    attestation = load_yaml(release_attestation_path)["attestation"]
    if (
        attestation.get("service") != contract["service"]
        or attestation.get("lane") != contract["lane_name"]
        or attestation.get("target_branch") != contract["target_branch"]
        or attestation.get("write_back_target") != contract["write_back_target"]
        or attestation.get("write_back_branch") != contract["write_back_branch"]
        or attestation.get("image_repository") != contract["image_repository"]
        or attestation.get("contract_label") != contract["contract_label"]
    ):
        return (
            {
                "status": "failed",
                "message": "The release attestation is still emitting the wrong prod handoff contract.",
            },
            None,
        )

    witness = load_yaml(release_witness_path)["witness"]
    if (
        witness.get("service") != contract["service"]
        or witness.get("lane") != contract["lane_name"]
        or witness.get("target_overlay") != contract["prod_overlay"]
        or witness.get("live_path") != contract["live_path"]
        or witness.get("gateway_host") != contract["gateway_host"]
        or witness.get("contract_label") != contract["contract_label"]
    ):
        return (
            {
                "status": "failed",
                "message": "The release witness still records the wrong prod route handoff.",
            },
            None,
        )

    if not commit_sha.strip():
        return (
            {
                "status": "failed",
                "message": "A non-empty commit SHA is required for the release simulation.",
            },
            None,
        )

    tool_ok, bundle, tool_error = run_json_tool(
        settings.lab_root / "app-repo" / "ci" / "scripts" / "render_release_bundle.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or bundle is None:
        return (
            {
                "status": "failed",
                "message": tool_error or "The lane bundle renderer failed.",
            },
            None,
        )

    if bundle.get("service") != settings.service_name:
        return (
            {
                "status": "failed",
                "message": "The lane bundle renderer is still targeting the wrong service.",
            },
            None,
        )

    if bundle.get("image_repository") != expected_repository:
        return (
            {
                "status": "failed",
                "message": "The lane bundle renderer is still emitting the old publish target.",
            },
            None,
        )

    if bundle.get("target_branch") != contract["target_branch"] or bundle.get("write_back_branch") != contract["write_back_branch"]:
        return (
            {
                "status": "failed",
                "message": "The lane bundle renderer is still publishing the wrong branch mapping.",
            },
            None,
        )

    if bundle.get("channel") != contract["promotion_channel"] or bundle.get("tag_source") != contract["tag_source"]:
        return (
            {
                "status": "failed",
                "message": "The lane bundle renderer is still using the migration-era channel or tag source.",
            },
            None,
        )

    tool_ok, attestation_payload, attestation_error = run_json_tool(
        settings.lab_root / "app-repo" / "ci" / "scripts" / "render_release_attestation.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or attestation_payload is None:
        return (
            {
                "status": "failed",
                "message": attestation_error or "The release attestation renderer failed.",
            },
            None,
        )

    if (
        attestation_payload.get("service") != contract["service"]
        or attestation_payload.get("lane") != contract["lane_name"]
        or attestation_payload.get("target_branch") != contract["target_branch"]
        or attestation_payload.get("write_back_target") != contract["write_back_target"]
        or attestation_payload.get("write_back_branch") != contract["write_back_branch"]
        or attestation_payload.get("image_repository") != contract["image_repository"]
        or attestation_payload.get("tracked_service") != contract["tracked_service"]
        or attestation_payload.get("contract_label") != contract["contract_label"]
    ):
        return (
            {
                "status": "failed",
                "message": "The release attestation renderer is still publishing the wrong prod contract.",
            },
            None,
        )

    tool_ok, witness_payload, witness_error = run_json_tool(
        settings.lab_root / "app-repo" / "ci" / "scripts" / "render_release_witness.py",
        "--lab-root",
        str(settings.lab_root),
        "--service",
        settings.service_name,
        "--commit-sha",
        commit_sha,
    )
    if not tool_ok or witness_payload is None:
        return (
            {
                "status": "failed",
                "message": witness_error or "The release witness renderer failed.",
            },
            None,
        )

    if (
        witness_payload.get("service") != contract["service"]
        or witness_payload.get("lane") != contract["lane_name"]
        or witness_payload.get("target_overlay") != contract["prod_overlay"]
        or witness_payload.get("live_path") != contract["live_path"]
        or witness_payload.get("gateway_host") != contract["gateway_host"]
        or witness_payload.get("tracked_service") != contract["tracked_service"]
        or witness_payload.get("contract_label") != contract["contract_label"]
    ):
        return (
            {
                "status": "failed",
                "message": "The release witness renderer is still publishing the wrong prod route contract.",
            },
            None,
        )

    dump_json(
        settings.lab_root / "artifacts" / "release_witness.json",
        {
            "commit_sha": commit_sha,
            "lane": contract["lane_name"],
            "target_overlay": contract["prod_overlay"],
            "live_path": contract["live_path"],
            "gateway_host": contract["gateway_host"],
            "status": "Prepared",
        },
    )

    return (
        {
            "status": "success",
            "message": f"Built {settings.service_name} for commit {commit_sha}.",
            "artifact_repository": artifact_repository,
            "bundle": bundle,
            "witness": witness_payload,
        },
        artifact_repository,
    )
