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
- contract label, tracked service, traffic service, prod namespace, and live path
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
  - `app-repo/services/nebula-api/release-contract.yaml`
  - `app-repo/services/nebula-api/release-baton.yaml`
  - `app-repo/services/nebula-api/release-attestation.yaml`
  - `app-repo/services/nebula-api/release-witness.yaml`
  - `app-repo/ci/scripts/render_release_bundle.py`
  - `app-repo/ci/scripts/render_release_attestation.py`
  - `app-repo/ci/scripts/render_release_witness.py`
- These files should agree on the same runner profile, branch, tag source, image repository, tracked service, target overlay, and contract label.
- The baton and attestation manifests are durable source-of-truth, not rollout by-products. If they still point at the migration lane, later stages will drift even when CI looks healthy.
- The release witness records which live route and gateway the prod handoff is supposed to reach. It must agree with the release contract and with the route-facing prod resources.
- The first CI stage now validates the release contract, release baton, release attestation, release witness, and both release renderers before the lane can progress.

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
  - `delivery-contract.yaml`
- These files should all target the active prod overlay and the active hotfix lane, not the legacy migration lane.
- `delivery-contract.yaml` is the prod handoff manifest that ties the promotion lane, analysis settings, and network edge together. It should not be left on migration defaults.

4. Resilience and observability

- Repair or create:
  - `autoscaling-policy.yaml`
  - `availability-budget.yaml`
  - `service-monitor.yaml`
  - `alert-route.yaml`
  - `burn-rate-alert.yaml`
  - `canary-analysis.yaml`
  - `observability-handoff.yaml`
  - `analysis-handoff.yaml`
  - `monitor-handoff.yaml`
  - `gitops-repo/tools/render_alert_policy.py`
  - `gitops-repo/tools/render_analysis_handoff.py`
  - `gitops-repo/tools/render_monitor_handoff.py`
- Missing prod files are expected here. Create them rather than patching generated live state.
- The observability handoff files carry the alert receiver, monitor namespace, analysis window, SLO, and contract label into later rollout stages.
- The monitor handoff ties the service monitor and the analysis lane together. It should carry the prod namespace, health path, interval, analysis template, receiver, and contract label.
- The alerting and analysis stages actively validate the observability handoff, analysis handoff, monitor handoff, and both analysis/monitor renderers, so leaving those files stale will now stop the rollout instead of only lowering the grader.

5. Traffic, mesh, and telemetry

- Repair or create:
  - `traffic-policy.yaml`
  - `traffic-intent.yaml`
  - `gateway-intent.yaml`
  - `route-contract.yaml`
  - `virtual-service.yaml`
  - `destination-rule.yaml`
  - `mesh-intent.yaml`
  - `workload-intent.yaml`
  - `telemetry-policy.yaml`
  - `telemetry-handoff.yaml`
  - `gitops-repo/tools/render_gateway_intent.py`
  - `gitops-repo/tools/render_mesh_policy.py`
  - `gitops-repo/tools/render_telemetry_policy.py`
- Missing prod mesh files are expected here. Create them under the prod overlay.
- These intent and handoff manifests are part of the durable prod contract. They must agree with the visible mesh and telemetry files on host, subsets, route prefix, propagation header, and contract label.
- The gateway intent is the durable edge handoff. It must agree with the route contract on gateway host, class, route prefix, live path, propagation header, and contract label.
- The traffic, mesh, and telemetry stages now validate these durable intent and handoff manifests directly, including the gateway-intent renderer. Fixing only the visible policy files is no longer enough for a healthy rollout.
- For the mesh contract specifically:
  - `destination-rule.yaml.host` and `mesh-intent.yaml.service_host` should be `<traffic_service>.prod.svc.cluster.local`
  - subset entries are top-level objects with `name`, `lane`, and `track`
  - the canary subset track should use the active promotion channel, not a guessed default like `stable`
  - `render_mesh_policy.py` should emit the same host and subset objects that the durable mesh files declare

## Common pitfalls

- `burn-rate-alert.yaml` should use the same top-level key that the durable alert path expects. In this lab that key is `burn_rate_alert`, not a migration-era guessed alias.
- `render_alert_policy.py` should read the durable burn-rate manifest and preserve the active receiver, metric source, and burn-rate windows from the prod contract.
- `virtual-service.yaml`, `destination-rule.yaml`, and `mesh-intent.yaml` should agree on the prod mesh host: `<traffic_service>.prod.svc.cluster.local`.
- Mesh subset objects are not nested `labels` maps in this task. They are durable top-level entries shaped like `{name, lane, track}`.
- The canary track should reuse the active promotion channel value such as `hotfix`; do not substitute a generic track like `canary` or `stable`.
- The mesh and telemetry helper scripts should mirror the durable intent files instead of rebuilding guessed defaults from only one visible manifest.

## Minimal success check

After the seeded source-of-truth is repaired:

- `python /app/bin/bootstrap_data.py` should remain safe to rerun.
- The first rollout should progress through the full lane instead of failing in CI.
- The second rollout should stay on the same prod contract.
- The final live deployment, route, mesh, and telemetry outputs should all reflect the contract derived from the active lane and the matching profiles.
- The durable handoff manifests and helper scripts should also emit the same contract, so the second rollout does not drift back.
- Once those two rollouts succeed and the second one stays on the same prod lane, the repair is complete. Extra simulator spelunking is unnecessary.
