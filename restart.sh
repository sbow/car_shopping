#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCRAPE=false
PURGE=false
for arg in "$@"; do
  case "$arg" in
    --scrape|-s) SCRAPE=true ;;
    --purge|-p)  PURGE=true ;;
    *) echo "Unknown argument: $arg"; echo "Usage: $0 [--scrape] [--purge]"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# STOP
# ---------------------------------------------------------------------------
kill_port() {
  local port=$1 name=$2
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
    echo "  Stopped $name (port $port)"
  else
    echo "  $name not running"
  fi
}

echo "==> Stopping services..."
kill_port 8000 "FastAPI"
kill_port 3000 "Dashboard"
pkill -f "python -m backend.main" 2>/dev/null && echo "  Stopped scraper daemon" || true
sleep 1

# ---------------------------------------------------------------------------
# PURGE
# ---------------------------------------------------------------------------
if [ "$PURGE" = true ]; then
  echo ""
  echo "==> Purge requested."
  read -r -p "  This will delete ALL listings, estimates, and alerts. Continue? [y/N] " confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || { echo "  Aborted."; exit 0; }

  docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T postgres \
    psql -U caruser -d car_shopping \
    -c "TRUNCATE listings, depreciation_estimates, alerts_sent RESTART IDENTITY CASCADE;"
  echo "  Database purged."

  rm -f "$REPO_ROOT/backend/processor/mpg_cache.json"
  rm -f "$REPO_ROOT/backend/scraper/cargurus_ids.json"
  echo "  Caches cleared."
fi

# ---------------------------------------------------------------------------
# START
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting FastAPI..."
source "$REPO_ROOT/backend/.venv/bin/activate"
cd "$REPO_ROOT"
uvicorn backend.api.main:app --port 8000 --reload \
  > /tmp/car_shopping_api.log 2>&1 &
API_PID=$!

echo -n "  Waiting for API"
for i in $(seq 1 15); do
  if curl -sf http://localhost:8000/api/watchlist > /dev/null 2>&1; then
    echo " ready (PID $API_PID)"
    break
  fi
  echo -n "."
  sleep 1
  if [ "$i" -eq 15 ]; then
    echo ""
    echo "ERROR: FastAPI did not start. Check /tmp/car_shopping_api.log"
    exit 1
  fi
done

echo "==> Starting Dashboard..."
cd "$REPO_ROOT/frontend/dashboard"
node server.js > /tmp/car_shopping_dashboard.log 2>&1 &
DASH_PID=$!

echo -n "  Waiting for Dashboard"
for i in $(seq 1 10); do
  if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo " ready (PID $DASH_PID)"
    break
  fi
  echo -n "."
  sleep 1
  if [ "$i" -eq 10 ]; then
    echo ""
    echo "ERROR: Dashboard did not start. Check /tmp/car_shopping_dashboard.log"
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# SCRAPE
# ---------------------------------------------------------------------------
if [ "$SCRAPE" = true ]; then
  echo ""
  echo "==> Running scrape pass (this will take a few minutes)..."
  cd "$REPO_ROOT"
  python -c "
import backend.config as config, backend.db as db
from backend.scraper.runner import run as scrape
from backend.processor.depreciation import compute_all
cfg = config.load()
db.init(cfg['database_url'])
scrape(cfg)
compute_all(cfg)
"
  echo "  Scrape complete."
fi

# ---------------------------------------------------------------------------
# DONE
# ---------------------------------------------------------------------------
echo ""
echo "==> All services running."
echo "  Dashboard:  http://localhost:3000"
echo "  API:        http://localhost:8000"
echo "  API log:    /tmp/car_shopping_api.log"
echo "  Dash log:   /tmp/car_shopping_dashboard.log"
