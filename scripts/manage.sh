#!/bin/bash
# Django-like wrapper for database migrations
# Can be run from the repo root OR from the scripts/ subdirectory.

# Resolve the repo root (one level up if this script lives in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"  # repo root is one level above scripts/

VENV_DIR="$APP_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    exit 1
fi

# Alembic must be run from the repo root so it finds alembic.ini
cd "$APP_DIR"

# Load .env so POSTGRES_* / SQLALCHEMY_DATABASE_URI are available
if [[ -f "$APP_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$APP_DIR/.env"
  set +a
fi

case "$1" in
  makemigrations)
    # Dev only — do NOT run on production deploy
    MSG="${2:-auto_migration}"
    echo "Generating new database migrations for: $MSG"
    echo "WARNING: Do not run this on the VPS. Migrations should be committed in git."
    "$VENV_DIR/bin/alembic" revision --autogenerate -m "$MSG"
    ;;

  migrate)
    # Production-safe migrate: uses .env password automatically, fixes orphan stamps
    echo "Applying database migrations (safe mode)..."
    "$VENV_DIR/bin/python3" "$SCRIPT_DIR/fix_alembic_and_migrate.py"
    ;;

  heads)
    "$VENV_DIR/bin/alembic" heads -v
    ;;

  current)
    "$VENV_DIR/bin/alembic" current -v
    ;;

  history)
    "$VENV_DIR/bin/alembic" history
    ;;

  show-db-password)
    # Print DB connection info from .env (password masked unless --show)
    if [[ "${2:-}" == "--show" ]]; then
      echo "POSTGRES_USER=${POSTGRES_USER:-}"
      echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-}"
      echo "POSTGRES_DB=${POSTGRES_DB:-}"
      echo "POSTGRES_SERVER=${POSTGRES_SERVER:-}"
    else
      echo "POSTGRES_USER=${POSTGRES_USER:-}"
      echo "POSTGRES_PASSWORD=******** (run: bash scripts/manage.sh show-db-password --show)"
      echo "POSTGRES_DB=${POSTGRES_DB:-}"
      echo "POSTGRES_SERVER=${POSTGRES_SERVER:-}"
    fi
    ;;

  stamp)
    TARGET="${2:-}"
    if [[ -z "$TARGET" ]]; then
      echo "Usage: bash scripts/manage.sh stamp <revision_id>"
      exit 1
    fi
    echo "Stamping database to revision: $TARGET"
    "$VENV_DIR/bin/alembic" stamp "$TARGET" || \
      "$VENV_DIR/bin/python3" -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
e=create_engine(settings.SQLALCHEMY_DATABASE_URI)
with e.begin() as c:
    c.execute(text('DELETE FROM alembic_version'))
    c.execute(text('INSERT INTO alembic_version (version_num) VALUES (:v)'), {'v': '$TARGET'})
print('stamped $TARGET via SQL')
"
    ;;

  fix-orphan-revision)
    # Same as migrate safe path
    "$VENV_DIR/bin/python3" "$SCRIPT_DIR/fix_alembic_and_migrate.py"
    ;;

  *)
    echo "Usage:"
    echo "  bash scripts/manage.sh migrate"
    echo "  bash scripts/manage.sh heads | current | history"
    echo "  bash scripts/manage.sh show-db-password [--show]"
    echo "  bash scripts/manage.sh stamp <revision>"
    echo "  bash scripts/manage.sh fix-orphan-revision"
    echo "  bash scripts/manage.sh makemigrations [msg]   # DEV ONLY"
    ;;
esac
