# Incident: registry pushes keep falling back into auth trouble

The publish path is noisy and inconsistent.

- The active prod registry host comes from the active release profile in `ops/reference/release-profiles.yaml`.
- The durable bot identity that gets reconciled into the cluster comes from `ops/source-of-truth/registry-robot.yaml`.
- Fixes that only patch `cluster/live/secrets/` are temporary; the next bootstrap or rollout will restore the seeded source-of-truth copy.
- The updater auth settings also need to agree with that same seeded identity, otherwise the lane may publish successfully and still fail later when GitOps write-back begins.
- `/app/data/docs/repair-checklist.md` summarizes the expected prod secret path and write-back destination.
