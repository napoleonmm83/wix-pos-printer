#!/bin/bash

# 🍓 Raspberry Pi Quick Start Script
# Wix Printer Service - Now with Smart Setup
# Version: 2.1

set -e  # Exit on any error

# --- Script Configuration ---
RESET_MODE=false
HELP_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --reset) RESET_MODE=true; shift ;;
        --help|-h) HELP_MODE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- UI & Logging ---
source "$(dirname "$0")/helpers.sh"

# --- Function Definitions ---

show_help() {
    echo "Wix Printer Service - Raspberry Pi Setup & Management (v2.1)"
    echo "---------------------------------------------------------------"
    echo "USAGE: $0 [OPTIONS]"
    echo "
OPTIONS:"
    echo "  --reset         Reset/remove complete installation."
    echo "  --help, -h      Show this help message."
    echo "
FEATURES:"
    echo "  ✨ Smart Configuration: Only prompts for missing values on update."
}

# Function to read .env file and export variables
load_env() {
    if [ -f ".env" ]; then
        log "Found existing .env file. Loading configuration..."
        export $(grep -v '^#' .env | xargs)
    else
        log "No .env file found. Starting fresh configuration."
    fi
}

# Function to update a value in the .env file
update_env_file() {
    local key=$1
    local value=$2
    local env_file=".env"

    # Use sudo to touch and modify the file, then ensure correct ownership
    sudo touch "$env_file"
    sudo chown wix-printer:wix-printer "$env_file"

    if grep -q "^${key}=" "$env_file"; then
        # Use sudo with sed to replace the line
        sudo sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
    else
        # Use sudo with tee to append the line
        echo "${key}=${value}" | sudo tee -a "$env_file" > /dev/null
    fi
}

# Function to get user input for a variable if it's not already set
get_or_prompt_var() {
    local var_name="$1"
    local prompt_text="$2"
    local default_value="$3"
    local is_secret=${4:-false}

    if [ ! -z "${!var_name}" ]; then
        log "Found existing value for ${BLUE}${var_name}${GREEN}. Skipping prompt."
        return
    fi

    echo -e "${YELLOW}❓ ${prompt_text}${NC}"
    local user_input
    if [ "$is_secret" = true ]; then
        read -sp "   👉 Enter value: " user_input
        echo
    else
        read -p "   👉 Enter value (default: ${default_value}): " user_input
    fi

    local final_value=${user_input:-$default_value}
    
    export ${var_name}="${final_value}"
    update_env_file "$var_name" "$final_value"
    log "Set ${BLUE}${var_name}${GREEN} to: ${final_value}"
}

# --- Main Execution ---

if [ "$HELP_MODE" = true ]; then
    show_help
    exit 0
fi

if [ "$RESET_MODE" = true ]; then
    exec bash "$(dirname "${BASH_SOURCE[0]}")/raspberry-pi-reset.sh"
fi

if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root."
   exit 1
fi

log "🍓 Starting Smart Setup for Wix Printer Service (v2.1)"

# Phases 1-4: System updates, user setup, permissions, python env (unchanged)
log "📦 Phases 1-4: System Update, User, Permissions, and Python Env Setup..."
sudo apt update && sudo apt-get install -y git python3-pip python3-venv sqlite3 curl cups libusb-1.0-0-dev dnsutils
if ! id "wix-printer" &>/dev/null; then sudo useradd -r -s /bin/bash -d /opt/wix-printer-service wix-printer; fi
sudo mkdir -p /opt/wix-printer-service && sudo chown wix-printer:wix-printer /opt/wix-printer-service
sudo usermod -a -G lp wix-printer

