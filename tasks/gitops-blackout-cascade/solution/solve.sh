#!/bin/bash
set -euo pipefail

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/runner.yaml
runner:
  docker_host: unix:///var/run/docker.sock
  expected_socket: unix:///var/run/docker.sock
  profile: socket-local
  pipeline_name: nebula-api-release
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/release-plan.yaml
release_plan:
  required_runner_profile: socket-local
  target_branch: main
  tag_source: git_sha
  artifact_repository: registry.internal.devops/platform/nebula-api
EOF

mkdir -p /app/data/lab_seed/app-repo/ci/scripts
cat <<'EOF' > /app/data/lab_seed/app-repo/ci/scripts/render_release_bundle.py
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
      "channel": "hotfix",
      "tag_source": release_plan["tag_source"],
      "image_repository": release["artifact_repository"],
      "target_branch": release["branch"],
      "write_back_branch": release_plan["target_branch"],
    }
    print(json.dumps(bundle))


if __name__ == "__main__":
    main()
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/nebula-api/release.yaml
service: nebula-api
branch: main
artifact_repository: registry.internal.devops/platform/nebula-api
current_commit: 2026.03.31-stable
EOF

cat <<'EOF' > /app/data/lab_seed/ops/source-of-truth/registry-robot.yaml
name: release-bot
username: nebula-pusher
token: nebula-prod-write
scopes:
  - push
  - pull
EOF

cat <<'EOF' > /app/data/lab_seed/controllers/image-updater.yaml
updater:
  tracked_service: nebula-api
  auth_secret: cluster/live/secrets/registry-robot.yaml
  write_back_target: gitops-repo
  write_back_branch: main
  manifest_path: services/nebula-api/overlays/prod/values.yaml
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/apps/nebula-api/application.yaml
application:
  service: nebula-api
  namespace: prod
  project: platform-prod
  source_path: services/nebula-api/overlays/prod
  sync_policy: automated
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/values.yaml
image:
  repository: registry.internal.devops/platform/nebula-api
  tag: 2026.03.31-stable
service:
  live_path: prod/nebula-api
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/release-gate.yaml
gate:
  allowed_channels:
    - stable
    - hotfix
  promotion_mode: canary
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/autoscaling-policy.yaml
autoscaling:
  service: nebula-api
  min_replicas: 3
  max_replicas: 12
  cpu_target_utilization: 70
  memory_target_utilization: 75
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/availability-budget.yaml
budget:
  service: nebula-api
  lane: prod-eu
  min_available: 2
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/promotion-policy.yaml
promotion:
  channel: hotfix
  strategy: canary
  freeze: false
  target_branch: main
  target_overlay: services/nebula-api/overlays/prod
  analysis_template: prod-error-budget
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/rollout-window.yaml
window:
  lane: prod-eu
  freeze: false
  require_analysis: true
  hold_minutes: 10
  rollback_on_slo_breach: true
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/canary-analysis.yaml
analysis:
  template: prod-error-budget
  window_minutes: 15
  success_rate_slo: 99.5
  metric_source: prod-prometheus
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/service-monitor.yaml
monitor:
  service: nebula-api
  namespace: observability-prod
  path: /internal/ready
  interval: 30s
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/alert-route.yaml
alert_route:
  receiver: prod-platform-pager
  severity: critical
  service: nebula-api
  metric_source: prod-prometheus
EOF

mkdir -p /app/data/lab_seed/gitops-repo/tools
cat <<'EOF' > /app/data/lab_seed/gitops-repo/tools/render_alert_policy.py
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
    burn_rate = load_yaml(overlay / "burn-rate-alert.yaml")["burn_rate_alert"]

    payload = {
      "service": alert_route["service"],
      "receiver": alert_route["receiver"],
      "metric_source": alert_route["metric_source"],
      "burn_rate": {
        "short_window": burn_rate["short_window"],
        "long_window": burn_rate["long_window"],
        "max_burn_rate": burn_rate["max_burn_rate"],
      },
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/burn-rate-alert.yaml
burn_rate_alert:
  service: nebula-api
  metric_source: prod-prometheus
  short_window: 5m
  long_window: 30m
  max_burn_rate: 2.0
  receiver: prod-platform-pager
  severity: critical
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/traffic-policy.yaml
traffic:
  gateway_host: edge.prod.internal.devops
  gateway_class: internal-mesh
  route_prefix: /nebula-api
  service: nebula-api
  analysis_template: prod-error-budget
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/virtual-service.yaml
virtual_service:
  gateway_host: edge.prod.internal.devops
  gateway_class: internal-mesh
  route_prefix: /nebula-api
  service: nebula-api
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/destination-rule.yaml
destination_rule:
  host: nebula-api.prod.svc.cluster.local
  subsets:
    - name: stable
      lane: prod-eu
      track: stable
    - name: canary
      lane: prod-eu
      track: hotfix
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-api/overlays/prod/telemetry-policy.yaml
telemetry:
  service: nebula-api
  namespace: observability-prod
  provider: prod-otel
  metric_source: prod-prometheus
  gateway_class: internal-mesh
  route_prefix: /nebula-api
  lane: prod-eu
  trace_sampling_percent: 5
  propagation_header: x-nebula-lane
  propagation_value: prod-eu
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/tools/render_mesh_policy.py
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
    destination_rule = load_yaml(overlay / "destination-rule.yaml")["destination_rule"]

    payload = {
      "gateway_host": virtual_service["gateway_host"],
      "service_host": destination_rule["host"],
      "subsets": destination_rule["subsets"],
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/tools/render_telemetry_policy.py
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

    payload = {
      "service": telemetry["service"],
      "namespace": telemetry["namespace"],
      "provider": telemetry["provider"],
      "metric_source": telemetry["metric_source"],
      "gateway_class": telemetry["gateway_class"],
      "route_prefix": telemetry["route_prefix"],
      "lane": telemetry["lane"],
      "trace_sampling_percent": telemetry["trace_sampling_percent"],
      "propagation": {
        "header": telemetry["propagation_header"],
        "value": telemetry["propagation_value"],
      },
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
EOF

python /app/bin/bootstrap_data.py
python /app/bin/simulate_rollout.py --commit-sha 2026.04.03-hotfix
python /app/bin/simulate_rollout.py --commit-sha 2026.04.03-hotfix-2
