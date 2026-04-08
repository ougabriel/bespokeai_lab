# Tenant Ops Release Recovery

The release candidate in `/app` is a small internal API used by an ops dashboard. It is currently broken.

Repair the application so that all of the following are true:

- `python /app/bin/bootstrap_data.py` completes successfully.
- Running the bootstrap command multiple times is safe and does not duplicate data.
- `python /app/bin/run_server.py` starts the API successfully.
- `GET /health` returns HTTP 200.
- `GET /reports/{tenant}/{YYYY-MM-DD}` returns the correct daily report for the seed data in `/app/data/job_runs.jsonl`.

The daily report rules are:

- A logical job is identified by the pair `(tenant, job_id)`.
- For each logical job, identify the most recent attempt across the entire dataset before filtering to the requested report date.
- "Most recent" means the row with the latest `finished_at` in UTC. If two rows have the same `finished_at`, the one with the larger `attempt_number` wins.
- The report date is based on `finished_at` in UTC.
- Status matching must ignore case and leading/trailing whitespace.
- The response body must include:
  - `tenant`
  - `report_date`
  - `successful_jobs`
  - `failed_jobs`
  - `total_jobs`
  - `total_runtime_seconds`
  - `success_rate`
- `success_rate` must be rounded to 3 decimal places.
- When no jobs match a tenant/date combination, the API should return HTTP 404.

Do not hardcode answers or add new seed data. Fix the implementation itself.
