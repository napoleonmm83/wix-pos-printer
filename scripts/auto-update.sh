#!/bin/bash

# Auto-Update Script for Wix Printer Service
# This script is triggered by a webhook from GitHub.

LOG_FILE="/opt/wix-printer-service/logs/auto-update.log"
SERVICE_DIR="/opt/wix-printer-service"

# --- Functions ---
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# --- Main Script ---
# Redirect all output to the log file
exec >> "$LOG_FILE" 2>&1

log "========================================="
log "🚀 Auto-Update process started..."
log "========================================="

# Navigate to the service directory
cd "$SERVICE_DIR" || { log "ERROR: Service directory $SERVICE_DIR not found."; exit 1; }

# Fetch and reset to the latest version from the main branch
log "Fetching latest code from origin/main..."
git fetch origin
git reset --hard origin/main
log "✅ Code updated successfully."

# Install/update Python dependencies
log "Checking for new Python dependencies..."
# Ensure the virtual environment is activated correctly
source "$SERVICE_DIR/venv/bin/activate"
pip install -r "$SERVICE_DIR/requirements.txt"
log "✅ Python dependencies are up to date."

# Restart the systemd services
log "Restarting services..."
sudo systemctl restart wix-printer.service
sudo systemctl restart wix-printer-app.service
log "✅ Services restarted."

log "🎉 Auto-Update process finished successfully."
echo # Add a final newline for log readability
