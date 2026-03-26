#!/usr/bin/env bash
# =============================================================================
# run_scraper.sh — Entry point called by the systemd timer
# =============================================================================
set -euo pipefail

INSTALL_DIR="/opt/scraper"
LOG_DIR="/var/log/scraper"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$LOG_DIR"

# Load environment variables from .env file
if [ -f "$INSTALL_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$INSTALL_DIR/.env"
    set +a
fi

echo "[$TIMESTAMP] Starting Palladam scraper run..."

cd "$INSTALL_DIR"

# Activate virtual environment and run the scraper
source "$INSTALL_DIR/.venv/bin/activate"

python main.py \
    --platforms all \
    --broad-search \
    --timeout 20 \
    2>&1 | tee "$LOG_DIR/run_$TIMESTAMP.log"

echo "[$TIMESTAMP] Scraper run complete. Log: $LOG_DIR/run_$TIMESTAMP.log"

# Rotate logs — keep last 30 runs
ls -1t "$LOG_DIR"/run_*.log 2>/dev/null | tail -n +31 | xargs -r rm --
