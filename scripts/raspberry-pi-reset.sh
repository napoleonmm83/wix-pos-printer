#!/bin/bash

# 🧹 Raspberry Pi Reset Script
# Wix Printer Service - Complete System Reset
# Version: 1.0
# Date: 2025-09-20

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions (following existing pattern)
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
   exit 1
fi

# Display header
echo ""
echo "=========================================="
echo "🧹 WIX PRINTER SERVICE - SYSTEM RESET"
echo "=========================================="
echo ""
echo "This script will COMPLETELY REMOVE the Wix Printer Service"
echo "and reset your Raspberry Pi to the state before installation."
echo ""
echo "⚠️  WARNING: This will delete:"
echo "   • All service files and configurations"
echo "   • Database and log files"
echo "   • Python virtual environment"
echo "   • systemd service"
echo "   • Service user account"
echo ""
echo "✅ This will NOT affect:"
echo "   • Your personal files"
echo "   • Other services or applications"
echo "   • System packages (they remain installed)"
echo ""

# Interactive confirmation
read -p "❓ Are you sure you want to COMPLETELY RESET the installation? (type 'RESET' to confirm): " -r
echo ""

if [ "$REPLY" != "RESET" ]; then
    log "Reset cancelled by user"
    exit 0
fi

echo "🔍 Analyzing current installation..."
echo ""

# Function to check if component exists
check_component() {
    local component="$1"
    local check_command="$2"
    
    if eval "$check_command" &>/dev/null; then
        echo "✅ Found: $component"
        return 0
    else
        echo "⏭️  Not found: $component"
        return 1
    fi
}

# Analyze what needs to be reset
echo "📋 INSTALLATION ANALYSIS:"
echo "----------------------------------------"

SYSTEMD_SERVICE_EXISTS=false
SERVICE_USER_EXISTS=false
SERVICE_DIR_EXISTS=false
PYTHON_ENV_EXISTS=false
DATABASE_EXISTS=false

if check_component "systemd service (wix-printer.service)" "systemctl list-unit-files | grep -q wix-printer.service"; then
    SYSTEMD_SERVICE_EXISTS=true
fi

if check_component "service user (wix-printer)" "id wix-printer"; then
    SERVICE_USER_EXISTS=true
fi

if check_component "service directory (/opt/wix-printer-service)" "[ -d /opt/wix-printer-service ]"; then
    SERVICE_DIR_EXISTS=true
fi

if check_component "Python virtual environment" "[ -d /opt/wix-printer-service/venv ]"; then
    PYTHON_ENV_EXISTS=true
fi

if check_component "database files" "[ -f /opt/wix-printer-service/data/wix_printer.db ]"; then
    DATABASE_EXISTS=true
fi

echo ""

# If nothing is found, exit early
if [ "$SYSTEMD_SERVICE_EXISTS" = false ] && [ "$SERVICE_USER_EXISTS" = false ] && [ "$SERVICE_DIR_EXISTS" = false ]; then
    log "🎉 No Wix Printer Service installation found!"
    log "Your system is already clean."
    exit 0
fi

# Final confirmation
echo "🚨 FINAL CONFIRMATION:"
echo "----------------------------------------"
echo "The following components will be PERMANENTLY DELETED:"
echo ""

[ "$SYSTEMD_SERVICE_EXISTS" = true ] && echo "🗑️  systemd service: wix-printer.service"
[ "$SERVICE_USER_EXISTS" = true ] && echo "🗑️  Service user: wix-printer"
[ "$SERVICE_DIR_EXISTS" = true ] && echo "🗑️  Service directory: /opt/wix-printer-service (including all files)"
[ "$PYTHON_ENV_EXISTS" = true ] && echo "🗑️  Python virtual environment"
[ "$DATABASE_EXISTS" = true ] && echo "🗑️  Database and log files"

echo ""
read -p "❓ Proceed with PERMANENT DELETION? (type 'DELETE' to confirm): " -r
echo ""

