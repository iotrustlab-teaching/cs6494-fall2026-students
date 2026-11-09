#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -n "${HW4_PYTHON:-}" ]; then
  PYTHON="$HW4_PYTHON"
elif [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
else
  echo 'Run sh ./setup.sh first, or set HW4_PYTHON to a tested Python 3.12 environment.' >&2
  exit 2
fi
exec "$PYTHON" server.py --port "${HW4_PORT:-8765}"
