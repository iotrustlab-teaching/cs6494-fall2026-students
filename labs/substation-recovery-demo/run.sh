#!/bin/sh
set -eu

exec "$(dirname "$0")/run_demo.sh" serve "$@"
