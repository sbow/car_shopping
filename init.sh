#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Checking requirements..."

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.11+." && exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if python3 -c 'import sys; assert sys.version_info >= (3,11)' 2>/dev/null; then
  echo "  Python $PYTHON_VER OK"
else
  echo "ERROR: Python 3.11+ required (found $PYTHON_VER)." && exit 1
fi

if ! command -v node &>/dev/null; then
  echo "ERROR: node not found. Install Node.js 18+." && exit 1
fi
echo "  Node $(node --version) OK"

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker not found. Install Docker." && exit 1
fi
echo "  Docker OK"

if ! docker compose version &>/dev/null 2>&1; then
  echo "ERROR: 'docker compose' (v2) not found." && exit 1
fi
echo "  Docker Compose OK"

# .env setup
if [ ! -f "$REPO_ROOT/.env" ]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo ""
  echo "==> Created .env from .env.example"
  echo "    Edit $REPO_ROOT/.env and fill in your credentials before continuing."
  echo "    Then re-run ./init.sh"
  exit 0
fi

# config.toml setup
if [ ! -f "$REPO_ROOT/config.toml" ]; then
  cp "$REPO_ROOT/config.toml.example" "$REPO_ROOT/config.toml"
  echo ""
  echo "==> Created config.toml from config.toml.example"
  echo "    Edit $REPO_ROOT/config.toml to set your target vehicles and preferences."
fi

echo ""
echo "==> Setting up Python venv..."
cd "$REPO_ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
playwright install chromium 2>/dev/null || true
echo "  Python venv ready."

echo ""
echo "==> Installing Node.js dependencies..."
cd "$REPO_ROOT/frontend/dashboard"
npm install --silent
echo "  Node modules ready."

echo ""
echo "==> Starting PostgreSQL via Docker Compose..."
cd "$REPO_ROOT"
docker compose up -d
echo "  Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U caruser &>/dev/null; then
    echo "  Postgres ready."
    break
  fi
  sleep 1
done

echo ""
echo "==> Running database migrations..."
for sql in "$REPO_ROOT/db/migrations/"*.sql; do
  echo "  Applying $(basename "$sql")..."
  docker compose exec -T postgres psql -U caruser -d car_shopping -f - < "$sql"
done

echo ""
echo "==> Done!"
echo ""
echo "Start the backend scraper:   source backend/.venv/bin/activate && python -m backend.main"
echo "Start the API server:        source backend/.venv/bin/activate && uvicorn backend.api.main:app --reload"
echo "Start the dashboard:         cd frontend/dashboard && node server.js"
echo "Dashboard URL:               http://localhost:3000"
