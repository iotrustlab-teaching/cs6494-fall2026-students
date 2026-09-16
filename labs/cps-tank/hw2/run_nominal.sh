#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${HW2_TRANSPORT:-}" == "modbus_tcp" ]]; then
    exec "$here/run_modbus_nominal.sh" "$@"
fi
exec "$here/run_case.sh" nominal "$@"
