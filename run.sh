#!/bin/sh
# Robot Console for macOS and Linux: creates .venv on first start, then opens the app.
# Extra options are passed through, e.g.  ./run.sh --no-hardware
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if [ ! -x .venv/bin/python ]; then
  echo "Creazione ambiente Python in .venv…"
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python robot_console.py "$@"
