#!/bin/bash
set -euo pipefail

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/runner.yaml
runner:
  docker_host: unix:///var/run/docker.sock
  expected_socket: unix:///var/run/docker.sock
  profile: socket-fleet
  pipeline_name: aurora-gateway-release
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/ci/release-plan.yaml
release_plan:
  required_runner_profile: socket-fleet
  target_branch: main
  tag_source: git_sha
  artifact_repository: registry.internal.devops/platform/aurora-gateway
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

cat <<'EOF' > /app/data/lab_seed/app-repo/services/aurora-gateway/release.yaml
service: aurora-gateway
branch: main
artifact_repository: registry.internal.devops/platform/aurora-gateway
current_commit: 2026.03.31-stable
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/aurora-gateway/release-contract.yaml
contract:
  service: aurora-gateway
  tracked_service: aurora-gateway
  traffic_service: aurora-gateway
  lane: dr-eu
  target_branch: main
  write_back_branch: main
  target_overlay: services/aurora-gateway/overlays/prod
  image_repository: registry.internal.devops/platform/aurora-gateway
  health_path: /internal/ready
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/aurora-gateway/release-baton.yaml
baton:
  service: aurora-gateway
  tracked_service: aurora-gateway
  lane: dr-eu
  write_back_target: gitops-repo
  write_back_branch: main
  target_overlay: services/aurora-gateway/overlays/prod
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/app-repo/services/aurora-gateway/release-attestation.yaml
attestation:
  service: aurora-gateway
  lane: dr-eu
  target_branch: main
  write_back_target: gitops-repo
  write_back_branch: main
  image_repository: registry.internal.devops/platform/aurora-gateway
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/ops/source-of-truth/registry-robot.yaml
name: failover-bot
username: aurora-pusher
token: aurora-prod-write
scopes:
  - push
  - pull
EOF

cat <<'EOF' > /app/data/lab_seed/controllers/image-updater.yaml
updater:
  tracked_service: aurora-gateway
  auth_secret: cluster/live/secrets/registry-robot.yaml
  write_back_target: gitops-repo
  write_back_branch: main
  manifest_path: services/aurora-gateway/overlays/prod/values.yaml
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/apps/aurora-gateway/application.yaml
application:
  service: aurora-gateway
  namespace: prod
  project: aurora-platform
  source_path: services/aurora-gateway/overlays/prod
  sync_policy: automated
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/values.yaml
image:
  repository: registry.internal.devops/platform/aurora-gateway
  tag: 2026.03.31-stable
service:
  live_path: prod/aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/release-gate.yaml
gate:
  allowed_channels:
    - stable
    - failover
  promotion_mode: canary
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/autoscaling-policy.yaml
autoscaling:
  service: aurora-gateway
  min_replicas: 3
  max_replicas: 12
  cpu_target_utilization: 70
  memory_target_utilization: 75
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/availability-budget.yaml
budget:
  service: aurora-gateway
  lane: dr-eu
  min_available: 2
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/promotion-policy.yaml
promotion:
  channel: failover
  strategy: canary
  freeze: false
  target_branch: main
  target_overlay: services/aurora-gateway/overlays/prod
  analysis_template: dr-error-budget
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/rollout-window.yaml
window:
  lane: dr-eu
  freeze: false
  require_analysis: true
  hold_minutes: 10
  rollback_on_slo_breach: true
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/delivery-contract.yaml
contract:
  lane: dr-eu
  channel: failover
  mode: canary
  target_overlay: services/aurora-gateway/overlays/prod
  analysis_template: dr-error-budget
  metric_source: dr-prometheus
  monitor_namespace: observability-dr
  gateway_host: edge.dr.internal.devops
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/observability-handoff.yaml
handoff:
  service: aurora-gateway
  lane: dr-eu
  analysis_template: dr-error-budget
  metric_source: dr-prometheus
  monitor_namespace: observability-dr
  receiver: dr-platform-pager
  severity: critical
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/analysis-handoff.yaml
handoff:
  service: aurora-gateway
  lane: dr-eu
  analysis_template: dr-error-budget
  window_minutes: 15
  success_rate_slo: 99.5
  metric_source: dr-prometheus
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/canary-analysis.yaml
analysis:
  template: dr-error-budget
  window_minutes: 15
  success_rate_slo: 99.5
  metric_source: dr-prometheus
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/service-monitor.yaml
monitor:
  service: aurora-gateway
  namespace: observability-dr
  path: /internal/ready
  interval: 30s
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/alert-route.yaml
alert_route:
  receiver: dr-platform-pager
  severity: critical
  service: aurora-gateway
  metric_source: dr-prometheus
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

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/burn-rate-alert.yaml
burn_rate_alert:
  service: aurora-gateway
  metric_source: dr-prometheus
  short_window: 5m
  long_window: 30m
  max_burn_rate: 2.0
  receiver: dr-platform-pager
  severity: critical
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/traffic-policy.yaml
traffic:
  gateway_host: edge.dr.internal.devops
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  service: aurora-gateway
  analysis_template: dr-error-budget
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/traffic-intent.yaml
intent:
  service: aurora-gateway
  lane: dr-eu
  gateway_host: edge.dr.internal.devops
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  progressive_steps:
    - 10
    - 50
    - 100
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/route-contract.yaml
contract:
  service: aurora-gateway
  lane: dr-eu
  gateway_host: edge.dr.internal.devops
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  live_path: prod/aurora-gateway
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/virtual-service.yaml
virtual_service:
  gateway_host: edge.dr.internal.devops
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  service: aurora-gateway
  progressive_steps:
    - 10
    - 50
    - 100
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/destination-rule.yaml
destination_rule:
  host: aurora-gateway.prod.svc.cluster.local
  subsets:
    - name: stable
      lane: dr-eu
      track: stable
    - name: canary
      lane: dr-eu
      track: failover
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/mesh-intent.yaml
intent:
  service: aurora-gateway
  lane: dr-eu
  service_host: aurora-gateway.prod.svc.cluster.local
  subsets:
    - name: stable
      lane: dr-eu
      track: stable
    - name: canary
      lane: dr-eu
      track: failover
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/workload-intent.yaml
intent:
  service: aurora-gateway
  lane: dr-eu
  namespace: prod
  image_repository: registry.internal.devops/platform/aurora-gateway
  health_path: /internal/ready
  live_path: prod/aurora-gateway
  contract_label: dr-eu.failover.aurora-gateway
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/telemetry-policy.yaml
telemetry:
  service: aurora-gateway
  namespace: observability-dr
  provider: dr-otel
  metric_source: dr-prometheus
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  lane: dr-eu
  trace_sampling_percent: 5
  propagation_header: x-aurora-lane
  propagation_value: dr-eu
EOF

cat <<'EOF' > /app/data/lab_seed/gitops-repo/services/aurora-gateway/overlays/prod/telemetry-handoff.yaml
handoff:
  service: aurora-gateway
  service_host: aurora-gateway.prod.svc.cluster.local
  provider: dr-otel
  metric_source: dr-prometheus
  gateway_class: failover-mesh
  route_prefix: /aurora-gateway
  propagation_header: x-aurora-lane
  propagation_value: dr-eu
  contract_label: dr-eu.failover.aurora-gateway
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
