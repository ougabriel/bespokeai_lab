# Prod Release Runbook

The lab models the `nebula-api` hotfix path across a few directories:

1. `app-repo/` contains the release lane, release metadata, service catalog, and the durable release handoff manifests.
   It also contains the CI helper scripts that render the release bundle, release attestation, and release witness used by the hotfix lane.
2. `ops/identity/` contains the canonical production bot identity material.
3. `ops/topology/` contains the active prod lane after the migration split.
4. `ops/reference/` contains the canonical release, promotion, observability, and traffic profiles that the active lane now points at.
5. `controllers/` contains the automation layer that writes GitOps changes.
6. `gitops-repo/` contains the prod application, overlay, promotion policy, release gate, delivery contract, autoscaling and availability resources, rollout policy, burn-rate alert, canary analysis config, observability, analysis, and monitor handoffs, alert route, traffic and gateway intents, route contract, service-mesh resources, workload intent, telemetry handoff policy, and the prod policy helper scripts.
7. `cluster/live/` contains the applied deployment, live secret, live route state, the reconciled mesh state, and the live telemetry handoff state.
8. `infra/` contains reachability data for the internal control plane.

Every rollout begins by reconciling the seeded credential source back into the live cluster before the release progresses. If a fix only changes live cluster state, the next rollout will drift back.

`python /app/bin/simulate_rollout.py --commit-sha <sha>` prints a stage-by-stage report for the current attempt. The control-plane API exposes the latest rollout report, the current deployment, and the current route state once the server is running.

The repair target is the seeded release state under `/app/data/lab_seed`. The Python control-plane code under `/app/app` and `/app/bin` is the simulator for this lab and should stay unchanged.
You do not need to inspect the simulator to derive the target values. Use the docs plus the seeded reference YAMLs instead.

The active production contract comes from one chain of source-of-truth:

1. `ops/topology/lane-map.yaml` picks the active lane and the profile names.
2. `ops/reference/release-profiles.yaml` defines runner, branch, tagging, registry host, and write-back behavior.
3. `ops/reference/resilience-profiles.yaml` defines autoscaling and minimum availability.
4. `ops/reference/promotion-profiles.yaml` defines the prod project, prod overlay, sync policy, release channel, and rollout hold behavior.
5. `ops/reference/observability-profiles.yaml` defines analysis template, SLOs, alert routing, monitor settings, and burn-rate windows.
6. `ops/reference/traffic-profiles.yaml` defines the prod gateway host, gateway class, route prefix, and progressive traffic steps.
7. `app-repo/services/nebula-api/service-catalog.yaml` defines the service name, image path suffix, and health path that the prod resources should use.

Use that contract to keep the whole lane aligned across these areas:

- CI contract:
  runner config, release plan, service release metadata, release contract, release baton, release attestation, release witness, and the release helper scripts
- Registry and updater contract:
  source-of-truth bot credentials plus updater auth, write-back target, write-back branch, and manifest path
- GitOps promotion contract:
  Argo application, prod overlay values, release gate, promotion policy, rollout window, and delivery contract
- Resilience and observability contract:
  autoscaling, availability budget, service monitor, alert route, burn-rate policy, canary analysis, observability handoff, analysis handoff, monitor handoff, the alert helper script, and the analysis/monitor handoff helper scripts
- Traffic, mesh, and telemetry contract:
  traffic policy, traffic intent, gateway intent, route contract, virtual service, destination rule, mesh intent, workload intent, telemetry policy, telemetry handoff, the gateway-intent helper script, the mesh helper script, and the telemetry helper script

The prod overlay is intentionally split between visible resources and durable handoff manifests.
The visible resources drive the live rollout:

- `values.yaml`
- `release-gate.yaml`
- `promotion-policy.yaml`
- `rollout-window.yaml`
- `autoscaling-policy.yaml`
- `availability-budget.yaml`
- `service-monitor.yaml`
- `alert-route.yaml`
- `burn-rate-alert.yaml`
- `canary-analysis.yaml`
- `traffic-policy.yaml`
- `virtual-service.yaml`
- `destination-rule.yaml`
- `telemetry-policy.yaml`

The handoff manifests carry the same contract into later rollout stages and helper scripts:

- `release-contract.yaml`
- `release-baton.yaml`
- `release-attestation.yaml`
- `release-witness.yaml`
- `delivery-contract.yaml`
- `observability-handoff.yaml`
- `analysis-handoff.yaml`
- `monitor-handoff.yaml`
- `traffic-intent.yaml`
- `gateway-intent.yaml`
- `route-contract.yaml`
- `mesh-intent.yaml`
- `workload-intent.yaml`
- `telemetry-handoff.yaml`

If the visible resources are fixed but the handoff manifests still point at the migration lane, bootstrap and the second rollout will drift back.
The simulator also validates these handoff manifests inside the rollout stages themselves, so stale release, delivery, observability, analysis, traffic, mesh, workload, or telemetry handoffs will now stop the lane before it reaches a healthy second rollout.

## Common repair pitfalls

- `burn-rate-alert.yaml` is part of the durable prod contract. The alerting path expects the same top-level key and field names used by the active prod lane rather than a migration-era alias.
- The alert, analysis, mesh, and telemetry renderers should mirror the durable handoff manifests. They should not reconstruct defaults like migration hosts, `stable` canary tracks, or legacy propagation headers.
- Mesh subset entries in this lab are durable top-level `{name, lane, track}` objects, and the mesh service host should be `<traffic_service>.prod.svc.cluster.local`.
- The active canary track comes from the promotion profile channel. If the promotion profile says `hotfix`, the mesh and route handoffs should keep `hotfix` instead of renaming it to `canary`.

Some prod overlay resources are expected to be created during the repair if they are missing. The important requirement is that they match the active production profiles and survive a second rollout without drift.

## Minimal recovery recipe

Use `/app/data/docs/repair-checklist.md` as the short recovery plan.

The quickest reliable sequence is:

1. Read the active lane and profile names.
2. Read the matching reference profiles and the service catalog.
3. Repair CI and release metadata first.
4. Repair the registry source-of-truth and updater write-back target next.
5. Repair Argo, promotion, and rollout policy so they all point at the prod overlay.
6. Create or repair the prod handoff manifests for release, delivery, observability, analysis, traffic, mesh, workload, and telemetry.
7. Create the missing prod resilience, burn-rate, mesh, and traffic resources.
8. Repair the helper scripts so they emit data for the same prod contract.

If you find yourself reading `/app/app/*.py` to discover the intended values, stop and go back to the checklist and reference profiles. The active contract is already described there.
