#!/usr/bin/env python

from __future__ import annotations

import argparse
import json
import sys

from app.rollout import execute_rollout


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate a prod rollout through the Aurora control plane.")
    parser.add_argument("--commit-sha", required=True, help="Fresh commit SHA to roll out")
    args = parser.parse_args()

    report = execute_rollout(args.commit_sha)
    print(json.dumps(report, indent=2, sort_keys=True))
    sys.exit(0 if report["status"] == "healthy" else 1)
