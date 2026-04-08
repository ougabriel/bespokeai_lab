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
    telemetry = load_yaml(overlay / "telemetry-policy.yaml")["telemetry"]
    traffic = load_yaml(overlay / "traffic-policy.yaml")["traffic"]

    payload = {
      "service": telemetry["service"],
      "namespace": telemetry["namespace"],
      "provider": "migration-otel",
      "metric_source": telemetry["metric_source"],
      "gateway_class": traffic["gateway_class"],
      "route_prefix": traffic["route_prefix"],
      "lane": telemetry["lane"],
      "trace_sampling_percent": 1,
      "propagation": {
        "header": "x-release-track",
        "value": telemetry["propagation_value"],
      },
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
