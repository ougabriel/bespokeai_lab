from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_json, load_yaml


def verify_resilience(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    promotion_intent = load_json(settings.lab_root / "artifacts" / "promotion_intent.json", {})

    if (
        promotion_intent.get("commit_sha") != commit_sha
        or promotion_intent.get("target_overlay") != contract["prod_overlay"]
        or promotion_intent.get("channel") != contract["promotion_channel"]
    ):
        return {
            "status": "failed",
            "message": "The prod resilience policy never received a valid promotion handoff.",
        }

    autoscaling_path = gitops_root / contract["prod_overlay"] / "autoscaling-policy.yaml"
    availability_path = gitops_root / contract["prod_overlay"] / "availability-budget.yaml"
    if not autoscaling_path.exists() or not availability_path.exists():
        return {
            "status": "failed",
            "message": "The prod resilience resources are incomplete for the active lane.",
        }

    autoscaling = load_yaml(autoscaling_path)["autoscaling"]
    if autoscaling.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The autoscaling policy still points at the wrong prod service.",
        }

    if autoscaling.get("min_replicas") != contract["min_replicas"]:
        return {
            "status": "failed",
            "message": "The autoscaling minimum replica floor is still using the migration setting.",
        }

    if autoscaling.get("max_replicas") != contract["max_replicas"]:
        return {
            "status": "failed",
            "message": "The autoscaling max replica ceiling is still using the migration setting.",
        }

    if autoscaling.get("cpu_target_utilization") != contract["cpu_target_utilization"]:
        return {
            "status": "failed",
            "message": "The autoscaling CPU target still uses the wrong prod threshold.",
        }

    if autoscaling.get("memory_target_utilization") != contract["memory_target_utilization"]:
        return {
            "status": "failed",
            "message": "The autoscaling memory target still uses the wrong prod threshold.",
        }

    availability_budget = load_yaml(availability_path)["budget"]
    if availability_budget.get("service") != contract["traffic_service"]:
        return {
            "status": "failed",
            "message": "The availability budget still points at the wrong prod service.",
        }

    if availability_budget.get("lane") != contract["lane_name"]:
        return {
            "status": "failed",
            "message": "The availability budget is still bound to the wrong release lane.",
        }

    if availability_budget.get("min_available") != contract["min_available"]:
        return {
            "status": "failed",
            "message": "The availability budget is still using the migration-era minimum availability.",
        }

    dump_json(
        settings.lab_root / "artifacts" / "resilience_gate.json",
        {
            "commit_sha": commit_sha,
            "lane": contract["lane_name"],
            "service": settings.service_name,
            "status": "Ready",
        },
    )

    return {
        "status": "success",
        "message": f"Validated autoscaling and availability policy for {settings.service_name} commit {commit_sha}.",
    }