# Grant passwordless sudo for service restarts needed by the auto-updater
log "🔐 Granting wix-printer user permission to restart services..."
SUDOERS_FILE="/etc/sudoers.d/010_wix-printer-nopasswd"
SUDOERS_CONTENT="wix-printer ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart wix-printer.service, /usr/bin/systemctl restart wix-printer-app.service"
echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null
sudo chmod 0440 "$SUDOERS_FILE"
log "✅ Permissions granted for auto-updates."
sudo bash -c 'echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"04b8\", ATTR{idProduct}==\"0e32\", GROUP=\"wix-printer\", MODE=\"0666\"" > /etc/udev/rules.d/99-wix-printer.rules'
sudo udevadm control --reload-rules && sudo udevadm trigger
PROJECT_DIR="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
sudo cp -r "$PROJECT_DIR"/* /opt/wix-printer-service/
sudo chown -R wix-printer:wix-printer /opt/wix-printer-service
cd /opt/wix-printer-service
sudo -u wix-printer python3 -m venv venv
sudo -u wix-printer bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Phase 5: Smart Configuration & DB Test
log "⚙️ Phase 5: Smart Configuration & DB Test..."
load_env

# Function to test the database connection
test_db_connection() {
    log "🧪 Testing database connection..."
    local test_script="
import os, sys, psycopg2
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('ERROR: DATABASE_URL not found in environment.', file=sys.stderr)
    sys.exit(1)
try:
    conn = psycopg2.connect(db_url)
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'Connection Error: {e}', file=sys.stderr)
    sys.exit(1)
"
    # Execute as the service user, ensuring the venv and env vars are loaded
    if sudo -u wix-printer bash -c "source venv/bin/activate && export $(grep -v '^#' .env | xargs) && python -c \"$test_script\""; then
        return 0 # Success
    else
        return 1 # Failure
    fi
}

# --- DATABASE_URL VALIDATION LOOP ---
log "🔎 Validating Database Connection..."
while true; do
    # Check if the current DATABASE_URL is valid and connects
    if [[ "$DATABASE_URL" == "postgresql://"* ]] && test_db_connection; then
        log "✅ Database connection is valid and successful."
        break # Exit the loop
    fi
    
    # If not valid, prompt the user for a new one
    warn "Database connection is not configured or failed the test."
    echo -e "${YELLOW}❓ Please enter the full PostgreSQL connection URL:${NC}"
    read -p "   👉 Enter value: " user_input

    # Update the variable and the .env file for the next loop iteration/test
    DATABASE_URL="$user_input"
    export DATABASE_URL
    update_env_file "DATABASE_URL" "$user_input"
    # Add a small delay to allow user to read error messages
    sleep 1
done

# --- Prompt for other variables ---
log "⚙️ Configuring other service variables..."
get_or_prompt_var "WIX_API_KEY" "Enter your Wix API Key" "" true
get_or_prompt_var "WIX_SITE_ID" "Enter your Wix Site ID" ""

# --- GitHub Webhook Secret ---
log "🔐 Configuring GitHub Webhook Secret for Auto-Updates..."
if [ -z "$GITHUB_WEBHOOK_SECRET" ]; then
    log "No existing secret found. Generating a new one..."
    GENERATED_SECRET=$(head /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 32)
    export GITHUB_WEBHOOK_SECRET="$GENERATED_SECRET"
    update_env_file "GITHUB_WEBHOOK_SECRET" "$GENERATED_SECRET"
    
    echo -e "${YELLOW}===================================================================${NC}"
    echo -e "${YELLOW}ACTION REQUIRED: Copy this secret into your GitHub Webhook settings.${NC}"
    echo -e "${YELLOW}===================================================================${NC}"
    echo ""
    echo -e "Your auto-generated Webhook Secret is:"
    echo -e "${BLUE}$GENERATED_SECRET${NC}"
    echo ""
    echo "1. Go to your GitHub repo -> Settings -> Webhooks"
    echo "2. Find your webhook (or create a new one)."
    echo "3. Paste this value into the 'Secret' field."
    echo ""
    read -p "Press ENTER to acknowledge and continue..."
else
    log "✅ Existing GITHUB_WEBHOOK_SECRET found."
fi


get_or_prompt_var "PRINTER_INTERFACE" "Printer connection type (usb/network)" "usb"
get_or_prompt_var "PRINTER_IP" "Printer IP address (if network)" "192.168.1.100"
get_or_prompt_var "SERVICE_PORT" "Service port for the main application" "8000"
get_or_prompt_var "LOG_LEVEL" "Log level (DEBUG, INFO, WARNING, ERROR)" "INFO"
get_or_prompt_var "NOTIFICATION_ENABLED" "Enable email notifications? (true/false)" "false"

if [ "$NOTIFICATION_ENABLED" = "true" ]; then
    get_or_prompt_var "SMTP_SERVER" "SMTP Server address" "smtp.gmail.com"
    get_or_prompt_var "SMTP_PORT" "SMTP Port" "587"
    get_or_prompt_var "SMTP_USERNAME" "SMTP Username (your email)" ""
    get_or_prompt_var "SMTP_PASSWORD" "SMTP Password (or App Password)" "" true
    get_or_prompt_var "NOTIFICATION_TO_EMAILS" "Email address to send alerts to" ""
fi

log "✅ Configuration check complete."

# Phase 6: Database Initialization
log "🗄️ Phase 6: Initializing database schema..."
sudo -u wix-printer bash -c "
source venv/bin/activate
export $(grep -v '^#' .env | xargs)
python -c 'from wix_printer_service.database import Database; db = Database(); print(\"Database schema checked/initialized successfully!\")'
"

# Phase 7: Service Installation
log "🔧 Phase 7: Installing systemd services..."
if [ -f "deployment/wix-printer.service" ]; then
    sudo cp deployment/wix-printer.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable wix-printer.service
fi
if [ -f "deployment/wix-printer-app.service" ]; then
    sudo cp deployment/wix-printer-app.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable wix-printer-app.service
fi
log "✅ Systemd services installed."

# Phase 8: Final Steps
log "📊 Phase 8: Finalizing setup..."

echo -e "${GREEN}=========================================="
echo -e "🎉 SETUP COMPLETE!"
echo -e "==========================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: Please ensure the DATABASE_URL is correctly set in /opt/wix-printer-service/.env${NC}"
echo ""
echo "Next Steps:"
echo "1. Start services: sudo systemctl start wix-printer.service && sudo systemctl start wix-printer-app.service"
echo "2. Check status: sudo systemctl status wix-printer.service"

read -p "❓ Do you want to start the services now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Starting services..."
    sudo systemctl restart wix-printer.service # Use restart to ensure new env is loaded
    sudo systemctl restart wix-printer-app.service
    sleep 3
    log "Services started. Use 'sudo systemctl status ...' to check them."
else
    log "Services not started. Please start them manually."
fi

# Phase 9: Public URL Setup (if not skipped)
if [[ "${SKIP_PUBLIC_URL:-}" != "1" ]]; then
    echo ""
    header "🌐 PUBLIC URL SETUP"
    echo "=========================================="
    echo ""
    echo "The Raspberry Pi setup is complete! Now let's configure public access"
    echo "so Wix can send webhooks to your printer service."
    echo ""

    read -p "❓ Do you want to set up public URL access now? (Y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log "Skipping public URL setup."
        log "You can run it later with: ./scripts/setup-public-url-menu.sh"
    else
        log "🚀 Starting Public URL Setup..."
        echo ""

        # Get script directory and run the public URL menu
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        exec "$SCRIPT_DIR/setup-public-url-menu.sh"
    fi
fi

log "🚀 Deployment finished!"
