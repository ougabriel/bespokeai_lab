from __future__ import annotations

from app.config import Settings
from app.fs import dump_yaml, load_yaml


def apply_secret_drift(settings: Settings) -> None:
    source_secret = load_yaml(
        settings.lab_root / "ops" / "source-of-truth" / "registry-robot.yaml"
    )
    dump_yaml(
        settings.lab_root / "cluster" / "live" / "secrets" / "registry-robot.yaml",
        source_secret,
    )


def _expected_secret(settings: Settings) -> dict[str, object]:
    broker = load_yaml(settings.lab_root / "ops" / "identity" / "registry-broker.yaml")["broker"]
    active_profile = broker["active_profile"]
    profile = broker["profiles"][active_profile]
    return {
        "name": broker["secret_name"],
        "username": profile["username"],
        "token": "-".join(profile["token_parts"]),
        "scopes": profile["scopes"],
    }


def push_image(
    settings: Settings,
    artifact_repository: str,
    commit_sha: str,
) -> dict[str, object]:
    registry_host = artifact_repository.split("/", 1)[0]
    dns_hosts = load_yaml(settings.lab_root / "infra" / "dns.yaml")["hosts"]
    if registry_host != settings.registry_host or not dns_hosts.get(registry_host):
        return {
            "status": "failed",
            "message": f"The registry host {registry_host!r} is not resolvable from the release lane.",
        }

    live_secret = load_yaml(
        settings.lab_root / "cluster" / "live" / "secrets" / "registry-robot.yaml"
    )
    expected_secret = _expected_secret(settings)
    if (
        live_secret.get("username") != expected_secret.get("username")
        or live_secret.get("token") != expected_secret.get("token")
        or set(live_secret.get("scopes", [])) != set(expected_secret.get("scopes", []))
    ):
        return {
            "status": "failed",
            "message": "The registry robot credentials still do not match the expected production values.",
        }

    catalog_path = settings.lab_root / "registry" / "catalog.yaml"
    catalog = load_yaml(catalog_path)
    tags = catalog.setdefault("images", {}).setdefault(artifact_repository, [])
    if commit_sha not in tags:
        tags.append(commit_sha)
    dump_yaml(catalog_path, catalog)

    return {
        "status": "success",
        "message": f"Pushed {artifact_repository}:{commit_sha} to the internal registry.",
    }
