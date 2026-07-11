#!/usr/bin/env bash
# =============================================================================
#  OctaOS – Fast Production Update & Redeploy Script
#  Usage: sudo bash updatedeploy.sh
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}━━━ $* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ── Paths & constants ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"  # repo root is one level above scripts/
ENV_FILE="$APP_DIR/.env"
VENV_DIR="$APP_DIR/venv"
FRONTEND_DIR="$APP_DIR/frontend"
RENDERER_DIR="$APP_DIR/video-renderer"
LOG_DIR="/var/log/octaos"

# ── Must-run-as-root check ────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
  error "Please run as root:  sudo bash scripts/updatedeploy.sh"
fi

# =============================================================================
# 1. Load Env Vars
# =============================================================================
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  success "Loaded configuration from .env"
else
  error ".env file not found at $ENV_FILE. Please run scripts/deploy.sh first."
fi

# =============================================================================
# 2. Git Pull Latest Changes
# =============================================================================
header "Pulling Latest Code"
cd "$APP_DIR"

if git rev-parse --git-dir &>/dev/null; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  info "Updating Git remote origin URL..."
  git remote set-url origin https://github.com/alienhousenetworks/OctaOsautomation.git || warn "Failed to update Git remote origin URL"
  info "Fetching latest changes from Git..."
  git fetch --all
  BEFORE=$(git rev-parse HEAD)
  info "Pulling latest from branch: $BRANCH"
  if ! git pull origin "$BRANCH"; then
    warn "Git pull failed. You might have uncommitted local changes on the VPS."
    warn "To overwrite local changes and pull:  git reset --hard origin/$BRANCH"
    warn "Continuing deployment with existing code..."
  else
    AFTER=$(git rev-parse HEAD)
    success "Code pulled successfully"
    if [[ "$BEFORE" != "$AFTER" ]]; then
      info "Changed files in this update:"
      git diff --name-only "$BEFORE" "$AFTER" | while read -r f; do
        if [[ "$f" == frontend/* ]]; then
          echo -e "  ${CYAN}[FRONTEND]${NC} $f"
        else
          echo -e "  ${YELLOW}[BACKEND]${NC}  $f"
        fi
      done
    else
      info "No new commits – code is already up-to-date"
    fi
  fi
else
  warn "Not a git repository – skipping pull"
fi

# =============================================================================
# 3. Update Backend Dependencies & Migrations
# =============================================================================
header "Updating Backend"

if [[ -d "$VENV_DIR" ]]; then
  info "Installing/updating Python dependencies..."
  "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" -q
  success "Python dependencies updated"
  
  info "Running database cleanup and migration..."
  cd "$APP_DIR"
  if [[ -f "$APP_DIR/cleanup_tenants.py" ]]; then
    "$VENV_DIR/bin/python3" "$APP_DIR/cleanup_tenants.py" || warn "cleanup_tenants.py failed"
  fi

  # IMPORTANT: Do NOT autogenerate migrations on the VPS.
  # `alembic revision --autogenerate` on production creates local-only revision
  # files that fork the graph → "Multiple head revisions" on the next deploy.
  # Migrations are authored in git and applied here only.
  chmod +x "$SCRIPT_DIR/manage.sh"

  # Drop untracked auto-generated migration junk from older deploys (keep git-tracked only)
  if [[ -d "$APP_DIR/alembic/versions" ]]; then
    info "Checking for untracked local Alembic revisions..."
    while IFS= read -r -d '' f; do
      warn "Removing untracked local migration (not in git): $f"
      rm -f "$f"
    done < <(cd "$APP_DIR" && git ls-files --others --exclude-standard 'alembic/versions/*.py' -z 2>/dev/null || true)
  fi

  info "Alembic heads before migrate:"
  "$SCRIPT_DIR/manage.sh" heads || true
  info "Alembic current DB revision:"
  "$SCRIPT_DIR/manage.sh" current || true

  info "Applying database migrations from git..."
  "$SCRIPT_DIR/manage.sh" migrate || error "Migrations failed!"

  if [[ -f "$APP_DIR/init_db.py" ]]; then
    "$VENV_DIR/bin/python3" "$APP_DIR/init_db.py" || warn "init_db.py had warnings (may be safe to ignore)"
  fi
  success "Database migrations completed"
else
  error "Virtualenv not found at $VENV_DIR. Please run deploy.sh first."
fi

# =============================================================================
# 4. Rebuild Next.js Frontend
# =============================================================================
header "Updating & Building Frontend"

if [[ -d "$FRONTEND_DIR" ]]; then
  cd "$FRONTEND_DIR"
  
  # Ensure frontend .env.local has the correct API URL.
  # Derives from NEXT_PUBLIC_API_URL if set in .env, otherwise falls back to PUBLIC_BASE_URL/api/v1
  RESOLVED_API_URL="${NEXT_PUBLIC_API_URL:-${PUBLIC_BASE_URL:-}/api/v1}"
  if [[ -z "$RESOLVED_API_URL" || "$RESOLVED_API_URL" == "/api/v1" ]]; then
    error "Neither NEXT_PUBLIC_API_URL nor PUBLIC_BASE_URL is set in .env – cannot build frontend correctly."
  fi
  cat > "$FRONTEND_DIR/.env.local" <<EOF
NEXT_PUBLIC_API_URL=${RESOLVED_API_URL}
EOF
  info "Frontend API URL set to: $RESOLVED_API_URL"

  info "Installing frontend dependencies..."
  npm ci --silent || npm install --silent
  
  info "Building Next.js production bundle (optimized for RAM size)..."
  NODE_OPTIONS="--max-old-space-size=1024" npm run build
  success "Frontend build completed"
  
  # Copy static assets for Next.js standalone runner if standalone directory exists
  NODE_BIN="$(which node)"
  if [[ -d "$FRONTEND_DIR/.next/standalone" ]]; then
    info "Next.js standalone structure found. Copying static files..."
    cp -r "$FRONTEND_DIR/.next/static"   "$FRONTEND_DIR/.next/standalone/.next/static"   2>/dev/null || true
    cp -r "$FRONTEND_DIR/public"         "$FRONTEND_DIR/.next/standalone/public"          2>/dev/null || true
    success "Next.js standalone assets copied"
  fi
else
  warn "Frontend directory not found at $FRONTEND_DIR – skipping frontend build"
fi

# =============================================================================
# 4.5 Update Node.js Video Renderer
# =============================================================================
header "Updating Video Renderer"

if [[ -d "$RENDERER_DIR" ]]; then
  cd "$RENDERER_DIR"
  info "Installing video-renderer dependencies..."
  npm install --silent
  success "Video renderer dependencies installed"
else
  info "Video renderer not found – skipping"
fi

# Always return to APP_DIR after frontend work
cd "$APP_DIR"

# =============================================================================
# 5. Restart Systemd Services & Nginx
# =============================================================================
header "Restarting Services"

info "Restarting OctaOS systemd services..."
for svc in octaos-api octaos-worker octaos-beat octaos-frontend octaos-video-renderer; do
  if systemctl restart "$svc" 2>/dev/null; then
    success "$svc restarted"
  else
    warn "Service $svc could not be restarted (may not be registered)"
  fi
done

info "Restarting Nginx..."
if nginx -t; then
  systemctl restart nginx
  success "Nginx restarted"
else
  warn "Nginx config test failed – skipping restart"
fi

# =============================================================================
# 6. Health Check
# =============================================================================
header "Health Check"
sleep 3

check_service() {
  if systemctl is-active --quiet "$1"; then
    success "$1 is active and running ✓"
  else
    warn "$1 is NOT running – check: journalctl -u $1 -n 50"
  fi
}

for svc in postgresql redis-server nginx octaos-api octaos-worker octaos-beat octaos-frontend; do
  check_service "$svc"
done

# HTTP smoke test – retry for up to 30 seconds (uvicorn takes a few seconds with 4 workers)
BACKEND_OK=false
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf "http://localhost:8001/" > /dev/null 2>&1; then
    BACKEND_OK=true
    break
  fi
  sleep 3
done

if $BACKEND_OK; then
  success "Backend API responding ✓"
else
  warn "Backend API not responding after 30s – check: journalctl -u octaos-api -n 50"
fi

if curl -sf "http://localhost:3001/" > /dev/null 2>&1; then
  success "Frontend responding ✓"
else
  warn "Frontend not responding yet"
fi

echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  OctaOS Update & Redeploy Successful!${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
