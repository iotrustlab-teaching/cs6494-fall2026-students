#!/bin/sh
set -eu
cd "$(dirname "$0")"
if ! command -v python3.12 >/dev/null 2>&1; then
  echo 'Python 3.12 is required for the tested package versions. Install it before running setup.' >&2
  exit 2
fi
python3.12 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-tooling.txt
.venv/bin/python -c 'import importlib.metadata as m; print("Ready: psy-taliro",m.version("psy-taliro"),"RTAMT",m.version("rtamt"))'
