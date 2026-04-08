#!/bin/bash
set -euo pipefail

set +e
python -m pytest /tests/test_outputs.py -q
status=$?
set -e

if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
