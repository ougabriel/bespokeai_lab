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
    release_plan = load_yaml(lab_root / "app-repo" / "ci" / "release-plan.yaml")["release_plan"]
    release = load_yaml(lab_root / "app-repo" / "services" / args.service / "release.yaml")

    bundle = {
        "service": args.service,
        "commit_sha": args.commit_sha,
        "channel": "stable",
        "tag_source": release_plan.get("tag_source", "build_number"),
        "image_repository": release.get("artifact_repository"),
        "target_branch": release.get("branch"),
        "write_back_branch": "release-relay",
    }
    print(json.dumps(bundle))


if __name__ == "__main__":
    main()
