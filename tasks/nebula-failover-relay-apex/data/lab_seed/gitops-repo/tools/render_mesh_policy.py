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
    virtual_service = load_yaml(overlay / "virtual-service.yaml")["virtual_service"]

    payload = {
        "gateway_host": virtual_service.get("gateway_host"),
        "service_host": f"{args.service}.svc.cluster.local",
        "subsets": [
            {"name": "stable", "lane": "release-relay", "track": "stable"},
            {"name": "canary", "lane": "release-relay", "track": "stable"},
        ],
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
