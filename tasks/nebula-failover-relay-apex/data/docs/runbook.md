# Prod Failover Runbook

The lab models the `nebula-relay` production failover relay across a few directories:

1. `app-repo/` contains the release lane, release metadata, service catalog, and the derived release handoff and attestation manifests for the failover lane.
   It also contains the CI helper scripts that render the release bundle and release attestation used during verification.
2. `ops/identity/` contains the canonical production bot identity material.
3. `ops/topology/` contains the active production failover lane after the control-region evacuation.
4. `ops/reference/` contains the canonical release, promotion, observability, and traffic profiles that the active lane now points at.
5. `controllers/` contains the automation layer that writes GitOps changes.
6. `gitops-repo/` contains the prod application, overlay, rollout controls, policy inputs, helper scripts, and a mix of derived handoff manifests used during verification.
7. `cluster/live/` contains the applied deployment, live secret, live route state, the reconciled mesh state, and the live telemetry handoff state.
8. `infra/` contains reachability data for the internal control plane.

Every rollout begins by reconciling the seeded credential source back into the live cluster before the release progresses. If a fix only changes live cluster state, the next failover rollout will drift back.

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
7. `app-repo/services/nebula-relay/service-catalog.yaml` defines the service name, image path suffix, and health path that the prod resources should use.

Use that contract to keep the whole lane aligned across these areas:

- CI contract:
  runner config, release plan, service release metadata, and any seeded helper that still emits stale failover data
- Registry and updater contract:
  source-of-truth bot credentials plus updater auth, write-back target, write-back branch, and manifest path
- GitOps promotion contract:
  Argo application, prod overlay values, release gate, promotion policy, rollout window, and the prod handoff data those controls depend on
- Resilience and observability contract:
  autoscaling, availability budget, service monitor, alerting, analysis inputs, and their helper outputs
- Traffic, mesh, and telemetry contract:
  traffic policy, route and mesh manifests, workload and telemetry handoffs, and the helper outputs that tie them together

Some prod overlay resources are expected to be created during the repair if they are missing. The important requirement is that they match the active production profiles and survive a second rollout without drift.

## Minimal recovery recipe

Use `/app/data/docs/repair-checklist.md` as the short recovery plan.

The quickest reliable sequence is:

1. Read the active lane and profile names.
2. Read the matching reference profiles and the service catalog.
3. Repair CI and release metadata first, including the derived release handoff manifest.
4. Repair the registry source-of-truth and updater write-back target next.
5. Repair Argo, promotion, and rollout policy so they all point at the prod overlay and the derived delivery handoff manifest.
6. Create the missing prod resilience, mesh, traffic, or telemetry resources that the active lane now expects.
7. Repair the helper scripts so they emit data for the same prod contract label and downstream handoff manifests.

If you find yourself reading `/app/app/*.py` to discover the intended values, stop and go back to the checklist and reference profiles. The active contract is already described there.
