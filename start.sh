#!/usr/bin/env bash
# ─────────────────────────────────────────────────────
# YT Private Suite — Local Launcher (Linux / macOS)
# Starts both backend + frontend from source.
# ─────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║   YT Private Suite – Local Launcher     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Backend ──────────────────────────────────────
echo "[1/2] Starting backend on http://localhost:8005 ..."
cd "$SCRIPT_DIR/backend"

# Create virtualenv if missing
if [ ! -d venv ]; then
  echo "       Creating Python virtualenv ..."
  python3 -m venv venv
fi
source venv/bin/activate

# Install deps if needed
pip install -q -r requirements.txt

# Start uvicorn in background
uvicorn main:app --host 127.0.0.1 --port 8005 &
BACKEND_PID=$!
echo "       Backend PID: $BACKEND_PID"
cd "$SCRIPT_DIR"

# ── Frontend ─────────────────────────────────────
echo "[2/2] Starting frontend on http://localhost:8080 ..."
cd "$SCRIPT_DIR/frontend"

if [ ! -d node_modules ]; then
  echo "       Installing npm dependencies (one-time) ..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "       Frontend PID: $FRONTEND_PID"
cd "$SCRIPT_DIR"

echo ""
echo "┌──────────────────────────────────────────┐"
echo "│  Backend  → http://localhost:8005        │"
echo "│  Frontend → http://localhost:8080        │"
echo "│                                          │"
echo "│  Open http://localhost:8080 in browser   │"
echo "│  Press Ctrl+C to stop everything         │"
echo "└──────────────────────────────────────────┘"
echo ""

# Trap Ctrl+C to kill both processes
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# Wait for either to exit
wait
