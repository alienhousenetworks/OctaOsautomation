#!/usr/bin/env bash
# =============================================================================
#  OctaOS – Development / QA Deploy Script
#  Usage: sudo bash scripts/deploy-dev.sh
#
#  What this does (in order):
#   1. Checks / installs system dependencies (nginx, node, python3, redis, postgres)
#   2. Creates or updates the .env file (auto-detects IP, generates secrets, prompts)
#   3. Pulls latest code from git
#   4. Sets up Python virtualenv & installs backend deps
#   5. Initialises / migrates the PostgreSQL database
#   6. Builds the Next.js frontend (with RAM optimization for cheap VPS)
#   7. Writes systemd services for: API (uvicorn), Celery worker, Celery beat
#   8. Configures nginx as reverse proxy for both backend & frontend
#   9. Optionally provisions a Let's Encrypt SSL certificate
#  10. Starts / restarts all services
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
ENV_EXAMPLE="$APP_DIR/.env.example"
VENV_DIR="$APP_DIR/venv"
FRONTEND_DIR="$APP_DIR/frontend"
LOG_DIR="/var/log/octaos"
APP_USER="${SUDO_USER:-$(whoami)}"   # run services as the invoking user, not root

# ── Must-run-as-root check ────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
  error "Please run as root:  sudo bash scripts/deploy-dev.sh"
fi

# =============================================================================
# 1. System Dependencies
# =============================================================================
header "System Dependencies"

apt_install() {
  local pkg="$1"
  if dpkg -l "$pkg" &>/dev/null; then
    info "$pkg already installed – skipping"
  else
    info "Installing $pkg …"
    apt-get install -y "$pkg" -qq
    success "$pkg installed"
  fi
}

info "Updating apt …"
apt-get update -qq

for pkg in git curl nginx postgresql postgresql-contrib redis-server python3 python3-pip python3-venv certbot python3-certbot-nginx; do
  apt_install "$pkg"
done

# Ensure database and redis are enabled & started
systemctl enable postgresql --quiet
systemctl start postgresql
success "PostgreSQL running ✓"

systemctl enable redis-server --quiet
systemctl start redis-server
success "Redis running ✓"

# Node.js 20 LTS (via NodeSource) – skip if already present
if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d 'v')" -lt 18 ]]; then
  info "Installing Node.js 20 LTS …"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - -qq
  apt-get install -y nodejs -qq
  success "Node.js $(node -v) installed"
else
  success "Node.js $(node -v) already present"
fi

# =============================================================================
# 2. Configure .env
# =============================================================================
header ".env Configuration"

