# Incident: the failover build lane no longer matches the evacuation target

The failover release path has been unstable since the control-region evacuation.

- The CI contract now comes from `ops/topology/lane-map.yaml`, the matching release profile, and the service catalog.
- The runner, release plan, and service release metadata should agree on the same prod branch, runner profile, tag source, and artifact repository.
- The noisy failures are usually not limited to the obvious YAMLs. If the visible CI metadata looks right but the stage still fails, inspect the seeded helper and derived handoff inputs that ride with the build lane.
