# Restore The Prod Hotfix Lane

[Context]
You are the DevOps engineer on call for `nebula-api`.

The seeded lab in `/app` models a production hotfix lane after a lane split. CI, registry publish, GitOps promotion, resilience, observability, traffic, mesh, and telemetry are no longer aligned on the same prod contract.

Use the seeded lab in `/app` together with the docs in `/app/data/docs`.

[Task]
Repair the seeded source-of-truth so the active production hotfix lane works again.

A correct repair makes all of these true:

- `python /app/bin/bootstrap_data.py` is safe to rerun.
- The first hotfix rollout can move through the full lane.
- A second hotfix rollout converges on the same prod lane instead of drifting back to migration-era settings.
- The final live deployment, route, mesh, and telemetry state match the active production contract.

[Instructions]
- Start with `/app/data/docs/repair-checklist.md`.
- Confirm the active prod lane from:
  - `/app/data/lab_seed/ops/topology/lane-map.yaml`
  - `/app/data/lab_seed/ops/reference/*.yaml`
  - `/app/data/lab_seed/app-repo/services/nebula-api/service-catalog.yaml`
  - `/app/data/docs/runbook.md`
  - `/app/data/docs/schema-guide.md`
  - `/app/data/docs/incidents/*.md`
- Repair the seeded files under `/app/data/lab_seed`.
- Some prod overlay resources are intentionally missing from the seed. Create them when the active contract requires them.
- Verify the repair by rerunning bootstrap and then running the two hotfix rollout commands back to back.

[Notes]
- Fix the release path itself. Do not hardcode the test commit SHAs into the API or CLI.
- Do not modify the tests.
- Do not replace the simulation with fake success responses.
- Do not edit the control-plane implementation under `/app/app` or `/app/bin`.
- Do not patch generated live state without fixing the seed. The next bootstrap or rollout will drift again if the source-of-truth is still wrong.
