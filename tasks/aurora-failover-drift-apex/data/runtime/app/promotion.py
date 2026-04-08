from __future__ import annotations

from app.config import Settings
from app.contract import release_contract
from app.fs import dump_json, load_yaml


def promote_release(
    settings: Settings,
    commit_sha: str,
) -> dict[str, object]:
    contract = release_contract(settings)
    promotion = load_yaml(
        settings.lab_root
        / contract["write_back_target"]
        / contract["prod_overlay"]
        / "promotion-policy.yaml"
    )["promotion"]

    if promotion.get("target_branch") != contract["write_back_branch"]:
        return {
            "status": "failed",
            "message": "The failover promotion policy is still targeting the old migration branch instead of the prod mainline.",
        }

    if promotion.get("target_overlay") != contract["prod_overlay"]:
        return {
            "status": "failed",
            "message": "The failover promotion policy still points at the legacy overlay instead of the prod overlay.",
        }

    if promotion.get("channel") != contract["promotion_channel"]:
        return {
            "status": "failed",
            "message": "The failover promotion policy is still wired to the wrong release channel.",
        }

    if promotion.get("analysis_template") != contract["analysis_template"]:
        return {
            "status": "failed",
            "message": "The promotion policy still references the wrong canary analysis template.",
        }

    if promotion.get("strategy") != contract["promotion_mode"]:
        return {
            "status": "failed",
            "message": "The promotion policy still uses the migration-era strategy instead of the canary path.",
        }

    if promotion.get("freeze") is not False:
        return {
            "status": "failed",
            "message": "The promotion policy is still frozen, so the failover lane never hands off to prod.",
        }

    dump_json(
        settings.lab_root / "artifacts" / "promotion_intent.json",
        {
            "analysis_template": contract["analysis_template"],
            "channel": contract["promotion_channel"],
            "commit_sha": commit_sha,
            "service": settings.service_name,
            "strategy": contract["promotion_mode"],
            "target_overlay": contract["prod_overlay"],
        },
    )

    return {
        "status": "success",
        "message": f"Promoted {settings.service_name} commit {commit_sha} into the prod canary lane.",
    }
