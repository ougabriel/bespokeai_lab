#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_USER="$(awk -F: '$3 >= 1000 && $1 != "nobody" { print $1; exit }' /etc/passwd || true)"
RUNTIME_ROOT="${ROOT_DIR}/data/runtime"

mkdir -p /app
rm -rf /app/app /app/bin /app/config /app/data /app/state
cp -R "${RUNTIME_ROOT}/app" /app/app
cp -R "${RUNTIME_ROOT}/bin" /app/bin
cp -R "${RUNTIME_ROOT}/config" /app/config
cp -R "${ROOT_DIR}/data" /app/data
rm -rf /app/data/runtime
mkdir -p /app/state

export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export PYTHONPATH=/app

ln -sf /usr/bin/python3 /usr/local/bin/python || true
chmod +x /app/bin/bootstrap_data.py /app/bin/run_server.py /app/bin/simulate_rollout.py /app/bin/task_entrypoint.sh

if [ -n "${TASK_USER}" ] && id "${TASK_USER}" >/dev/null 2>&1; then
    chown -R "${TASK_USER}:${TASK_USER}" /app
fi
chmod -R u+rwX,go+rX /app
chmod -R a+w /app/data /app/state

python /app/bin/bootstrap_data.py >/tmp/gitops-blackout-cascade-bootstrap.json

if [ -n "${TASK_USER}" ] && id "${TASK_USER}" >/dev/null 2>&1; then
    chown -R "${TASK_USER}:${TASK_USER}" /app
fi
chmod -R a+w /app/data /app/state
