# Incident: registry pushes keep falling out of the failover corridor

The publish path is noisy and inconsistent.

- The active prod registry host comes from the active release profile in `ops/reference/release-profiles.yaml`.
- The durable bot identity that gets reconciled into the cluster comes from `ops/source-of-truth/registry-robot.yaml`.
- Fixes that only patch `cluster/live/secrets/` are temporary; the next bootstrap or failover rollout will restore the seeded source-of-truth copy.
- The updater auth settings also need to agree with that same seeded identity, otherwise the lane may publish successfully and still fail later when GitOps write-back begins.
- If credentials look repaired but later stages still reject the lane, double-check where the write-back contract is anchored, not just the secret contents.
