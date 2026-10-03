#!/bin/sh
set -eu
cd "$(dirname "$0")"

case "${1:-serve}" in
  serve)
    port="${PORT:-8766}"
    printf 'CTF Prep Workbench: http://127.0.0.1:%s/\n' "$port"
    exec python3 -m http.server "$port" --bind 127.0.0.1
    ;;
  check)
    python3 tests/check_fixture.py
    ;;
  rebuild)
    python3 tools/build_fixture.py
    ;;
  *)
    printf 'Usage: %s [serve|check|rebuild]\n' "$0" >&2
    exit 2
    ;;
esac
