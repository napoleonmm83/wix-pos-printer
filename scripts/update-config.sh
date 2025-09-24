#!/bin/bash

# 🔧 Wix Printer Service - Configuration Update Tool
# Version: 1.0
# Updates existing configuration with new Auto-Check settings

set -e  # Exit on any error

# --- UI & Logging ---
source "$(dirname "$0")/helpers.sh"

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to read .env file and get specific values
get_env_value() {
    local key="$1"
    if [ -f ".env" ]; then
        grep "^${key}=" .env 2>/dev/null | cut -d'=' -f2- || echo ""
    fi
}

load_env() {
    if [ -f ".env" ]; then
        log "Found existing .env file. Loading configuration..."
        # Load specific values we need
        export AUTO_CHECK_ENABLED=$(get_env_value "AUTO_CHECK_ENABLED")
        export AUTO_CHECK_INTERVAL=$(get_env_value "AUTO_CHECK_INTERVAL")
        export AUTO_CHECK_HOURS_BACK=$(get_env_value "AUTO_CHECK_HOURS_BACK")
        export DATABASE_URL=$(get_env_value "DATABASE_URL")
    else
        error "No .env file found. Please run the main setup first."
        exit 1
    fi
}

# Function to update a value in the .env file
update_env_file() {
    local key=$1
    local value=$2
    local env_file=".env"

    if grep -q "^${key}=" "$env_file"; then
        # Replace existing value
        sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
        log "Updated ${BLUE}${key}${GREEN} to: ${value}"
    else
        # Add new value
        echo "${key}=${value}" >> "$env_file"
        log "Added ${BLUE}${key}${GREEN} with value: ${value}"
    fi
}

# Function to prompt for configuration update
prompt_config_update() {
    local var_name="$1"
    local description="$2"
    local current_value="${!var_name}"
    local new_default="$3"

    echo -e "${YELLOW}⚙️  ${description}${NC}"
    echo -e "   Current: ${BLUE}${current_value:-"not set"}${NC}"
    echo -e "   Recommended: ${GREEN}${new_default}${NC}"

    read -p "   👉 New value (press ENTER to keep current, or enter new value): " user_input

    if [ ! -z "$user_input" ]; then
        export ${var_name}="${user_input}"
        update_env_file "$var_name" "$user_input"
        echo -e "   ✅ Updated to: ${GREEN}${user_input}${NC}"
    else
        if [ -z "${current_value}" ] && [ ! -z "${new_default}" ]; then
            # No current value, use default
            export ${var_name}="${new_default}"
            update_env_file "$var_name" "$new_default"
            echo -e "   ✅ Set to default: ${GREEN}${new_default}${NC}"
        else
            echo -e "   ✅ Keeping current value: ${GREEN}${current_value}${NC}"
        fi
    fi
    echo ""
}

# Function to restart services if they exist
restart_services() {
    log "🔄 Checking if services need to be restarted..."

    # Check if running in production environment
    if systemctl list-unit-files | grep -q "wix-printer.service"; then
        echo -e "${YELLOW}Found systemd services.${NC}"
        read -p "❓ Restart services to apply new configuration? (Y/n): " -n 1 -r
        echo ""

        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            log "Restarting services..."
            sudo systemctl restart wix-printer.service || log "Warning: Could not restart wix-printer.service"
            sudo systemctl restart wix-printer-app.service || log "Warning: Could not restart wix-printer-app.service"
            sleep 2
            log "✅ Services restarted."
        else
            log "Services not restarted. Changes will take effect on next restart."
        fi
    else
        log "No systemd services found. Configuration updated in .env file."
        log "Please restart your services manually to apply changes."
    fi
}

# --- Main Execution ---

echo ""
header "🔧 WIX PRINTER SERVICE - CONFIGURATION UPDATE"
echo "============================================="
echo ""

log "This tool helps you update your Auto-Check configuration settings."
log "The new version includes enhanced order change detection capabilities."
echo ""

# Load current configuration
load_env

