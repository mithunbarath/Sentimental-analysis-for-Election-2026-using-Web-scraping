#!/usr/bin/env bash
# =============================================================================
# setup_vm.sh — GCP Compute Engine VM bootstrap for Palladam Politics Scraper
#
# Run once as root (or sudo) on a fresh Debian 12 / Ubuntu 22.04 VM:
#   sudo bash setup_vm.sh
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/mithunbarath/XDOSO-Palladam-scraper.git"  # update if different
INSTALL_DIR="/opt/scraper"
PYTHON="python3.11"
SERVICE_USER="scraper"

echo "========================================================"
echo "  Palladam Scraper — GCP VM Setup"
echo "========================================================"

# ── 1. System dependencies ────────────────────────────────────────────────────
apt-get update -y
apt-get install -y \
    git curl wget gnupg ca-certificates \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 \
    libcairo2 libasound2 redis-server

echo "[1/6] System packages installed."

# ── 2. Create a dedicated non-root user ──────────────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
    echo "[2/6] User '$SERVICE_USER' created."
else
    echo "[2/6] User '$SERVICE_USER' already exists."
fi

# ── 3. Clone / update repository ─────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[3/6] Updating existing repo..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "[3/6] Cloning repo..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# ── 4. Python virtual environment + dependencies ──────────────────────────────
echo "[4/6] Setting up Python venv..."
sudo -u "$SERVICE_USER" bash -c "
    $PYTHON -m venv $INSTALL_DIR/.venv
    source $INSTALL_DIR/.venv/bin/activate
    pip install --upgrade pip
    pip install -r $INSTALL_DIR/requirements.txt
"

# Install Playwright browsers (Chromium only to save space)
echo "[4/6] Installing Playwright Chromium..."
sudo -u "$SERVICE_USER" bash -c "
    source $INSTALL_DIR/.venv/bin/activate
    playwright install chromium
    playwright install-deps chromium
"

# ── 5. Install systemd timer units ───────────────────────────────────────────
echo "[5/6] Installing systemd units..."
cp "$INSTALL_DIR/deploy/scraper.service" /etc/systemd/system/scraper.service
cp "$INSTALL_DIR/deploy/scraper.timer"   /etc/systemd/system/scraper.timer
systemctl daemon-reload
systemctl enable scraper.timer
systemctl start  scraper.timer

# ── 6. Create .env file placeholder ─────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$INSTALL_DIR/.env.example" "$ENV_FILE"
    chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "[6/6] Created .env from .env.example — PLEASE FILL IN YOUR SECRETS."
else
    echo "[6/6] .env already exists, skipping."
fi

echo ""
echo "========================================================"
echo "  Setup complete!"
echo "  Next steps:"
echo "    1. Edit $ENV_FILE and add your API keys."
echo "    2. Copy your GCP service account JSON to $INSTALL_DIR/gcp-service-account.json"
echo "    3. Edit $INSTALL_DIR/config.yaml to set your spreadsheet_id."
echo "    4. Check timer:  sudo systemctl status scraper.timer"
echo "    5. View logs:    journalctl -u scraper.service -f"
echo "========================================================"
