#!/usr/bin/env bash
# Start OctaOS locally: FastAPI, Celery worker, Celery beat, and Next.js.
# The Remotion video renderer stays off unless you pass --with-renderer.
#
# Usage:
#   bash scripts/run-dev.sh
#   bash scripts/run-dev.sh --with-renderer
#   bash scripts/run-dev.sh --no-worker --no-beat
#   bash scripts/run-dev.sh --no-frontend
#
# Stop everything with Ctrl+C. Logs go to $TMPDIR/octaos-dev/.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$APP_DIR/venv"
FRONTEND_DIR="$APP_DIR/frontend"
RENDERER_DIR="$APP_DIR/video-renderer"
LOG_DIR="${TMPDIR:-/tmp}/octaos-dev"

WITH_RENDERER=0
WITH_WORKER=1
WITH_BEAT=1
WITH_API=1
WITH_FRONTEND=1

usage() {
  sed -n '2,12p' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-renderer) WITH_RENDERER=1 ;;
    --no-worker) WITH_WORKER=0 ;;
    --no-beat) WITH_BEAT=0 ;;
    --no-api) WITH_API=0 ;;
    --no-frontend) WITH_FRONTEND=0 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -x "$VENV_DIR/bin/uvicorn" || ! -x "$VENV_DIR/bin/celery" ]]; then
  echo "Python environment is missing uvicorn or celery at $VENV_DIR"
  echo "Set it up with:"
  echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ "$WITH_FRONTEND" -eq 1 && ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Frontend dependencies are not installed."
  echo "  cd frontend && npm install"
  exit 1
fi

if [[ "$WITH_RENDERER" -eq 1 && ! -d "$RENDERER_DIR/node_modules" ]]; then
  echo "Video renderer dependencies are not installed."
  echo "  cd video-renderer && npm install"
  exit 1
fi

if [[ -f "$APP_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$APP_DIR/.env"
  set +a
else
  echo "No .env file at $APP_DIR/.env"
  echo "Copy .env.example to .env and fill in Postgres, Redis, and API keys."
  exit 1
fi

mkdir -p "$LOG_DIR"

if [[ "$WITH_WORKER" -eq 1 || "$WITH_BEAT" -eq 1 ]]; then
  if command -v redis-cli >/dev/null 2>&1; then
    if ! redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping >/dev/null 2>&1; then
      echo "Redis is not responding on ${REDIS_HOST:-localhost}:${REDIS_PORT:-6379}."
      echo "Start Redis before Celery, or rerun with --no-worker --no-beat."
      exit 1
    fi
  else
    echo "redis-cli is not installed; skipping the Redis check."
  fi
fi

PIDS=()

cleanup() {
  local pid
  echo
  echo "Stopping OctaOS..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  echo "Stopped. Logs remain in $LOG_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Start a command in its own process group so Ctrl+C stops reloaders and npm children.
start_job() {
  local name="$1"
  local workdir="$2"
  shift 2
  local logfile="$LOG_DIR/${name}.log"
  : >"$logfile"
  echo "Starting ${name}"
  echo "  log: ${logfile}"
  (
    cd "$workdir"
    exec python3 -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' "$@"
  ) >"$logfile" 2>&1 &
  PIDS+=("$!")
}

if [[ "$WITH_API" -eq 1 ]]; then
  start_job api "$APP_DIR" \
    "$VENV_DIR/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --reload
fi

if [[ "$WITH_WORKER" -eq 1 ]]; then
  start_job celery-worker "$APP_DIR" \
    "$VENV_DIR/bin/celery" -A app.worker.tasks worker --loglevel=info
fi

if [[ "$WITH_BEAT" -eq 1 ]]; then
  start_job celery-beat "$APP_DIR" \
    "$VENV_DIR/bin/celery" -A app.worker.tasks beat --loglevel=info
fi

if [[ "$WITH_FRONTEND" -eq 1 ]]; then
  start_job frontend "$FRONTEND_DIR" \
    npm run dev
fi

if [[ "$WITH_RENDERER" -eq 1 ]]; then
  start_job video-renderer "$RENDERER_DIR" \
    npm start
fi

sleep 2
failed=0
for pid in "${PIDS[@]}"; do
  if ! kill -0 "$pid" 2>/dev/null; then
    failed=1
  fi
done

echo
if [[ "$WITH_API" -eq 1 ]]; then
  echo "API:        http://127.0.0.1:8000"
  echo "Docs:       http://127.0.0.1:8000/docs"
fi
if [[ "$WITH_FRONTEND" -eq 1 ]]; then
  echo "Dashboard:  http://127.0.0.1:3000"
fi
if [[ "$WITH_RENDERER" -eq 1 ]]; then
  echo "Renderer:   http://127.0.0.1:${PORT:-8002}"
fi
echo
echo "Press Ctrl+C to stop."

if [[ "$failed" -eq 1 ]]; then
  echo
  echo "One or more processes exited immediately. Check logs in $LOG_DIR"
fi

wait
