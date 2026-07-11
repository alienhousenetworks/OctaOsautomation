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

case "$1" in
  makemigrations)
    # Equivalent to Django's `python manage.py makemigrations`
    # It reads your SQLAlchemy models and automatically generates the alter/create/drop SQL
    MSG="${2:-auto_migration}"
    echo "Generating new database migrations for: $MSG"
    "$VENV_DIR/bin/alembic" revision --autogenerate -m "$MSG"
    ;;
    
  migrate)
    # Equivalent to Django's `python manage.py migrate`
    # It applies all pending migrations to the database
    echo "Applying pending migrations to the database..."
    # Use `heads` so a temporary multi-head graph still applies (merge if needed).
    # Prefer single `head` when graph is linear.
    HEADS_COUNT=$("$VENV_DIR/bin/alembic" heads 2>/dev/null | wc -l | tr -d ' ')
    if [[ "${HEADS_COUNT:-0}" -gt 1 ]]; then
      echo "WARNING: multiple Alembic heads detected ($HEADS_COUNT). Upgrading all heads."
      echo "Heads:"
      "$VENV_DIR/bin/alembic" heads || true
      "$VENV_DIR/bin/alembic" upgrade heads
    else
      "$VENV_DIR/bin/alembic" upgrade head
    fi
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

  stamp)
    # Force-set alembic_version without running SQL.
    # Use when DB points at a deleted local revision (e.g. old auto_deploy_update).
    # Example: bash scripts/manage.sh stamp 9a1b2c3d4e5f
    TARGET="${2:-}"
    if [[ -z "$TARGET" ]]; then
      echo "Usage: bash scripts/manage.sh stamp <revision_id>"
      echo "  Common: stamp 9a1b2c3d4e5f   then: migrate"
      exit 1
    fi
    echo "Stamping database to revision: $TARGET"
    "$VENV_DIR/bin/alembic" stamp "$TARGET"
    ;;

  fix-orphan-revision)
    # Recover when alembic_version points at a missing file (deleted auto_deploy junk).
    # Resets stamp to last known git revision before enterprise, then upgrades.
    # SAFE: does not drop data; only rewrites alembic_version row + applies pending SQL.
    FALLBACK="${2:-9a1b2c3d4e5f}"
    echo "Attempting orphan revision recovery..."
    echo "  1) Stamp to fallback git revision: $FALLBACK"
    if ! "$VENV_DIR/bin/alembic" stamp "$FALLBACK"; then
      echo "alembic stamp failed (common when current rev file is missing)."
      echo "Falling back to direct SQL update of alembic_version..."
      # shellcheck disable=SC1091
      if [[ -f "$APP_DIR/.env" ]]; then set -a; source "$APP_DIR/.env"; set +a; fi
      DB_URL="${SQLALCHEMY_DATABASE_URI:-}"
      if [[ -z "$DB_URL" ]]; then
        DB_URL="postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-password}@${POSTGRES_SERVER:-localhost}/${POSTGRES_DB:-octaos}"
      fi
      "$VENV_DIR/bin/python3" - <<PY
import sys
from sqlalchemy import create_engine, text
url = """${DB_URL}"""
engine = create_engine(url)
with engine.begin() as conn:
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": "${FALLBACK}"})
    print("alembic_version set to ${FALLBACK}")
PY
    fi
    echo "  2) Upgrade to head..."
    "$VENV_DIR/bin/alembic" upgrade head
    echo "Recovery complete. Current:"
    "$VENV_DIR/bin/alembic" current || true
    ;;
    
  *)
    echo "Usage:"
    echo "  bash scripts/manage.sh makemigrations [optional_description_with_no_spaces]"
    echo "  bash scripts/manage.sh migrate"
    echo "  bash scripts/manage.sh heads"
    echo "  bash scripts/manage.sh current"
    echo "  bash scripts/manage.sh history"
    echo "  bash scripts/manage.sh stamp <revision>"
    echo "  bash scripts/manage.sh fix-orphan-revision [fallback_rev]"
    ;;
esac
