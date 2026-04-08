from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_yaml, load_yaml


def update_gitops_manifests(
    settings: Settings,
    commit_sha: str,
) -> dict[str, object]:
    contract = release_contract(settings)
    updater_config = load_yaml(settings.lab_root / "controllers" / "image-updater.yaml")["updater"]
    if updater_config.get("tracked_service") != contract["tracked_service"]:
        return {
            "status": "failed",
            "message": "The image updater is no longer tracking the prod service.",
        }

    if updater_config.get("auth_secret") != contract["registry_auth_secret"]:
        return {
            "status": "failed",
            "message": "The image updater is pointed at the wrong registry credential reference.",
        }

    if updater_config.get("write_back_target") != contract["write_back_target"]:
        return {
            "status": "failed",
            "message": "The image updater is writing back to the wrong repository target.",
        }

    if updater_config.get("write_back_branch") != contract["write_back_branch"]:
        return {
            "status": "failed",
            "message": "The image updater is still trying to land prod changes on the old migration branch.",
        }

    expected_manifest_path = f"{contract['prod_overlay']}/values.yaml"
    if updater_config.get("manifest_path") != expected_manifest_path:
        return {
            "status": "failed",
            "message": "The image updater is still targeting the old manifest path from before the repo reorg.",
        }

    values_path = (
        settings.lab_root
        / contract["write_back_target"]
        / contract["prod_overlay"]
        / "values.yaml"
    )
    values = load_yaml(values_path)
    values["image"]["tag"] = commit_sha
    dump_yaml(values_path, values)

    return {
        "status": "success",
        "message": f"Updated the GitOps values file to tag {commit_sha}.",
    }
