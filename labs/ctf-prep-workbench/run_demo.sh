#!/bin/sh
set -eu
cd "$(dirname "$0")"

case "${1:-serve}" in
  serve)
    port="${PORT:-8766}"
    printf 'Utility OT Security Workbench: http://127.0.0.1:%s/\n' "$port"
    exec python3 -m http.server "$port" --bind 127.0.0.1
    ;;
  check)
    python3 tests/check_fixture.py
    if command -v node >/dev/null 2>&1; then node tests/check_policy.js; fi
    if command -v node >/dev/null 2>&1; then node tests/check_scenario.js; fi
    ;;
  rebuild)
    python3 tools/build_fixture.py
    ;;
  *)
    printf 'Usage: %s [serve|check|rebuild]\n' "$0" >&2
    exit 2
    ;;
esac
