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
  - `app-repo/ci/scripts/render_release_bundle.py`
    Must emit a bundle whose branch, channel, tag source, and image repository match the active release contract.

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
    Top-level key: `burn_rate`
    Important fields: `service`, `metric_source`, `short_window`, `long_window`, `max_burn_rate`
  - `canary-analysis.yaml`
    Top-level key: `analysis`
    Important fields: `template`, `window_minutes`, `success_rate_slo`, `metric_source`
  - `gitops-repo/tools/render_alert_policy.py`
    Must emit alert policy JSON that matches the active observability profile.

- Traffic, mesh, and telemetry:
  - `traffic-policy.yaml`
    Top-level key: `traffic`
    Important fields: `service`, `gateway_host`, `gateway_class`, `route_prefix`, `progressive_steps`
  - `virtual-service.yaml`
    Top-level key: `virtual_service`
    Important fields: `service`, `hosts`, `http`, route destinations, subset weights
  - `destination-rule.yaml`
    Top-level key: `destination_rule`
    Important fields: `service`, `host`, `subsets`
  - `telemetry-policy.yaml`
    Top-level key: `telemetry`
    Important fields: `service`, `namespace`, `provider`, `metric_source`, `gateway_class`, `route_prefix`, `lane`, `trace_sampling_percent`, `propagation_header`, `propagation_value`
  - `gitops-repo/tools/render_mesh_policy.py`
    Must emit mesh policy JSON whose host and subsets match the active traffic contract.
  - `gitops-repo/tools/render_telemetry_policy.py`
    Must emit telemetry handoff JSON whose provider, propagation header, and lane value match the active traffic and observability contract.

Files under `cluster/live/` and generated state under `/app/state/` are rollout outputs, not the durable source-of-truth. If a change only fixes generated state, the next bootstrap or rollout will revert it.
