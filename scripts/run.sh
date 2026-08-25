#!/bin/sh
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export STATIC_DIR="$ROOT/web/static"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

.venv/bin/python -m terminal &
PY_PID=$!
trap 'kill $PY_PID 2>/dev/null || true' EXIT

i=0
until curl -sf http://127.0.0.1:8081/api/health >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 40 ]; then
    echo "Python API не поднялся на :8081"
    exit 1
  fi
  sleep 0.25
done

cd "$ROOT/web"
go run .
