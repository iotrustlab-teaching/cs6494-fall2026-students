#!/bin/sh
# One command per reproducible, isolated public-source practice flight.
set -eu
cd "$(dirname "$0")"

case_name=${1:-}
if [ "$case_name" != all ] && [ "$case_name" != clean-starter ] && \
   [ "$case_name" != attack-starter ] && [ "$case_name" != attack-student ] && \
   [ "$case_name" != clean-student ]; then
  echo 'Usage: ./run.sh {clean-starter|attack-starter|attack-student|clean-student|all}' >&2
  exit 2
fi
command -v docker >/dev/null 2>&1 || {
  echo 'Docker is required. Start Docker Desktop, then retry.' >&2
  exit 2
}
docker compose version >/dev/null
mkdir -p runs
docker compose config --quiet

run_one() {
  label=$1
  echo "Starting isolated $label flight (ArduPilot SITL + Gazebo Harmonic)."
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  docker compose up --build -d sim
  result=0
  docker compose exec -T sim python3 /lab/runner.py --case "$label" || result=$?
  if [ "$result" -ne 0 ]; then
    echo "Flight runner failed for $label; container logs follow." >&2
    docker compose logs --tail=80 sim >&2 || true
  fi
  docker compose down --remove-orphans
  return "$result"
}

if [ "$case_name" = all ]; then
  for label in clean-starter attack-starter attack-student clean-student; do
    run_one "$label" || exit $?
  done
else
  run_one "$case_name"
fi

echo 'Evidence receipts are in ./runs/*.summary.json, *.jsonl, and *.route.svg.'
