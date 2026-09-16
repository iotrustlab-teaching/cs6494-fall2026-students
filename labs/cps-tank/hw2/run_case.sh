#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case_name="${1:-}"
if [[ -z "$case_name" ]]; then
    echo "usage: $0 nominal|sensor_spoof [additional options]" >&2
    exit 2
fi
shift
exec python3 "$here/hw2_lab.py" run "$case_name" "$@"
