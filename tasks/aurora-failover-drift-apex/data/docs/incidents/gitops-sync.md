# Incident: failover promotion never fully reaches the evacuation target

Even when the build finishes, prod still does not end up serving the fresh version.

- The updater contract is derived from the active release profile and should write the prod image tag back into the prod overlay, not the retired primary target.
- Use the active lane plus the matching promotion, observability, and traffic profiles to derive the prod GitOps target state.
- The active GitOps files include the updater handoff, prod application, prod overlay values, promotion controls, and the derived prod handoff manifests.
- The resilience and observability files that must align to the active prod lane are:
  - `autoscaling-policy.yaml`
  - `availability-budget.yaml`
  - `service-monitor.yaml`
  - `alert-route.yaml`
  - `burn-rate-alert.yaml`
  - `canary-analysis.yaml`
  - `gitops-repo/tools/render_alert_policy.py`
- The traffic and mesh files that must align to the active prod lane include the traffic policy, route/mesh intent manifests, mesh resources, and the mesh helper script.
- The telemetry and workload handoffs for the prod lane must also align to the active observability and traffic profiles.
- Some of these prod overlay resources are intentionally absent from the seed. Missing prod resources should be created rather than worked around in generated live state.
