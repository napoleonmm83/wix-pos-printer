#!/bin/bash

# Auto-Update Script for Wix Printer Service (DEBUGGING VERSION)
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
log "🚀 DEBUG: Auto-Update process started..."
log "========================================="

log "Executing: cd $SERVICE_DIR"
cd "$SERVICE_DIR" || { log "FATAL: Service directory $SERVICE_DIR not found."; exit 1; }
log "Finished: cd"

log "Executing: git fetch origin"
git fetch origin
log "Finished: git fetch origin"

log "Executing: git reset --hard origin/main"
git reset --hard origin/main
log "Finished: git reset --hard origin/main"

log "Executing: source venv/bin/activate"
source "$SERVICE_DIR/venv/bin/activate"
log "Finished: sourcing venv"

log "Executing: pip install -r requirements.txt"
pip install -r "$SERVICE_DIR/requirements.txt"
log "Finished: pip install"

log "Executing: sudo systemctl restart wix-printer.service"
sudo systemctl restart wix-printer.service
log "Finished: restart wix-printer.service"

log "Executing: sudo systemctl restart wix-printer-app.service"
sudo systemctl restart wix-printer-app.service
log "Finished: restart wix-printer-app.service"

log "🎉 DEBUG: Auto-Update process finished successfully."
echo