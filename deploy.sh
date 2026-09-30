#!/usr/bin/env bash
#
# Budget Tracker — One-Shot Migration Script
# Target: Ubuntu 24.04 VPS (Server Utama VPS KVM 6GB, Frankfurt)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/bahalil71/budget-tracker/main/deploy.sh | bash
#   atau:  bash deploy.sh
#
# Parameter:
#   MODE=systemd   (default)  → install via systemd, paling hemat RAM
#   MODE=docker               → install via Docker Compose
#
set -euo pipefail

MODE="${MODE:-systemd}"
APP_DIR="/root/budget-tracker"
REPO="https://github.com/bahalil71/budget-tracker.git"
PORT="${PORT:-8088}"

info()  { echo -e "\033[0;36m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[0;32m[ OK ]\033[0m  $*"; }
warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[0;31m[FAIL]\033[0m  $*"; exit 1; }

echo -e "\033[1;36m"
cat << 'BANNER'
╔══════════════════════════════════════════════╗
║       💰 Budget Tracker Deploy Script        ║
║   FastAPI + aiogram + SQLite + Web Dashboard ║
╚══════════════════════════════════════════════╝
BANNER
echo -e "\033[0m"

# ── 1. Pre-flight checks ─────────────────────────────────────────
info "Checking prerequisites…"
if [ "$(id -u)" -ne 0 ]; then
  fail "Must run as root (use sudo bash deploy.sh)"
fi
command -v git >/dev/null 2>&1 || fail "git not installed. Run: apt-get install -y git"
command -v python3 >/dev/null 2>&1 || fail "python3 not found"

PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if [ "$(printf '3.10\n3.9\n3.8\n' | sort -V | head -1 | cut -d. -f2)" ]; then :; fi
info "Python version: $PY_VER"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || fail "Python 3.10+ required (found $PY_VER)"
ok "Prerequisites OK"

# ── 2. Swap safety net (this VPS has 3.8GB RAM) ────────────────────
TOTAL_MB=$(free -m | awk '/^Mem:/{print $2}')
info "Detected RAM: ${TOTAL_MB} MB"
if [ "$TOTAL_MB" -lt 4096 ] && [ "$(swapon --show 2>/dev/null | wc -l)" -eq 0 ]; then
  warn "Low RAM & no swap detected. Creating 2GB swap file…"
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ok "Swap created (2GB)"
else
  ok "RAM/swap OK"
fi

# ── 3. System packages ─────────────────────────────────────────────
info "Installing system dependencies…"
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  python3-venv python3-pip curl ca-certificates \
  $( [ "$MODE" = "docker" ] && echo "docker.io docker-compose-plugin" ) \
  >/dev/null 2>&1 || warn "apt install had issues, continuing…"
ok "System dependencies ready"

# ── 4. Clone / update repo ─────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  info "Repo exists — pulling latest…"
  git -C "$APP_DIR" pull --ff-only || warn "git pull failed, keeping current version"
else
  info "Cloning repository…"
  git clone --depth 1 "$REPO" "$APP_DIR"
fi
ok "Source code ready at $APP_DIR"

# ── 5. .env (BOT_TOKEN) ────────────────────────────────────────────
if [ -f "$APP_DIR/.env" ] && grep -q '^BOT_TOKEN=' "$APP_DIR/.env"; then
  ok ".env already present (keeping existing BOT_TOKEN)"
else
  info "Creating .env…"
  if [ -t 0 ]; then
    read -rp "Masukkan Telegram BOT_TOKEN: " TG_TOKEN
  else
    read -r TG_TOKEN
  fi
  [ -n "${TG_TOKEN:-}" ] || fail "BOT_TOKEN tidak boleh kosong"
  printf 'BOT_TOKEN=%s\n' "$TG_TOKEN" > "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  ok ".env created (chmod 600)"
fi

# ── 6. Install mode ────────────────────────────────────────────────
if [ "$MODE" = "docker" ]; then
  info "Starting via Docker Compose…"
  cd "$APP_DIR"
  if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
  $DC up -d --build
  $DC logs --tail 20
  ok "Docker container started"
else
  info "Setting up Python virtualenv + systemd…"
  cd "$APP_DIR"
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  ok "Dependencies installed"

  cat > /etc/systemd/system/budget-tracker.service << 'UNIT'
[Unit]
Description=Budget Tracker Hybrid (FastAPI + aiogram + SQLite)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/budget-tracker
EnvironmentFile=/root/budget-tracker/.env
ExecStart=/root/budget-tracker/.venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONOPTIMIZE=2
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

  systemctl daemon-reload
  systemctl enable budget-tracker
  systemctl restart budget-tracker
  sleep 5
  systemctl is-active --quiet budget-tracker || fail "Service gagal start. Cek: journalctl -u budget-tracker -n 50"
  ok "systemd service active"
fi

# ── 7. Firewall ────────────────────────────────────────────────────
info "Configuring firewall…"
if command -v ufw >/dev/null 2>&1; then
  ufw allow "$PORT"/tcp >/dev/null 2>&1 || warn "ufw allow failed (maybe already open)"
  ok "UFW: port $PORT allowed"
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --add-port="$PORT/tcp" && firewall-cmd --reload >/dev/null
  ok "firewalld: port $PORT allowed"
else
  warn "No ufw/firewalld found — pastikan port $PORT terbuka di security group provider"
fi

# ── 8. Health check ────────────────────────────────────────────────
info "Health check…"
sleep 3
HEALTH=$(curl -fsS "http://localhost:$PORT/health" 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q healthy; then
  ok "API healthy on port $PORT"
else
  warn "Health check belum hijau — cek log service"
fi

# ── 9. Summary ─────────────────────────────────────────────────────
PUB_IP=$(curl -fsS https://api.ipify.org 2>/dev/null || echo "<IP-KAMU>")
cat << EOF

$(printf '\033[1;32m')╔══════════════════════════════════════════════╗
║            ✅ DEPLOY BERHASIL!                   ║
╚══════════════════════════════════════════════╝$(printf '\033[0m')

  🌐 Web Dashboard : http://${PUB_IP}:${PORT}/
  📚 Swagger Docs  : http://${PUB_IP}:${PORT}/docs
  🤖 Telegram Bot  : cek di chat (masih aktif, polling)
  📂 App directory : ${APP_DIR}
  💾 Database      : ${APP_DIR}/budget.db

  MODE            : ${MODE}

  Manage service:
    systemctl status budget-tracker
    systemctl restart budget-tracker
    journalctl -u budget-tracker -f

  Update app:
    cd ${APP_DIR} && git pull && systemctl restart budget-tracker

EOF
