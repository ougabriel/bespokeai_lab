# Incident: the failover build lane no longer matches the evacuation target

The failover release path has been unstable since the control-region evacuation.

- The CI contract now comes from `ops/topology/lane-map.yaml` plus `ops/reference/release-profiles.yaml`.
- The runner, release plan, and service release metadata should agree on the same prod branch, runner profile, tag source, and artifact repository.
- Use `ops/topology/lane-map.yaml`, the matching release profile, and the service catalog to derive the active CI contract.
- The active CI files are the runner config, release plan, service release metadata, the derived release manifests, and the CI helper scripts.
- The release manifests and CI renderers are part of the contract: they must emit prod failover handoff data that matches the active release lane instead of the retired primary lane.
