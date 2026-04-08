# Repair Checklist

Use this file as the recovery worksheet for the hotfix lane. It tells you where to look and what has to agree, but the target values still need to be derived from the active lane, the matching reference profiles, and the service catalog.

## Start here

Read these first, in this order:

- `ops/topology/lane-map.yaml`
- `ops/reference/release-profiles.yaml`
- `ops/reference/resilience-profiles.yaml`
- `ops/reference/promotion-profiles.yaml`
- `ops/reference/observability-profiles.yaml`
- `ops/reference/traffic-profiles.yaml`
- `app-repo/services/nebula-api/service-catalog.yaml`

From that chain, derive the active production contract:

- active lane and active profile names
- runner profile, target branch, tag source, registry host, write-back target, and write-back branch
- prod project, prod overlay, sync policy, promotion channel, promotion mode, rollout hold, and rollback behavior
- min/max replicas, CPU target, memory target, and minimum availability
- analysis template, SLO window, metric source, burn-rate windows, alert receiver, and monitor settings
- gateway host, gateway class, route prefix, progressive traffic steps, and telemetry propagation settings
- service name, tracked service, traffic service, image path suffix, and health path

## Repair order

1. CI and release metadata

- Repair:
  - `app-repo/ci/runner.yaml`
  - `app-repo/ci/release-plan.yaml`
  - `app-repo/services/nebula-api/release.yaml`
  - `app-repo/ci/scripts/render_release_bundle.py`
- These files should agree on the same runner profile, branch, tag source, and image repository.

2. Registry and updater

- Repair:
  - `ops/source-of-truth/registry-robot.yaml`
  - `controllers/image-updater.yaml`
- The durable bot identity must match the active broker identity.
- The updater must track the active service, use the live registry secret path, and write the prod image tag back into the active prod overlay on the active write-back branch.

3. GitOps and promotion

- Repair:
  - `gitops-repo/apps/nebula-api/application.yaml`
  - `gitops-repo/services/nebula-api/overlays/prod/values.yaml`
  - `release-gate.yaml`
  - `promotion-policy.yaml`
  - `rollout-window.yaml`
- These files should all target the active prod overlay and the active hotfix lane, not the legacy migration lane.

4. Resilience and observability

- Repair or create:
  - `autoscaling-policy.yaml`
  - `availability-budget.yaml`
  - `service-monitor.yaml`
  - `alert-route.yaml`
  - `burn-rate-alert.yaml`
  - `canary-analysis.yaml`
  - `gitops-repo/tools/render_alert_policy.py`
- Missing prod files are expected here. Create them rather than patching generated live state.

5. Traffic, mesh, and telemetry

- Repair or create:
  - `traffic-policy.yaml`
  - `virtual-service.yaml`
  - `destination-rule.yaml`
  - `telemetry-policy.yaml`
  - `gitops-repo/tools/render_mesh_policy.py`
  - `gitops-repo/tools/render_telemetry_policy.py`
- Missing prod mesh files are expected here. Create them under the prod overlay.

## Minimal success check

After the seeded source-of-truth is repaired:

- `python /app/bin/bootstrap_data.py` should remain safe to rerun.
- The first rollout should progress through the full lane instead of failing in CI.
- The second rollout should stay on the same prod contract.
- The final live deployment, route, mesh, and telemetry outputs should all reflect the contract derived from the active lane and the matching profiles.
- Once those two rollouts succeed and the second one stays on the same prod lane, the repair is complete. Extra simulator spelunking is unnecessary.
