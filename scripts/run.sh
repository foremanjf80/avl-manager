#!/usr/bin/env bash
# Launch the dev server. Usage: ./scripts/run.sh [port]
#
# Exists because the two ways this fails look nothing like their cause:
# a bare "uvicorn" outside the venv resolves to the system Python and dies on
# "No module named 'fastapi'", and a server left over from a previous run dies
# on "Address already in use" no matter how correct the command is.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${1:-8000}"

if [ ! -x .venv/bin/uvicorn ]; then
    echo "No .venv here. Create it first:" >&2
    echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

if [ -f .env ]; then
    set -a; . ./.env; set +a          # handles values with spaces or '#'
else
    echo "warning: no .env - copy .env.example and set SECRET_KEY" >&2
fi

# Whoever holds the port is almost always our own last run.
holder=$(ss -lptnH "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
if [ -n "$holder" ]; then
    echo "Port $PORT is held by pid $holder:" >&2
    ps -o pid=,cmd= -p "$holder" >&2
    read -rp "Stop it and take the port? [y/N] " ans
    case "$ans" in
        [yY]*) kill "$holder"
               for _ in $(seq 20); do
                   ss -lptnH "sport = :$PORT" 2>/dev/null | grep -q . || break
                   sleep 0.25
               done ;;
        *) echo "Leaving it. Pick another port: ./scripts/run.sh $((PORT+1))" >&2
           exit 1 ;;
    esac
fi

echo "http://localhost:$PORT"
exec .venv/bin/uvicorn app.main:app --reload --port "$PORT"
