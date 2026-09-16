#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${HW2_TRANSPORT:-}" == "modbus_tcp" ]]; then
    exec python3 "$here/modbus_reset.py"
fi
exec python3 "$here/hw2_lab.py" reset
