#!/bin/bash
set -euo pipefail

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/runner.yaml
runner:
  docker_host: unix:///var/run/docker.sock
  expected_socket: unix:///var/run/docker.sock
  profile: socket-dr
  pipeline_name: nebula-relay-release
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/release-plan.yaml
release_plan:
  required_runner_profile: socket-dr
  target_branch: main
  tag_source: git_sha
  artifact_repository: registry.internal.devops/platform/nebula-relay
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
    release_contract = load_yaml(
        lab_root / "app-repo" / "services" / args.service / "release-contract.yaml"
    )["contract"]

    bundle = {
      "service": args.service,
      "commit_sha": args.commit_sha,
      "channel": "failover",
      "tag_source": release_plan["tag_source"],
      "image_repository": release["artifact_repository"],
      "target_branch": release["branch"],
      "write_back_branch": release_plan["target_branch"],
      "tracked_service": release_contract["tracked_service"],
      "traffic_service": release_contract["traffic_service"],
      "target_overlay": release_contract["target_overlay"],
      "health_path": release_contract["health_path"],
      "contract_label": release_contract["contract_label"],
    }
    print(json.dumps(bundle))


if __name__ == "__main__":
    main()
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/scripts/render_release_attestation.py
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
    release_attestation = load_yaml(
        lab_root / "app-repo" / "services" / args.service / "release-attestation.yaml"
    )["attestation"]
    release_contract = load_yaml(
        lab_root / "app-repo" / "services" / args.service / "release-contract.yaml"
    )["contract"]

    payload = {
      "service": release_attestation["service"],
      "lane": release_attestation["lane"],
      "target_branch": release_attestation["target_branch"],
      "write_back_target": release_attestation["write_back_target"],
      "write_back_branch": release_attestation["write_back_branch"],
      "image_repository": release_attestation["image_repository"],
      "tracked_service": release_contract["tracked_service"],
      "contract_label": release_attestation["contract_label"],
      "commit_sha": args.commit_sha,
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/nebula-relay/release.yaml
service: nebula-relay
branch: main
artifact_repository: registry.internal.devops/platform/nebula-relay
current_commit: 2026.03.31-stable
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/nebula-relay/release-contract.yaml
contract:
  service: nebula-relay
  tracked_service: nebula-relay
  traffic_service: nebula-relay
  lane: prod-dr
  target_branch: main
  write_back_branch: main
  target_overlay: services/nebula-relay/overlays/prod
  image_repository: registry.internal.devops/platform/nebula-relay
  health_path: /internal/ready
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/nebula-relay/release-baton.yaml
baton:
  service: nebula-relay
  tracked_service: nebula-relay
  lane: prod-dr
  write_back_target: gitops-repo
  write_back_branch: main
  target_overlay: services/nebula-relay/overlays/prod
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/nebula-relay/release-attestation.yaml
attestation:
  service: nebula-relay
  lane: prod-dr
  target_branch: main
  write_back_target: gitops-repo
  write_back_branch: main
  image_repository: registry.internal.devops/platform/nebula-relay
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/ops/source-of-truth/registry-robot.yaml
name: failover-bot
username: nebula-pusher
token: nebula-prod-write
scopes:
  - push
  - pull
EOF

cat <<'EOF' > /app/data/lab_seed/controllers/image-updater.yaml
updater:
  tracked_service: nebula-relay
  auth_secret: cluster/live/secrets/registry-robot.yaml
  write_back_target: gitops-repo
  write_back_branch: main
  manifest_path: services/nebula-relay/overlays/prod/values.yaml
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/apps/nebula-relay/application.yaml
application:
  service: nebula-relay
  namespace: prod
  project: nebula-platform
  source_path: services/nebula-relay/overlays/prod
  sync_policy: automated
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/values.yaml
image:
  repository: registry.internal.devops/platform/nebula-relay
  tag: 2026.03.31-stable
service:
  live_path: prod/nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/release-gate.yaml
gate:
  allowed_channels:
    - stable
    - failover
  promotion_mode: canary
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/autoscaling-policy.yaml
autoscaling:
  service: nebula-relay
  min_replicas: 3
  max_replicas: 12
  cpu_target_utilization: 70
  memory_target_utilization: 75
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/availability-budget.yaml
budget:
  service: nebula-relay
  lane: prod-dr
  min_available: 2
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/promotion-policy.yaml
promotion:
  channel: failover
  strategy: canary
  freeze: false
  target_branch: main
  target_overlay: services/nebula-relay/overlays/prod
  analysis_template: nebula-dr-error-budget
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/rollout-window.yaml
window:
  lane: prod-dr
  freeze: false
  require_analysis: true
  hold_minutes: 10
  rollback_on_slo_breach: true
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/delivery-contract.yaml
contract:
  lane: prod-dr
  channel: failover
  mode: canary
  target_overlay: services/nebula-relay/overlays/prod
  analysis_template: nebula-dr-error-budget
  metric_source: nebula-dr-prometheus
  monitor_namespace: observability-nebula-dr
  gateway_host: edge.nebula-dr.internal.devops
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/observability-handoff.yaml
handoff:
  service: nebula-relay
  lane: prod-dr
  analysis_template: nebula-dr-error-budget
  metric_source: nebula-dr-prometheus
  monitor_namespace: observability-nebula-dr
  receiver: nebula-dr-pager
  severity: critical
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/analysis-handoff.yaml
handoff:
  service: nebula-relay
  lane: prod-dr
  analysis_template: nebula-dr-error-budget
  window_minutes: 15
  success_rate_slo: 99.5
  metric_source: nebula-dr-prometheus
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/canary-analysis.yaml
analysis:
  template: nebula-dr-error-budget
  window_minutes: 15
  success_rate_slo: 99.5
  metric_source: nebula-dr-prometheus
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/service-monitor.yaml
monitor:
  service: nebula-relay
  namespace: observability-nebula-dr
  path: /internal/ready
  interval: 30s
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/alert-route.yaml
alert_route:
  receiver: nebula-dr-pager
  severity: critical
  service: nebula-relay
  metric_source: nebula-dr-prometheus
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
    delivery_contract = load_yaml(overlay / "delivery-contract.yaml")["contract"]

    payload = {
      "service": alert_route["service"],
      "receiver": alert_route["receiver"],
      "severity": alert_route["severity"],
      "metric_source": alert_route["metric_source"],
      "analysis_template": delivery_contract["analysis_template"],
      "monitor_namespace": delivery_contract["monitor_namespace"],
      "contract_label": delivery_contract["contract_label"],
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

cat <<'EOF' > /app/data/lab_seed/gitops-repo/tools/render_analysis_handoff.py
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
    analysis_handoff = load_yaml(overlay / "analysis-handoff.yaml")["handoff"]
    observability_handoff = load_yaml(overlay / "observability-handoff.yaml")["handoff"]

    payload = {
      "service": analysis_handoff["service"],
      "lane": analysis_handoff["lane"],
      "analysis_template": analysis_handoff["analysis_template"],
      "window_minutes": analysis_handoff["window_minutes"],
      "success_rate_slo": analysis_handoff["success_rate_slo"],
      "metric_source": analysis_handoff["metric_source"],
      "receiver": observability_handoff["receiver"],
      "severity": observability_handoff["severity"],
      "contract_label": analysis_handoff["contract_label"],
      "commit_sha": args.commit_sha,
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/burn-rate-alert.yaml
burn_rate_alert:
  service: nebula-relay
  metric_source: nebula-dr-prometheus
  short_window: 5m
  long_window: 30m
  max_burn_rate: 2.0
  receiver: nebula-dr-pager
  severity: critical
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/traffic-policy.yaml
traffic:
  gateway_host: edge.nebula-dr.internal.devops
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  service: nebula-relay
  analysis_template: nebula-dr-error-budget
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/traffic-intent.yaml
intent:
  service: nebula-relay
  lane: prod-dr
  gateway_host: edge.nebula-dr.internal.devops
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  progressive_steps:
    - 10
    - 50
    - 100
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/route-contract.yaml
contract:
  service: nebula-relay
  lane: prod-dr
  gateway_host: edge.nebula-dr.internal.devops
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  live_path: prod/nebula-relay
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/virtual-service.yaml
virtual_service:
  gateway_host: edge.nebula-dr.internal.devops
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  service: nebula-relay
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/destination-rule.yaml
destination_rule:
  host: nebula-relay.prod.svc.cluster.local
  subsets:
    - name: stable
      lane: prod-dr
      track: stable
    - name: canary
      lane: prod-dr
      track: failover
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/mesh-intent.yaml
intent:
  service: nebula-relay
  lane: prod-dr
  service_host: nebula-relay.prod.svc.cluster.local
  subsets:
    - name: stable
      lane: prod-dr
      track: stable
    - name: canary
      lane: prod-dr
      track: failover
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/workload-intent.yaml
intent:
  service: nebula-relay
  lane: prod-dr
  namespace: prod
  image_repository: registry.internal.devops/platform/nebula-relay
  health_path: /internal/ready
  live_path: prod/nebula-relay
  contract_label: prod-dr.failover.nebula-relay
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/telemetry-policy.yaml
telemetry:
  service: nebula-relay
  namespace: observability-nebula-dr
  provider: nebula-dr-otel
  metric_source: nebula-dr-prometheus
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  lane: prod-dr
  trace_sampling_percent: 5
  propagation_header: x-nebula-corridor
  propagation_value: prod-dr
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/nebula-relay/overlays/prod/telemetry-handoff.yaml
handoff:
  service: nebula-relay
  service_host: nebula-relay.prod.svc.cluster.local
  provider: nebula-dr-otel
  metric_source: nebula-dr-prometheus
  gateway_class: nebula-failover-mesh
  route_prefix: /nebula-relay
  propagation_header: x-nebula-corridor
  propagation_value: prod-dr
  contract_label: prod-dr.failover.nebula-relay
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
    delivery_contract = load_yaml(overlay / "delivery-contract.yaml")["contract"]

    payload = {
      "gateway_host": virtual_service["gateway_host"],
      "gateway_class": virtual_service["gateway_class"],
      "route_prefix": virtual_service["route_prefix"],
      "service": virtual_service["service"],
      "service_host": destination_rule["host"],
      "subsets": destination_rule["subsets"],
      "contract_label": delivery_contract["contract_label"],
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
    handoff = load_yaml(overlay / "telemetry-handoff.yaml")["handoff"]

    payload = {
      "service": telemetry["service"],
      "namespace": telemetry["namespace"],
      "provider": telemetry["provider"],
      "metric_source": telemetry["metric_source"],
      "gateway_class": telemetry["gateway_class"],
      "route_prefix": telemetry["route_prefix"],
      "lane": telemetry["lane"],
      "trace_sampling_percent": telemetry["trace_sampling_percent"],
      "service_host": handoff["service_host"],
      "contract_label": handoff["contract_label"],
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
python /app/bin/simulate_rollout.py --commit-sha 2026.04.03-failover
python /app/bin/simulate_rollout.py --commit-sha 2026.04.03-failover-2
