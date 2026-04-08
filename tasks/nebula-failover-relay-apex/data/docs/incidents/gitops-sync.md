# Incident: failover promotion never fully reaches the evacuation target

Even when the build finishes, prod still does not end up serving the fresh version.

- The updater contract is derived from the active release profile and should write the prod image tag back into the prod overlay, not the retired primary target.
- Use the active lane plus the matching promotion, observability, and traffic profiles to derive the prod GitOps target state.
- The active GitOps state is broader than the application and overlay values. Promotion controls, helper outputs, and downstream prod handoffs all need to agree on the same lane contract.
- If promotion appears healthy but the later stages still drift, assume one of the derived prod handoffs is stale or missing.
- The resilience, observability, traffic, mesh, workload, and telemetry resources all depend on the same lane contract even though they fail at different times.
- Some of these prod overlay resources are intentionally absent from the seed. Missing prod resources should be created rather than worked around in generated live state.
