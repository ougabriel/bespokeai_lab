# Schema Guide

The active production lane is not guessed from the tests. It is derived from the seeded contract under `/app/data/lab_seed`.
Use `/app/data/docs/repair-checklist.md` for the short-form recovery order and this file for the field-level schema details.

Use this chain when deciding what "prod" means:

1. `ops/topology/lane-map.yaml` selects the active lane and the profile names for release, resilience, promotion, observability, and traffic.
2. `ops/reference/*.yaml` defines the canonical settings for those profiles.
3. `app-repo/services/nebula-api/service-catalog.yaml` defines the service name, image repo suffix, and health path used by prod resources.

The seeded files are grouped by responsibility:

- CI and release metadata:
  - `app-repo/ci/runner.yaml`
    Top-level key: `runner`
    Important fields: `docker_host`, `expected_socket`, `profile`, `pipeline_name`
  - `app-repo/ci/release-plan.yaml`
    Top-level key: `release_plan`
    Important fields: `required_runner_profile`, `target_branch`, `tag_source`, `artifact_repository`
  - `app-repo/services/nebula-api/release.yaml`
    Important fields: `service`, `branch`, `artifact_repository`, `current_commit`
  - `app-repo/services/nebula-api/release-contract.yaml`
    Top-level key: `contract`
    Important fields: `service`, `tracked_service`, `traffic_service`, `lane`, `target_branch`, `write_back_branch`, `target_overlay`, `image_repository`, `health_path`, `contract_label`
  - `app-repo/services/nebula-api/release-baton.yaml`
    Top-level key: `baton`
    Important fields: `service`, `tracked_service`, `lane`, `write_back_target`, `write_back_branch`, `target_overlay`, `contract_label`
  - `app-repo/services/nebula-api/release-attestation.yaml`
    Top-level key: `attestation`
    Important fields: `service`, `lane`, `target_branch`, `write_back_target`, `write_back_branch`, `image_repository`, `contract_label`
  - `app-repo/services/nebula-api/release-witness.yaml`
    Top-level key: `witness`
    Important fields: `service`, `lane`, `target_overlay`, `live_path`, `gateway_host`, `contract_label`
  - `app-repo/ci/scripts/render_release_bundle.py`
    Must emit a bundle whose branch, channel, tag source, and image repository match the active release contract.
    Expected payload fields: `service`, `commit_sha`, `channel`, `tag_source`, `image_repository`, `target_branch`, `write_back_branch`, `tracked_service`, `traffic_service`, `target_overlay`, `health_path`, `contract_label`
  - `app-repo/ci/scripts/render_release_attestation.py`
    Must emit release attestation JSON whose service, lane, tracked service, branch, write-back target, image repository, and contract label match the active release contract.
    Expected payload fields: `service`, `lane`, `target_branch`, `write_back_target`, `write_back_branch`, `image_repository`, `tracked_service`, `contract_label`, `commit_sha`
  - `app-repo/ci/scripts/render_release_witness.py`
    Must emit release witness JSON whose service, lane, target overlay, live path, gateway host, tracked service, and contract label match the active release contract.
    Expected payload fields: `service`, `lane`, `target_overlay`, `live_path`, `gateway_host`, `tracked_service`, `contract_label`, `commit_sha`

- Registry and automation:
  - `ops/source-of-truth/registry-robot.yaml`
    Important fields: `name`, `username`, `token`, `scopes`
  - `controllers/image-updater.yaml`
    Top-level key: `updater`
    Important fields: `tracked_service`, `auth_secret`, `write_back_target`, `write_back_branch`, `manifest_path`

- GitOps and promotion:
  - `gitops-repo/apps/nebula-api/application.yaml`
    Top-level key: `application`
    Important fields: `service`, `namespace`, `project`, `source_path`, `sync_policy`
  - `gitops-repo/services/nebula-api/overlays/prod/values.yaml`
    Important fields: `image.repository`, `image.tag`, `service.live_path`
  - `release-gate.yaml`
    Top-level key: `gate`
    Important fields: `allowed_channels`, `promotion_mode`
  - `promotion-policy.yaml`
    Top-level key: `promotion`
    Important fields: `channel`, `strategy`, `freeze`, `target_branch`, `target_overlay`, `analysis_template`
  - `rollout-window.yaml`
    Top-level key: `window`
    Important fields: `lane`, `freeze`, `require_analysis`, `hold_minutes`, `rollback_on_slo_breach`, `progressive_steps`
  - `delivery-contract.yaml`
    Top-level key: `contract`
    Important fields: `lane`, `channel`, `mode`, `target_overlay`, `analysis_template`, `metric_source`, `monitor_namespace`, `gateway_host`, `gateway_class`, `route_prefix`, `contract_label`