echo -e "${GREEN}CURRENT CONFIGURATION:${NC}"
echo -e "  Auto-Check Enabled: ${BLUE}${AUTO_CHECK_ENABLED:-"not set"}${NC}"
echo -e "  Check Interval: ${BLUE}${AUTO_CHECK_INTERVAL:-"not set"}${NC} seconds"
echo -e "  Hours Back: ${BLUE}${AUTO_CHECK_HOURS_BACK:-"not set"}${NC} hours"
echo ""

echo -e "${YELLOW}NEW FEATURES IN THIS VERSION:${NC}"
echo "  🔄 Enhanced order change detection"
echo "  📝 Automatic reprint on order modifications"
echo "  ⏱️  Optimized 48-hour lookback window"
echo "  📊 Improved logging and monitoring"
echo ""

read -p "❓ Do you want to update your Auto-Check configuration? (Y/n): " -n 1 -r
echo ""
echo ""

if [[ $REPLY =~ ^[Nn]$ ]]; then
    log "Configuration update cancelled."
    exit 0
fi

log "🔧 Starting configuration update..."
echo ""

# Update Auto-Check settings
prompt_config_update "AUTO_CHECK_ENABLED" "Enable Auto-Check service?" "true"
prompt_config_update "AUTO_CHECK_INTERVAL" "Check interval in seconds (how often to check for orders)" "30"
prompt_config_update "AUTO_CHECK_HOURS_BACK" "Hours to look back (48 hours recommended for change detection)" "48"

echo -e "${GREEN}========================${NC}"
echo -e "${GREEN}CONFIGURATION SUMMARY${NC}"
echo -e "${GREEN}========================${NC}"
echo ""
echo -e "Auto-Check Enabled: ${BLUE}${AUTO_CHECK_ENABLED}${NC}"
echo -e "Check Interval: ${BLUE}${AUTO_CHECK_INTERVAL}${NC} seconds"
echo -e "Hours Back: ${BLUE}${AUTO_CHECK_HOURS_BACK}${NC} hours"
echo ""

if [ "${AUTO_CHECK_HOURS_BACK}" = "48" ]; then
    echo -e "${GREEN}✅ Optimized configuration for order change detection!${NC}"
    echo -e "   Your system will now detect and reprint:"
    echo -e "   • Order quantity changes"
    echo -e "   • New items added to orders"
    echo -e "   • Delivery address changes"
    echo -e "   • Any order modifications"
else
    echo -e "${YELLOW}ℹ️  Note: 48 hours is recommended for comprehensive change detection.${NC}"
fi
echo ""

# Check if database schema needs updating
log "🗄️ Checking database schema..."
if [ ! -z "$DATABASE_URL" ]; then
    # Run database schema update if update script exists
    if [ -f "update_database_schema.py" ]; then
        log "Running database schema update..."
        python update_database_schema.py
    else
        log "Database schema update script not found. Schema should be current."
    fi
else
    warn "DATABASE_URL not found. Make sure database is properly configured."
fi

# Offer to restart services
restart_services

echo ""
echo -e "${GREEN}=========================================="
echo -e "🎉 CONFIGURATION UPDATE COMPLETE!"
echo -e "==========================================${NC}"
echo ""
echo -e "${YELLOW}WHAT'S NEW:${NC}"
echo "• Enhanced order change detection is now active"
echo "• System will automatically detect order modifications"
echo "• Reprint functionality for changed orders"
echo "• Improved monitoring and logging"
echo ""

if [ "${AUTO_CHECK_ENABLED}" = "true" ]; then
    echo -e "${GREEN}✅ Auto-Check is ENABLED and will run every ${AUTO_CHECK_INTERVAL} seconds${NC}"
    echo -e "${GREEN}✅ Looking back ${AUTO_CHECK_HOURS_BACK} hours for orders and changes${NC}"
else
    echo -e "${YELLOW}ℹ️  Auto-Check is DISABLED. Enable it to use automatic order processing.${NC}"
fi

echo ""
log "Configuration file updated: .env"
log "You can run this tool again anytime to adjust settings."

log "🚀 Configuration update finished!"