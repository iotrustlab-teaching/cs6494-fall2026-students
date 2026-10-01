#!/bin/sh
set -eu

demo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$demo_dir"

command=${1:-serve}
if [ "$#" -gt 0 ]; then
  shift
fi

case "$command" in
  serve)
    exec python3 server.py --host 127.0.0.1 --port "${PORT:-8765}" "$@"
    ;;
  serve-openplc)
    exec python3 server.py --host 127.0.0.1 --port "${PORT:-8765}" \
      --controller-backend openplc "$@"
    ;;
  check)
    python3 -m unittest discover -s tests -v
    ;;
  rehearse)
    exec python3 rehearse.py "$@"
    ;;
  *)
    echo "usage: $0 [serve|serve-openplc|check|rehearse]" >&2
    exit 2
    ;;
esac
