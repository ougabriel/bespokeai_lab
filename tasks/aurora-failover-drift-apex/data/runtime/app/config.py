from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR.parent / "config" / "runtime.yaml"


@dataclass(frozen=True)
class Settings:
    lab_seed_root: Path
    lab_root: Path
    docs_root: Path
    api_host: str
    api_port: int
    service_name: str
    registry_host: str


def load_settings(config_path: str | None = None) -> Settings:
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with target_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    return Settings(
        lab_seed_root=Path(raw_config["paths"]["lab_seed_root"]),
        lab_root=Path(raw_config["paths"]["lab_root"]),
        docs_root=Path(raw_config["paths"]["docs_root"]),
        api_host=raw_config["api"]["host"],
        api_port=int(raw_config["api"]["port"]),
        service_name=raw_config["release"]["service_name"],
        registry_host=raw_config["release"]["registry_host"],
    )
