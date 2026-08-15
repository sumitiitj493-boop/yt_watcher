#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "+------------------------------------------+"
echo "|   YT Private Suite - Local Launcher      |"
echo "+------------------------------------------+"
echo

cleanup() {
  echo
  echo "Shutting down..."
  if [ "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup INT TERM EXIT

echo "[1/2] Starting backend on http://localhost:8000 ..."
cd "$BACKEND_DIR"

if [ ! -d venv ]; then
  echo "       Creating Python virtualenv ..."
  python3 -m venv venv
fi

source venv/bin/activate
python -m pip install -q -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
echo "       Backend PID: $BACKEND_PID"

echo "[2/2] Starting frontend on http://localhost:8080 ..."
cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
  echo "       Installing npm dependencies one time ..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "       Frontend PID: $FRONTEND_PID"

echo
echo "+------------------------------------------+"
echo "|  Backend  - http://localhost:8000        |"
echo "|  Frontend - http://localhost:8080        |"
echo "|                                          |"
echo "|  Open http://localhost:8080 in browser   |"
echo "|  Press Ctrl+C to stop everything         |"
echo "+------------------------------------------+"
echo

wait
