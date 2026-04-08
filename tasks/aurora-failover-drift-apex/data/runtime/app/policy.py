from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_json, load_yaml


def verify_policy(settings: Settings, commit_sha: str) -> dict[str, object]:
    contract = release_contract(settings)
    gitops_root = settings.lab_root / contract["write_back_target"]
    promotion_intent = load_json(settings.lab_root / "artifacts" / "promotion_intent.json", {})
    resilience_gate = load_json(settings.lab_root / "artifacts" / "resilience_gate.json", {})

    if (
        promotion_intent.get("commit_sha") != commit_sha
        or promotion_intent.get("target_overlay") != contract["prod_overlay"]
        or promotion_intent.get("channel") != contract["promotion_channel"]
        or promotion_intent.get("analysis_template") != contract["analysis_template"]
    ):
        return {
            "status": "failed",
            "message": "The prod safety policy never received a valid failover promotion handoff.",
        }

    if (
        resilience_gate.get("commit_sha") != commit_sha
        or resilience_gate.get("lane") != contract["lane_name"]
        or resilience_gate.get("status") != "Ready"
    ):
        return {
            "status": "failed",
            "message": "The prod safety policy never received a valid resilience handoff.",
        }

    window = load_yaml(gitops_root / contract["prod_overlay"] / "rollout-window.yaml")["window"]
    if window.get("lane") != contract["lane_name"]:
        return {
            "status": "failed",
            "message": "The progressive delivery window is still bound to the old release lane.",
        }

    if window.get("freeze") is not False:
        return {
            "status": "failed",
            "message": "The progressive delivery window is still frozen from the migration cutover.",
        }

    if window.get("require_analysis") is not True:
        return {
            "status": "failed",
            "message": "The prod rollout policy is still bypassing the required canary analysis gate.",
        }

    if window.get("hold_minutes") != contract["rollout_hold_minutes"]:
        return {
            "status": "failed",
            "message": "The prod rollout hold window is still set to the wrong duration.",
        }

    if window.get("rollback_on_slo_breach") is not contract["rollback_on_slo_breach"]:
        return {
            "status": "failed",
            "message": "The prod rollback policy is still using the migration-era behavior.",
        }

    if window.get("progressive_steps") != contract["progressive_steps"]:
        return {
            "status": "failed",
            "message": "The progressive delivery steps do not match the active prod lane.",
        }

    dump_json(
        settings.lab_root / "artifacts" / "policy_gate.json",
        {
            "analysis_template": contract["analysis_template"],
            "channel": contract["promotion_channel"],
            "commit_sha": commit_sha,
            "lane": contract["lane_name"],
            "progressive_steps": contract["progressive_steps"],
            "require_analysis": True,
            "service": settings.service_name,
        },
    )

    return {
        "status": "success",
        "message": f"Validated the prod delivery policy for {settings.service_name} commit {commit_sha}.",
    }
