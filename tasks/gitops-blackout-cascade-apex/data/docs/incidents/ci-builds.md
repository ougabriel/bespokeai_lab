# Incident: the hotfix build lane no longer matches prod

The hotfix release path has been unstable since the production lane split.

- The CI contract now comes from `ops/topology/lane-map.yaml` plus `ops/reference/release-profiles.yaml`.
- The runner, release plan, and service release metadata should agree on the same prod branch, runner profile, tag source, and artifact repository.
- Use `ops/topology/lane-map.yaml`, the matching release profile, and the service catalog to derive the active CI contract.
- The active CI files are:
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
- The release helper scripts are part of the contract: they must emit prod hotfix bundle, attestation, and witness data that match the active release lane instead of the old migration lane.
