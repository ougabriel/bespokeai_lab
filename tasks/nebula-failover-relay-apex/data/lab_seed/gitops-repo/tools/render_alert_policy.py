#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def load_yaml(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-root", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--commit-sha", required=True)
    args = parser.parse_args()

    lab_root = Path(args.lab_root)
    overlay = lab_root / "gitops-repo" / "services" / args.service / "overlays" / "prod"
    alert_route = load_yaml(overlay / "alert-route.yaml")["alert_route"]

    payload = {
        "service": alert_route.get("service"),
        "receiver": alert_route.get("receiver"),
        "metric_source": "shadow-prometheus",
        "burn_rate": {
            "short_window": "15m",
            "long_window": "1h",
            "max_burn_rate": 6.0,
        },
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
