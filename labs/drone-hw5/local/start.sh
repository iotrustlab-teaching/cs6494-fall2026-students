#!/bin/sh
set -eu
mkdir -p /runs
cd /runs
gz sim -s -r -v 3 /opt/ardupilot_gazebo/worlds/iris_runway.sdf > /runs/gazebo.log 2>&1 &
gz_pid=$!
trap 'kill "$gz_pid" 2>/dev/null || true' EXIT INT TERM
ready=0
for i in $(seq 1 60); do
  if ! kill -0 "$gz_pid" 2>/dev/null; then
    cat /runs/gazebo.log >&2
    exit 1
  fi
  if gz topic -l 2>/dev/null | grep -q '/world/iris_runway/clock'; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  cat /runs/gazebo.log >&2
  echo 'Gazebo world did not become ready within 60 s' >&2
  exit 1
fi
exec /usr/local/bin/arducopter -w -I0 --model JSON \
  --home=-35.363262,149.165237,584,0 \
  --defaults=/lab/gazebo-iris.parm
