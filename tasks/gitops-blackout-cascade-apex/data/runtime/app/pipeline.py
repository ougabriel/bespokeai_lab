from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import load_yaml
from app.tooling import run_json_tool


def run_ci(settings: Settings, commit_sha: str) -> tuple[dict[str, object], str | None]:
    runner_path = settings.lab_root / "app-repo" / "ci" / "runner.yaml"
    plan_path = settings.lab_root / "app-repo" / "ci" / "release-plan.yaml"
    release_path = settings.lab_root / "app-repo" / "services" / settings.service_name / "release.yaml"

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

    return (
        {
            "status": "success",
            "message": f"Built {settings.service_name} for commit {commit_sha}.",
            "artifact_repository": artifact_repository,
            "bundle": bundle,
        },
        artifact_repository,
    )