if [ "$REPLY" != "DELETE" ]; then
    log "Reset cancelled by user"
    exit 0
fi

echo "🧹 Starting system reset..."
echo ""

# Phase 1: Stop and disable service
if [ "$SYSTEMD_SERVICE_EXISTS" = true ]; then
    log "🛑 Phase 1: Stopping and disabling systemd service..."
    
    # Stop service if running
    if systemctl is-active --quiet wix-printer.service 2>/dev/null; then
        log "Stopping wix-printer.service..."
        sudo systemctl stop wix-printer.service
    fi
    
    # Disable service if enabled
    if systemctl is-enabled --quiet wix-printer.service 2>/dev/null; then
        log "Disabling wix-printer.service..."
        sudo systemctl disable wix-printer.service
    fi
    
    # Remove service file
    if [ -f /etc/systemd/system/wix-printer.service ]; then
        log "Removing service file..."
        sudo rm -f /etc/systemd/system/wix-printer.service
    fi
    
    # Reload systemd
    log "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    
    log "✅ systemd service removed successfully"
    echo ""
fi

# Phase 2: Remove service directory and all files
if [ "$SERVICE_DIR_EXISTS" = true ]; then
    log "🗂️  Phase 2: Removing service directory and all files..."
    
    # Safety check: ensure we're only deleting the correct directory
    if [ -d "/opt/wix-printer-service" ]; then
        log "Removing /opt/wix-printer-service and all contents..."
        sudo rm -rf /opt/wix-printer-service
        log "✅ Service directory removed successfully"
    fi
    echo ""
fi

# Phase 3: Remove service user
if [ "$SERVICE_USER_EXISTS" = true ]; then
    log "👤 Phase 3: Removing service user..."
    
    # Remove user from groups first
    if groups wix-printer 2>/dev/null | grep -q lp; then
        log "Removing user from lp group..."
        sudo gpasswd -d wix-printer lp 2>/dev/null || true
    fi
    
    # Remove user account
    log "Removing wix-printer user account..."
    sudo userdel wix-printer 2>/dev/null || true
    
    log "✅ Service user removed successfully"
    echo ""
fi

# Phase 4: Clean up any remaining systemd references
log "🧽 Phase 4: Cleaning up system references..."

# Reset systemd if needed
sudo systemctl reset-failed 2>/dev/null || true

log "✅ System cleanup completed"
echo ""

# Phase 5: Verification
log "🔍 Phase 5: Verifying reset completion..."
echo ""

RESET_SUCCESS=true

echo "📋 RESET VERIFICATION:"
echo "----------------------------------------"

if systemctl list-unit-files | grep -q wix-printer.service; then
    echo "❌ systemd service still exists"
    RESET_SUCCESS=false
else
    echo "✅ systemd service removed"
fi

if id wix-printer &>/dev/null; then
    echo "❌ Service user still exists"
    RESET_SUCCESS=false
else
    echo "✅ Service user removed"
fi

if [ -d /opt/wix-printer-service ]; then
    echo "❌ Service directory still exists"
    RESET_SUCCESS=false
else
    echo "✅ Service directory removed"
fi

echo ""

if [ "$RESET_SUCCESS" = true ]; then
    echo "🎉 RESET COMPLETED SUCCESSFULLY!"
    echo ""
    echo "✅ Your Raspberry Pi has been reset to the state before installation."
    echo "✅ You can now run the setup script again for a fresh installation."
    echo ""
    echo "📝 To reinstall the Wix Printer Service:"
    echo "   ./scripts/raspberry-pi-quickstart.sh"
    echo ""
else
    echo "⚠️  RESET COMPLETED WITH WARNINGS"
    echo ""
    echo "Some components could not be removed automatically."
    echo "This is usually not a problem, but you may want to check manually."
    echo ""
fi

log "Reset script completed"
echo ""
