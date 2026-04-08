from __future__ import annotations

import shutil

from app.config import load_settings
from app.fs import dump_json, file_count


def reset_lab() -> dict[str, object]:
    settings = load_settings()
    if settings.lab_root.exists():
        shutil.rmtree(settings.lab_root)

    shutil.copytree(settings.lab_seed_root, settings.lab_root)

    artifacts_dir = settings.lab_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    dump_json(artifacts_dir / "rollout_history.json", [])

    return {
        "status": "ok",
        "service": settings.service_name,
        "lab_root": str(settings.lab_root),
        "seed_file_count": file_count(settings.lab_root),
    }
