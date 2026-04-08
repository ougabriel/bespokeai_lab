from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_yaml, load_json, load_yaml


def _release_channel(commit_sha: str) -> str:
    return "failover" if "failover" in commit_sha else "stable"


def sync_application(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    app_manifest = load_yaml(gitops_root / "apps" / settings.service_name / "application.yaml")["application"]
    if app_manifest.get("project") != contract["prod_project"]:
        return {
            "status": "failed",
            "message": "The application is still attached to the old shared Argo project after the migration.",
        }

    if app_manifest.get("sync_policy") != contract["sync_policy"]:
        return {
            "status": "failed",
            "message": "The application is still set to manual sync, so prod never reconciles itself.",
        }

    if app_manifest.get("source_path") != contract["prod_overlay"]:
        return {
            "status": "failed",
            "message": "The application source path is still pinned to the pre-cutover layout instead of the prod overlay.",
        }

    promotion_intent = load_json(settings.lab_root / "artifacts" / "promotion_intent.json", {})
    if (
        promotion_intent.get("commit_sha") != commit_sha
        or promotion_intent.get("target_overlay") != contract["prod_overlay"]
        or promotion_intent.get("channel") != contract["promotion_channel"]
        or promotion_intent.get("analysis_template") != contract["analysis_template"]
    ):
        return {
            "status": "failed",
            "message": "The failover promotion handoff never lined up with the prod overlay Argo is supposed to reconcile.",
        }

    source_path = gitops_root / contract["prod_overlay"]
    values_path = source_path / "values.yaml"
    if not values_path.exists():
        return {
            "status": "failed",
            "message": f"The application source path {app_manifest['source_path']!r} does not resolve to a release overlay.",
        }

    values = load_yaml(values_path)
    repository = values["image"]["repository"]
    tag = values["image"]["tag"]

    catalog = load_yaml(settings.lab_root / "registry" / "catalog.yaml")
    available_tags = catalog.get("images", {}).get(repository, [])
    if tag not in available_tags:
        return {
            "status": "failed",
            "message": f"The desired image {repository}:{tag} is not available in the registry catalog.",
        }

    release_gate = load_yaml(source_path / "release-gate.yaml")["gate"]
    channel = _release_channel(tag)
    if channel not in release_gate.get("allowed_channels", []):
        return {
            "status": "failed",
            "message": f"The prod release gate still blocks the {channel} channel.",
        }

    if release_gate.get("promotion_mode") != contract["promotion_mode"]:
        return {
            "status": "failed",
            "message": "The prod release gate is still pinned to the migration-era promotion mode instead of the canary failover path.",
        }

    deployment_path = (
        settings.lab_root / "cluster" / "live" / "deployments" / f"{settings.service_name}.yaml"
    )
    deployment = load_yaml(deployment_path)
    deployment["deployment"].update(
        {
            "image": f"{repository}:{tag}",
            "status": "Healthy",
            "sync_status": "Synced",
            "live_commit": tag,
            "source_path": app_manifest["source_path"],
        }
    )
    dump_yaml(deployment_path, deployment)

    return {
        "status": "success",
        "message": f"Synced {settings.service_name} from {app_manifest['source_path']}.",
    }