- Resilience and observability:
  - `autoscaling-policy.yaml`
    Top-level key: `autoscaling`
    Important fields: `service`, `min_replicas`, `max_replicas`, `cpu_target_utilization`, `memory_target_utilization`
  - `availability-budget.yaml`
    Top-level key: `budget`
    Important fields: `service`, `lane`, `min_available`
  - `service-monitor.yaml`
    Top-level key: `monitor`
    Important fields: `service`, `namespace`, `path`, `interval`
  - `alert-route.yaml`
    Top-level key: `alert_route`
    Important fields: `receiver`, `severity`, `service`, `metric_source`
  - `burn-rate-alert.yaml`
    Top-level key: `burn_rate_alert` or `burn_rate`
    Important fields: `service`, `metric_source`, `short_window`, `long_window`, `max_burn_rate`, `receiver`, `severity`
  - `canary-analysis.yaml`
    Top-level key: `analysis`
    Important fields: `template`, `window_minutes`, `success_rate_slo`, `metric_source`
  - `observability-handoff.yaml`
    Top-level key: `handoff`
    Important fields: `service`, `lane`, `analysis_template`, `metric_source`, `monitor_namespace`, `receiver`, `severity`, `contract_label`
  - `analysis-handoff.yaml`
    Top-level key: `handoff`
    Important fields: `service`, `lane`, `analysis_template`, `window_minutes`, `success_rate_slo`, `metric_source`, `contract_label`
  - `monitor-handoff.yaml`
    Top-level key: `handoff`
    Important fields: `service`, `lane`, `namespace`, `path`, `interval`, `analysis_template`, `receiver`, `contract_label`
  - `gitops-repo/tools/render_alert_policy.py`
    Must emit alert policy JSON that matches the active observability profile.
    Expected payload fields: `service`, `receiver`, `severity`, `metric_source`, `analysis_template`, `monitor_namespace`, `contract_label`, `burn_rate.short_window`, `burn_rate.long_window`, `burn_rate.max_burn_rate`
  - `gitops-repo/tools/render_analysis_handoff.py`
    Must emit JSON that combines the analysis handoff and observability handoff for the active lane.
    Expected payload fields: `service`, `lane`, `analysis_template`, `window_minutes`, `success_rate_slo`, `metric_source`, `receiver`, `severity`, `contract_label`, `commit_sha`
  - `gitops-repo/tools/render_monitor_handoff.py`
    Must emit JSON that combines the service monitor and the monitor handoff for the active lane.
    Expected payload fields: `service`, `lane`, `namespace`, `path`, `interval`, `analysis_template`, `receiver`, `contract_label`, `commit_sha`

- Traffic, mesh, and telemetry:
  - `traffic-policy.yaml`
    Top-level key: `traffic`
    Important fields: `service`, `gateway_host`, `gateway_class`, `route_prefix`, `progressive_steps`
  - `traffic-intent.yaml`
    Top-level key: `intent`
    Important fields: `service`, `lane`, `gateway_host`, `gateway_class`, `route_prefix`, `progressive_steps`, `contract_label`
  - `gateway-intent.yaml`
    Top-level key: `intent`
    Important fields: `service`, `lane`, `gateway_host`, `gateway_class`, `route_prefix`, `live_path`, `propagation_header`, `contract_label`
  - `route-contract.yaml`
    Top-level key: `contract`
    Important fields: `service`, `lane`, `gateway_host`, `gateway_class`, `route_prefix`, `live_path`, `contract_label`
  - `virtual-service.yaml`
    Top-level key: `virtual_service`
    Important fields: `service`, `hosts`, `http`, route destinations, subset weights
  - `destination-rule.yaml`
    Top-level key: `destination_rule`
    Important fields: `service`, `host`, `subsets`
    `host` must match the active mesh service host: `<traffic_service>.prod.svc.cluster.local`
    `subsets` must be a top-level list of objects shaped like `{name, lane, track}`
    Expected subsets:
    `{"name": "stable", "lane": <active_lane>, "track": "stable"}`
    `{"name": "canary", "lane": <active_lane>, "track": <promotion_channel>}`
  - `mesh-intent.yaml`
    Top-level key: `intent`
    Important fields: `service`, `lane`, `service_host`, `subsets`, `contract_label`
    `service_host` must reuse the same `<traffic_service>.prod.svc.cluster.local` value as the destination rule
    `subsets` uses the same top-level `{name, lane, track}` schema as `destination-rule.yaml`
  - `workload-intent.yaml`
    Top-level key: `intent`
    Important fields: `service`, `lane`, `namespace`, `image_repository`, `health_path`, `live_path`, `contract_label`
  - `telemetry-policy.yaml`
    Top-level key: `telemetry`
    Important fields: `service`, `namespace`, `provider`, `metric_source`, `gateway_class`, `route_prefix`, `lane`, `trace_sampling_percent`, `propagation_header`, `propagation_value`
  - `telemetry-handoff.yaml`
    Top-level key: `handoff`
    Important fields: `service`, `service_host`, `provider`, `metric_source`, `gateway_class`, `route_prefix`, `propagation_header`, `propagation_value`, `contract_label`
  - `gitops-repo/tools/render_mesh_policy.py`
    Must emit mesh policy JSON whose host and subsets match the active traffic contract.
    Expected payload fields: `gateway_host`, `gateway_class`, `route_prefix`, `service`, `service_host`, `subsets`, `contract_label`
    The renderer should mirror the durable mesh contract instead of rebuilding guessed defaults:
    - `service_host` should match `destination-rule.yaml.host`
    - `subsets` should preserve the durable top-level `{name, lane, track}` entries
  - `gitops-repo/tools/render_gateway_intent.py`
    Must emit gateway intent JSON whose edge metadata matches the active traffic contract.
    Expected payload fields: `service`, `lane`, `gateway_host`, `gateway_class`, `route_prefix`, `live_path`, `propagation_header`, `contract_label`, `commit_sha`
  - `gitops-repo/tools/render_telemetry_policy.py`
    Must emit telemetry handoff JSON whose provider, propagation header, and lane value match the active traffic and observability contract.
    Expected payload fields: `service`, `namespace`, `provider`, `metric_source`, `gateway_class`, `route_prefix`, `lane`, `trace_sampling_percent`, `service_host`, `contract_label`, `propagation.header`, `propagation.value`

Files under `cluster/live/` and generated state under `/app/state/` are rollout outputs, not the durable source-of-truth. If a change only fixes generated state, the next bootstrap or rollout will revert it.
