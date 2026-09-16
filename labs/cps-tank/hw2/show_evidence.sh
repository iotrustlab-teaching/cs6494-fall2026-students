#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -ne 1 ]]; then
    echo "usage: $0 RUN_BUNDLE" >&2
    exit 2
fi
exec python3 "$here/evidence_summary.py" "$1"
