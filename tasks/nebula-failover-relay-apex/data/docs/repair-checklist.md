# Repair Checklist

Use this file as the recovery worksheet for the failover lane. It tells you where to investigate and which contracts have to agree, but the target values still need to be derived from the active lane, the matching reference profiles, and the service catalog.

## Start here

Read these first, in this order:

- `ops/topology/lane-map.yaml`
- `ops/reference/release-profiles.yaml`
- `ops/reference/resilience-profiles.yaml`
- `ops/reference/promotion-profiles.yaml`
- `ops/reference/observability-profiles.yaml`
- `ops/reference/traffic-profiles.yaml`
- `app-repo/services/nebula-relay/service-catalog.yaml`

From that chain, derive the active production contract:

- active lane and active profile names
- runner profile, target branch, tag source, registry host, write-back target, and write-back branch
- prod project, prod overlay, sync policy, promotion channel, promotion mode, rollout hold, and rollback behavior
- min/max replicas, CPU target, memory target, and minimum availability
- analysis template, SLO window, metric source, burn-rate windows, alert receiver, and monitor settings
- gateway host, gateway class, route prefix, progressive traffic steps, and telemetry propagation settings
- service name, tracked service, traffic service, image path suffix, and health path
- the compact contract label `<lane>.<channel>.<service>` used by the handoff manifests and helper scripts

## Repair order

1. CI and release metadata

- Repair the CI lane first.
- That includes the visible release metadata plus any seeded helper or derived manifest that still emits the wrong branch, tag source, publish target, or contract label.

2. Registry and updater

- Repair the durable registry identity and the updater handoff so they agree on the active service, the live registry secret path, and the active write-back destination.

3. GitOps and promotion

- Repair the prod application path, overlay values, release gate, promotion policy, rollout controls, and any prod handoff data that still points at the retired primary lane.

4. Resilience and observability

- Repair or create the prod resilience and observability inputs that the active lane now depends on.
- Missing prod files are expected here. Create them rather than patching generated live state.

5. Traffic, mesh, and telemetry

- Repair or create the prod traffic policy, route and mesh intent manifests, workload and telemetry handoffs, and the related helper scripts.
- Missing prod mesh files are expected here. Create them under the prod overlay.
- The traffic, mesh, workload, and telemetry handoff manifests for the prod lane must all match the same contract label, service host, and propagation settings.

## Minimal success check

After the seeded source-of-truth is repaired:

- `python /app/bin/bootstrap_data.py` should remain safe to rerun.
- The first rollout should progress through the full lane instead of failing in CI.
- The second rollout should stay on the same prod contract.
- The final live deployment, route, mesh, and telemetry outputs should all reflect the contract derived from the active lane and the matching profiles.
- Once those two rollouts succeed and the second one stays on the same prod lane, the repair is complete. Extra simulator spelunking is unnecessary.
