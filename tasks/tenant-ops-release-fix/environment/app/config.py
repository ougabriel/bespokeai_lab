from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "runtime.yaml"


@dataclass(frozen=True)
class Settings:
    database_path: str
    job_runs_path: str
    api_host: str
    api_port: int


def load_settings(config_path: str | None = None) -> Settings:
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with target_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    return Settings(
        database_path=raw_config["database"]["path"],
        job_runs_path=raw_config["inputs"]["job_runs_path"],
        api_host=raw_config["api"]["host"],
        api_port=int(raw_config["api"]["port"]),
    )