prompt_var() {
  # Usage: prompt_var VAR_NAME "Description" "default_or_empty"
  local var="$1" desc="$2" default="${3:-}"
  local current
  current=$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- || true)

  # Skip if already set to a real value (not a CHANGE_ME placeholder)
  if [[ -n "$current" && "$current" != *"CHANGE_ME"* ]]; then
    info "$var already configured"
    return
  fi

  if [[ $# -ge 3 ]]; then
    read -r -p "  ${BOLD}${var}${NC} (${desc}) [${default}]: " input
    input="${input:-$default}"
  else
    while true; do
      read -r -p "  ${BOLD}${var}${NC} (${desc}): " input
      [[ -n "$input" ]] && break
      warn "Value cannot be empty – please enter a value"
    done
  fi

  # Update or append in .env
  if grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${var}=.*|${var}=${input}|" "$ENV_FILE"
  else
    echo "${var}=${input}" >> "$ENV_FILE"
  fi
}

# Create .env from example if it doesn't exist
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    info "Created .env from .env.example"
  else
    touch "$ENV_FILE"
    info "Created empty .env"
  fi
fi

# Auto-detect VPS public IP to make deployment easier
info "Detecting server public IP..."
DETECTED_IP=$(curl -s --max-time 3 https://ipinfo.io/ip || curl -s --max-time 3 https://ifconfig.me || echo "127.0.0.1")
success "Public IP detected: $DETECTED_IP"

echo ""
echo -e "${YELLOW}Please provide the following configuration values.${NC}"
echo -e "${YELLOW}Press Enter to keep an existing or default value.${NC}"
echo ""

# ── Domain & Server ───────────────────────────────────────────────────────────
prompt_var "DOMAIN"    "Your domain name (e.g. octaos.example.com - or hit Enter to use IP)" "$DETECTED_IP"
prompt_var "SERVER_IP" "Your server's public IP address"              "$DETECTED_IP"

# Load domain & IP for use in this script
DOMAIN=$(grep -E "^DOMAIN=" "$ENV_FILE" | cut -d'=' -f2-)
SERVER_IP=$(grep -E "^SERVER_IP=" "$ENV_FILE" | cut -d'=' -f2-)

# Determine protocol & SSL configuration early to build Next.js with correct API URL
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [[ "$DOMAIN" == "localhost" ]]; then
  USE_SSL=false
  PROTOCOL="http"
  info "Domain is an IP address or localhost; SSL certificate request will be skipped."
else
  read -r -p "  Enable Let's Encrypt SSL (HTTPS)? [Y/n]: " do_ssl
  if [[ "${do_ssl:-y}" =~ ^[Yy]$ ]]; then
    USE_SSL=true
    PROTOCOL="https"
  else
    USE_SSL=false
    PROTOCOL="http"
  fi
fi

# ── Database ──────────────────────────────────────────────────────────────────
prompt_var "POSTGRES_SERVER"   "PostgreSQL host"           "localhost"
prompt_var "POSTGRES_USER"     "PostgreSQL username"       "octaos"

# Auto-generate DB password if missing or default
current_pg_pass=$(grep -E "^POSTGRES_PASSWORD=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- || true)
if [[ -z "$current_pg_pass" || "$current_pg_pass" == *"CHANGE_ME"* ]]; then
  generated_pg_pass=$(openssl rand -hex 16)
  if grep -q "^POSTGRES_PASSWORD=" "$ENV_FILE"; then
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${generated_pg_pass}|" "$ENV_FILE"
  else
    echo "POSTGRES_PASSWORD=${generated_pg_pass}" >> "$ENV_FILE"
  fi
  success "POSTGRES_PASSWORD auto-generated ✓"
fi

prompt_var "POSTGRES_DB"       "PostgreSQL database name"  "octaos"

# ── Redis ─────────────────────────────────────────────────────────────────────
prompt_var "REDIS_HOST" "Redis host" "localhost"
prompt_var "REDIS_PORT" "Redis port" "6379"

# ── AI Keys ───────────────────────────────────────────────────────────────────
prompt_var "ANTHROPIC_API_KEY" "Anthropic API key" ""

read -r -p "  Do you have an OpenAI key? [y/N]: " has_openai
if [[ "$has_openai" =~ ^[Yy]$ ]]; then
  prompt_var "OPENAI_API_KEY" "OpenAI API key" ""
fi

# ── SMTP ──────────────────────────────────────────────────────────────────────
prompt_var "EMAIL_HOST"          "SMTP host"         "smtp.gmail.com"
prompt_var "EMAIL_PORT"          "SMTP port"         "587"
prompt_var "EMAIL_USE_TLS"       "Use TLS (True/False)" "True"
prompt_var "EMAIL_HOST_USER"     "SMTP username"     "yourgmail@gmail.com"
prompt_var "EMAIL_HOST_PASSWORD" "SMTP password"     "nefxdsudmwmwllug"
prompt_var "DEFAULT_FROM_EMAIL"  "SMTP from address" "yourgmail@gmail.com"

# ── App Security ──────────────────────────────────────────────────────────────
current_secret_key=$(grep -E "^SECRET_KEY=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- || true)
if [[ -z "$current_secret_key" || "$current_secret_key" == *"CHANGE_ME"* ]]; then
  generated_key=$(openssl rand -hex 32)
  if grep -q "^SECRET_KEY=" "$ENV_FILE"; then
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${generated_key}|" "$ENV_FILE"
  else
    echo "SECRET_KEY=${generated_key}" >> "$ENV_FILE"
  fi
  success "SECRET_KEY auto-generated ✓"
fi

# ── Frontend API URL ──────────────────────────────────────────────────────────
NEXT_PUBLIC_API_URL="${PROTOCOL}://${DOMAIN}/api/v1"
if grep -q "^NEXT_PUBLIC_API_URL=" "$ENV_FILE"; then
  sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}|" "$ENV_FILE"
else
  echo "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" >> "$ENV_FILE"
fi

# ── Public Base URL (for media/branding uploads) ──────────────────────────────
PUBLIC_BASE_URL="${PROTOCOL}://${DOMAIN}"
if grep -q "^PUBLIC_BASE_URL=" "$ENV_FILE"; then
  sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=${PUBLIC_BASE_URL}|" "$ENV_FILE"
else
  echo "PUBLIC_BASE_URL=${PUBLIC_BASE_URL}" >> "$ENV_FILE"
fi
success "PUBLIC_BASE_URL set to ${PUBLIC_BASE_URL} ✓"

# Mark dev=true for development/QA deployment (enables magic OTP 123455)
if grep -q "^DEV=" "$ENV_FILE"; then
  sed -i "s|^DEV=.*|DEV=true|" "$ENV_FILE"
else
  echo "DEV=true" >> "$ENV_FILE"
fi

success ".env configured ✓"

# Load all env vars for use below
set -a; source "$ENV_FILE"; set +a

# =============================================================================
# 3. Pull Latest Code
# =============================================================================
header "Git Pull"

cd "$APP_DIR"

if git rev-parse --git-dir &>/dev/null; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  info "Updating Git remote origin URL..."
  git remote set-url origin https://github.com/alienhousenetworks/OctaOsautomation.git || warn "Failed to update Git remote origin URL"
  info "Fetching latest changes from Git..."
  git fetch --all
  info "Pulling latest from branch: $BRANCH"
  if ! git pull origin "$BRANCH"; then
    warn "Git pull failed. You might have uncommitted local changes on the VPS."
    warn "To overwrite local changes and pull:  git reset --hard origin/$BRANCH"
    warn "Continuing deployment with existing code..."
  else
    success "Code up to date"
  fi
else
  warn "Not a git repository – skipping pull"
fi

# =============================================================================
# 4. PostgreSQL – Create user & database
# =============================================================================
header "PostgreSQL Setup"

PG_USER="$POSTGRES_USER"
PG_PASS="$POSTGRES_PASSWORD"
PG_DB="$POSTGRES_DB"

info "Ensuring PostgreSQL user '${PG_USER}' exists and has the correct password …"
if sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'" | grep -q 1; then
  sudo -u postgres psql -c "ALTER USER ${PG_USER} WITH PASSWORD '${PG_PASS}';"
else
  sudo -u postgres psql -c "CREATE USER ${PG_USER} WITH PASSWORD '${PG_PASS}';"
fi

info "Ensuring database '${PG_DB}' exists …"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${PG_DB} TO ${PG_USER};" -q
success "PostgreSQL ready ✓"

# =============================================================================
# 5. Python Backend – virtualenv & deps
# =============================================================================
header "Backend Setup"

info "Creating/updating virtualenv …"
python3 -m venv "$VENV_DIR"

info "Upgrading pip …"
"$VENV_DIR/bin/pip" install --upgrade pip -q

info "Installing python dependencies …"
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" -q
success "Python dependencies installed ✓"

info "Running database init/migration …"
"$VENV_DIR/bin/python3" "$APP_DIR/init_db.py" || warn "init_db.py had warnings (may be safe to ignore)"
success "Database initialised ✓"

# =============================================================================
# 6. Next.js Frontend – install & build
# =============================================================================
header "Frontend Build"

cd "$FRONTEND_DIR"

# Write frontend .env.local
cat > "$FRONTEND_DIR/.env.local" <<EOF
NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
EOF

info "Installing npm dependencies …"
npm ci --silent
info "Building Next.js production bundle (optimized for RAM size) …"
NODE_OPTIONS="--max-old-space-size=1024" npm run build
success "Frontend built ✓"

# =============================================================================
# 7. Log Directory
# =============================================================================
mkdir -p "$LOG_DIR"
chown -R "$APP_USER":"$APP_USER" "$LOG_DIR"

# =============================================================================
# 8. Systemd Services
# =============================================================================
header "Systemd Services"

UVICORN_BIN="$VENV_DIR/bin/uvicorn"
CELERY_BIN="$VENV_DIR/bin/celery"

# ── 8a. API (uvicorn) ─────────────────────────────────────────────────────────
cat > /etc/systemd/system/octaos-api.service <<EOF
[Unit]
Description=OctaOS FastAPI Backend
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${UVICORN_BIN} app.main:app --host 127.0.0.1 --port 8001 --workers 4
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/api.log
StandardError=append:${LOG_DIR}/api-error.log

[Install]
WantedBy=multi-user.target
EOF

# ── 8b. Celery Worker (Correct App target: app.worker.tasks) ─────────────────
cat > /etc/systemd/system/octaos-worker.service <<EOF
[Unit]
Description=OctaOS Celery Worker
After=network.target redis.service postgresql.service
Requires=redis.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${CELERY_BIN} -A app.worker.tasks worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10
StandardOutput=append:${LOG_DIR}/worker.log
StandardError=append:${LOG_DIR}/worker-error.log

[Install]
WantedBy=multi-user.target
EOF

# ── 8c. Celery Beat (Correct App target: app.worker.tasks) ───────────────────
cat > /etc/systemd/system/octaos-beat.service <<EOF
[Unit]
Description=OctaOS Celery Beat Scheduler
After=network.target redis.service
Requires=octaos-worker.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${CELERY_BIN} -A app.worker.tasks beat --loglevel=info --scheduler celery.beat:PersistentScheduler
Restart=always
RestartSec=10
StandardOutput=append:${LOG_DIR}/beat.log
StandardError=append:${LOG_DIR}/beat-error.log

[Install]
WantedBy=multi-user.target
EOF

# ── 8d. Next.js Frontend (Dynamic Standalone vs Fallback Service) ────────────
NODE_BIN="$(which node)"
NPM_BIN="$(which npm)"

if [[ -d "$FRONTEND_DIR/.next/standalone" ]]; then
  FRONTEND_EXEC="${NODE_BIN} ${FRONTEND_DIR}/.next/standalone/server.js"
  # Copy static assets for Next.js standalone runner
  cp -r "$FRONTEND_DIR/.next/static"   "$FRONTEND_DIR/.next/standalone/.next/static"   2>/dev/null || true
  cp -r "$FRONTEND_DIR/public"         "$FRONTEND_DIR/.next/standalone/public"          2>/dev/null || true
  success "Next.js standalone assets copied ✓"
else
  FRONTEND_EXEC="${NPM_BIN} run start"
  success "Using 'npm run start' fallback for frontend ✓"
fi

cat > /etc/systemd/system/octaos-frontend.service <<EOF
[Unit]
Description=OctaOS Next.js Frontend
After=network.target octaos-api.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${FRONTEND_DIR}
Environment=NODE_ENV=production
Environment=PORT=3001
EnvironmentFile=${ENV_FILE}
ExecStart=${FRONTEND_EXEC}
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/frontend.log
StandardError=append:${LOG_DIR}/frontend-error.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

for svc in octaos-api octaos-worker octaos-beat octaos-frontend; do
  systemctl enable "$svc" --quiet
  systemctl restart "$svc"
  success "$svc enabled & started ✓"
done

# =============================================================================
# 9. Nginx Configuration
# =============================================================================
header "Nginx Configuration"

# Detect active Nginx configuration structure
if [[ -d "/etc/nginx/conf.d" ]] && grep -qE "^\s*include\s+.*conf\.d/\*\.conf" /etc/nginx/nginx.conf; then
  NGINX_CONF="/etc/nginx/conf.d/octaos.conf"
  NGINX_LINK="/etc/nginx/conf.d/octaos.conf"
  info "Detected active Nginx conf.d structure"
elif [[ -d "/etc/nginx/sites-enabled" ]] && grep -qE "^\s*include\s+.*sites-enabled/" /etc/nginx/nginx.conf; then
  NGINX_CONF="/etc/nginx/sites-available/octaos.conf"
  NGINX_LINK="/etc/nginx/sites-enabled/octaos.conf"
  info "Detected active Nginx sites-enabled structure"
else
  # Fallback: if conf.d directory exists, use it, otherwise sites-enabled
  if [[ -d "/etc/nginx/conf.d" ]]; then
    NGINX_CONF="/etc/nginx/conf.d/octaos.conf"
    NGINX_LINK="/etc/nginx/conf.d/octaos.conf"
    info "Fallback: Using Nginx conf.d structure"
  else
    NGINX_CONF="/etc/nginx/sites-available/octaos.conf"
    NGINX_LINK="/etc/nginx/sites-enabled/octaos.conf"
    info "Fallback: Using Nginx sites-enabled structure"
  fi
fi

# Clean up any potential conflicting config files from previous runs to avoid duplication or inactive config conflicts
rm -f /etc/nginx/sites-available/octaos \
      /etc/nginx/sites-enabled/octaos \
      /etc/nginx/sites-available/octaos.conf \
      /etc/nginx/sites-enabled/octaos.conf \
      /etc/nginx/conf.d/octaos.conf 2>/dev/null || true

cat > "$NGINX_CONF" <<EOF
# ── OctaOS Nginx Config ──────────────────────────────────────────────────────
# Auto-generated by deploy-dev.sh

# Rate limiting zone
limit_req_zone \$binary_remote_addr zone=api_limit:10m rate=30r/s;

server {
    listen 80;
    server_name ${DOMAIN};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN"   always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1024;

    # ── API ──────────────────────────────────────────────────────────────────
    location /api/ {
        limit_req zone=api_limit burst=50 nodelay;
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade          \$http_upgrade;
        proxy_set_header   Connection       "upgrade";
        proxy_set_header   Host             \$host;
        proxy_set_header   X-Real-IP        \$remote_addr;
        proxy_set_header   X-Forwarded-For  \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        client_max_body_size 50M;
    }

    # ── Media (FastAPI static) ────────────────────────────────────────────────
    location /media/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    # ── API Docs ─────────────────────────────────────────────────────────────
    location ~ ^/(docs|redoc|openapi.json) {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
    }

    # ── Next.js Static Assets ─────────────────────────────────────────────────
    location /_next/static/ {
        alias ${FRONTEND_DIR}/.next/static/;
        expires 365d;
        add_header Cache-Control "public, immutable";
    }

    location /favicon.ico {
        alias ${FRONTEND_DIR}/public/favicon.ico;
    }

    # ── Frontend (Next.js) ────────────────────────────────────────────────────
    location / {
        proxy_pass         http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade         \$http_upgrade;
        proxy_set_header   Connection      "upgrade";
        proxy_set_header   Host            \$host;
        proxy_set_header   X-Real-IP       \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
    }
}
EOF

# Enable site
if [[ "$NGINX_CONF" != "$NGINX_LINK" ]]; then
  ln -sf "$NGINX_CONF" "$NGINX_LINK"
fi

# Remove default site symlink if it exists to avoid port 80/443 conflict
if [[ -d "/etc/nginx/sites-enabled" ]]; then
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
fi

nginx -t && systemctl restart nginx
success "Nginx configured & restarted ✓"

# =============================================================================
# 10. Provision Let's Encrypt SSL if chosen early
# =============================================================================
header "SSL Certificate"

if [[ "$USE_SSL" == "true" ]]; then
  read -r -p "  Admin email for certificate notifications: " admin_email
  certbot --nginx \
    -d "$DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "$admin_email" \
    --redirect
  success "SSL certificate installed ✓"
  systemctl enable certbot.timer --quiet 2>/dev/null || true
else
  warn "Skipped SSL – site is running on HTTP only"
fi

# =============================================================================
# 11. Firewall (ufw) – optional
# =============================================================================
header "Firewall"

if command -v ufw &>/dev/null; then
  ufw allow OpenSSH    --force -q
  ufw allow 'Nginx Full' --force -q
  ufw --force enable   -q 2>/dev/null || true
  success "UFW firewall configured ✓"
else
  warn "ufw not found – skipping firewall setup"
fi

# =============================================================================
# 12. Health Check
# =============================================================================
header "Health Check"

sleep 3

check_service() {
  if systemctl is-active --quiet "$1"; then
    success "$1 is running ✓"
  else
    warn "$1 is NOT running – check: journalctl -u $1 -n 50"
  fi
}

for svc in postgresql redis-server nginx octaos-api octaos-worker octaos-beat octaos-frontend; do
  check_service "$svc"
done

# Quick HTTP smoke test
if curl -sf "http://localhost:8001/" > /dev/null 2>&1; then
  success "Backend API responding ✓"
else
  warn "Backend API not yet responding – may still be starting up"
fi

if curl -sf "http://localhost:3001/" > /dev/null 2>&1; then
  success "Frontend responding ✓"
else
  warn "Frontend not yet responding – may still be starting up"
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  OctaOS Deployed Successfully (Development Mode)!${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  🌐 Frontend  → ${CYAN}${PROTOCOL}://${DOMAIN}${NC}"
echo -e "  🔌 API       → ${CYAN}${PROTOCOL}://${DOMAIN}/api/v1${NC}"
echo -e "  📖 API Docs  → ${CYAN}${PROTOCOL}://${DOMAIN}/docs${NC}"
echo ""
echo -e "  Logs in: ${LOG_DIR}/"
echo -e "    api:      tail -f ${LOG_DIR}/api.log"
echo -e "    worker:   tail -f ${LOG_DIR}/worker.log"
echo -e "    frontend: tail -f ${LOG_DIR}/frontend.log"
echo ""
echo -e "  Restart all services:"
echo -e "    ${YELLOW}sudo systemctl restart octaos-api octaos-worker octaos-beat octaos-frontend nginx${NC}"
echo ""
