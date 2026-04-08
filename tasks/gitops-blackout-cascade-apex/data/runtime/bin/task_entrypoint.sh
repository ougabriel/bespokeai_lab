#!/usr/bin/env sh
set -eu

if [ "$#" -eq 0 ]; then
    exec /bin/bash
fi

exec "$@"
