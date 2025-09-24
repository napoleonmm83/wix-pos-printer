#!/bin/bash

# 🌐 Cloudflare Tunnel Setup Script
# Wix Printer Service - Browser Authentication + Optional API Management
# Version: 2.1
# Date: 2025-09-24

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" >&2
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}" >&2
}

header() {
    echo -e "${CYAN}${BOLD}$1${NC}"
}

# Constants
TUNNEL_NAME="wix-pos-printer-tunnel"
SERVICE_PORT="8000"
CONFIG_DIR="/etc/cloudflared"
SERVICE_NAME="cloudflared"

show_menu() {
    clear
    header "=========================================="
    header "🌐 CLOUDFLARE TUNNEL MANAGER"
    header "=========================================="
    echo ""
    echo "Wix POS Printer Service - Tunnel Management"
    echo "Browser-Based Setup & Maintenance Tool"
    echo ""
    header "VERFÜGBARE OPTIONEN:"
    echo ""
    echo -e "  ${BOLD}1)${NC} 🚀 Neues Tunnel Setup (Erstinstallation)"
    echo -e "  ${BOLD}2)${NC} 🔄 Tunnel Update/Konfiguration erneuern"
    echo -e "  ${BOLD}3)${NC} 🧹 Tunnel komplett reset/bereinigen"
    echo -e "  ${BOLD}4)${NC} 📊 Tunnel Status anzeigen"
    echo -e "  ${BOLD}5)${NC} 🧪 Tunnel testen"
    echo -e "  ${BOLD}6)${NC} 📜 Logs anzeigen"
    echo -e "  ${BOLD}7)${NC} 🗑️ DNS-Records bereinigen (API-Token)"
    echo -e "  ${BOLD}0)${NC} ❌ Beenden"
    echo ""
}

install_cloudflared() {
    log "📦 Installing cloudflared..."

    # Detect architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            CLOUDFLARED_ARCH="amd64"
            ;;
        aarch64|arm64)
            CLOUDFLARED_ARCH="arm64"
            ;;
        armv7l|armv6l)
            CLOUDFLARED_ARCH="arm"
            ;;
        *)
            error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac

    # Download and install cloudflared
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CLOUDFLARED_ARCH"
    log "Downloading cloudflared for $ARCH..."

    if curl -L --output /tmp/cloudflared "$CLOUDFLARED_URL"; then
        sudo mv /tmp/cloudflared /usr/local/bin/
        sudo chmod +x /usr/local/bin/cloudflared

        # Verify installation
        if cloudflared version >/dev/null 2>&1; then
            log "✅ cloudflared installed and verified successfully"
        else
            error "cloudflared installation failed - binary not functional"
            log "Trying alternative installation method..."

            # Try package manager installation as fallback
            if command -v apt-get >/dev/null 2>&1; then
                log "Installing via apt package manager..."
                curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
                echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
                sudo apt-get update && sudo apt-get install -y cloudflared

                if cloudflared version >/dev/null 2>&1; then
                    log "✅ cloudflared installed via package manager"
                else
                    error "Package manager installation also failed"
                    exit 1
                fi
            else
                error "No alternative installation method available"
                exit 1
            fi
        fi
    else
        error "Failed to download cloudflared"
        log "Please check your internet connection and try again"
        exit 1
    fi
}

cleanup_old_tunnel() {
    log "🧹 Cleaning up existing tunnel configuration..."

    # Stop service if running
    if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
        log "Stopping cloudflared service..."
        sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
    fi

    # Disable service
    if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
        log "Disabling cloudflared service..."
        sudo systemctl disable $SERVICE_NAME 2>/dev/null || true
    fi

    # Remove systemd service file
    if [[ -f "/etc/systemd/system/$SERVICE_NAME.service" ]]; then
        log "Removing systemd service file..."
        sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        sudo systemctl daemon-reload
    fi

    # Remove configuration directory
    if [[ -d "$CONFIG_DIR" ]]; then
        log "Removing configuration directory..."
        sudo rm -rf "$CONFIG_DIR"
    fi

    # Clean up user cloudflared directory
    if [[ -d "$HOME/.cloudflared" ]]; then
        log "Cleaning up user cloudflared directory..."
        # Keep cert.pem for authentication, remove everything else
        find "$HOME/.cloudflared" -type f ! -name "cert.pem" -delete 2>/dev/null || true
    fi

    # Delete tunnel if it exists
    if command -v cloudflared >/dev/null 2>&1; then
        log "Checking for existing tunnel..."
        EXISTING_TUNNEL=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}' | head -1) || true

        if [[ -n "$EXISTING_TUNNEL" ]]; then
            log "Deleting existing tunnel: $EXISTING_TUNNEL"
            cloudflared tunnel delete "$EXISTING_TUNNEL" --force 2>/dev/null || warn "Could not delete tunnel automatically"
        fi
    fi

    log "✅ Cleanup completed"
}

complete_cleanup() {
    log "🗑️ Performing complete tunnel cleanup..."

    cleanup_old_tunnel

    # Also remove cloudflared binary
    if [[ -f "/usr/local/bin/cloudflared" ]]; then
        log "Removing cloudflared binary..."
        sudo rm -f "/usr/local/bin/cloudflared"
    fi

    # Remove entire user cloudflared directory
    if [[ -d "$HOME/.cloudflared" ]]; then
        log "Removing entire user cloudflared directory..."
        rm -rf "$HOME/.cloudflared"
    fi

    # Remove log files
    if [[ -f "/var/log/cloudflared.log" ]]; then
        sudo rm -f "/var/log/cloudflared.log"
    fi

    log "✅ Complete cleanup finished"
}

get_domain_info() {
    echo ""
    header "🌐 DOMAIN CONFIGURATION"
    echo "----------------------------------------"

    while [[ -z "${DOMAIN:-}" ]]; do
        echo -n "Enter your domain name (e.g., example.com): "
        read DOMAIN
        if [[ -z "$DOMAIN" ]]; then
            warn "Domain name is required"
        fi
    done

    echo -n "Enter subdomain for printer service (default: printer): "
    read SUBDOMAIN
    if [[ -z "$SUBDOMAIN" ]]; then
        SUBDOMAIN="printer"
    fi

    FULL_DOMAIN="$SUBDOMAIN.$DOMAIN"

    echo ""
    log "Configuration:"
    log "  Domain: $DOMAIN"
    log "  Subdomain: $SUBDOMAIN"
    log "  Full Domain: $FULL_DOMAIN"
    log "  Webhook URL: https://$FULL_DOMAIN/webhook/orders"
    echo ""
}

browser_authentication() {
    echo ""
    header "🔐 CLOUDFLARE AUTHENTICATION"
    echo "----------------------------------------"
    echo ""
    echo "This will open your browser to authenticate with Cloudflare."
    echo ""
    echo "📋 INSTRUCTIONS:"
    echo "   1. Browser will open to Cloudflare login"
    echo "   2. Log in to your Cloudflare account"
    echo "   3. Authorize cloudflared access"
    echo "   4. Return to this terminal when done"
    echo ""

    read -p "Press ENTER to open browser for authentication..."
    echo ""

    if cloudflared tunnel login; then
        log "✅ Authentication successful!"
        return 0
    else
        error "Authentication failed"
        return 1
    fi
}

create_tunnel() {
    log "🚇 Creating Cloudflare Tunnel..."

    # Check if tunnel already exists
    EXISTING_TUNNEL=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}' | head -1) || true

    if [[ -n "$EXISTING_TUNNEL" ]]; then
        log "✅ Found existing tunnel: $TUNNEL_NAME (ID: $EXISTING_TUNNEL)"
        TUNNEL_ID="$EXISTING_TUNNEL"

        # Check if credentials file exists for existing tunnel
        TUNNEL_CREDS="$HOME/.cloudflared/$TUNNEL_ID.json"
        if [[ ! -f "$TUNNEL_CREDS" ]]; then
            warn "Existing tunnel found but credentials missing"
            log "This is a common issue when tunnels exist remotely but credentials are missing locally"

            # Strategy: Create tunnel with unique name to avoid conflicts
            TIMESTAMP=$(date +%Y%m%d-%H%M%S)
            NEW_TUNNEL_NAME="$TUNNEL_NAME-$TIMESTAMP"
            log "Creating new tunnel with unique name: $NEW_TUNNEL_NAME"

            if cloudflared tunnel create "$NEW_TUNNEL_NAME"; then
                NEW_TUNNEL_ID=$(cloudflared tunnel list | grep "$NEW_TUNNEL_NAME" | awk '{print $1}')
                if [[ -n "$NEW_TUNNEL_ID" ]]; then
                    log "✅ New tunnel created successfully (ID: $NEW_TUNNEL_ID)"
                    log "Old tunnel ID: $TUNNEL_ID (will remain in Cloudflare but unused)"
                    log "New tunnel ID: $NEW_TUNNEL_ID (will be used for this setup)"

                    # Update variables to use new tunnel
                    TUNNEL_ID="$NEW_TUNNEL_ID"
                    TUNNEL_NAME="$NEW_TUNNEL_NAME"
                    TUNNEL_RECREATED="true"
                else
                    error "Could not find new tunnel ID after creation"
                    return 1
                fi
            else
                error "Failed to create new unique tunnel"
                log "You may need to manually clean up tunnels in the Cloudflare dashboard"
                return 1
            fi
        fi
    else
        log "Creating new tunnel: $TUNNEL_NAME"
        if cloudflared tunnel create "$TUNNEL_NAME"; then
            TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
            if [[ -z "$TUNNEL_ID" ]]; then
                error "Could not find tunnel ID after creation"
                return 1
            fi
            log "✅ Tunnel created successfully (ID: $TUNNEL_ID)"
            TUNNEL_RECREATED="true"
        else
            error "Failed to create tunnel"
            return 1
        fi
    fi
}

create_dns_record() {
    log "🌐 Creating DNS record..."

    if cloudflared tunnel route dns "$TUNNEL_ID" "$FULL_DOMAIN"; then
        log "✅ DNS record created: $FULL_DOMAIN"
        return 0
    else
        error "Failed to create DNS record"
        return 1
    fi
}

create_tunnel_config() {
    log "⚙️ Creating tunnel configuration..."

    sudo mkdir -p "$CONFIG_DIR"

    sudo tee "$CONFIG_DIR/config.yml" > /dev/null <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CONFIG_DIR/$TUNNEL_ID.json

ingress:
  # Webhook endpoints with optimized settings
  - hostname: $FULL_DOMAIN
    path: /webhook/*
    service: http://localhost:$SERVICE_PORT
    originRequest:
      httpHostHeader: $FULL_DOMAIN
      connectTimeout: 30s
      tlsTimeout: 10s
      tcpKeepAlive: 30s
      keepAliveTimeout: 90s
      keepAliveConnections: 10

  # Health check endpoint
  - hostname: $FULL_DOMAIN
    path: /health*
    service: http://localhost:$SERVICE_PORT
    originRequest:
      httpHostHeader: $FULL_DOMAIN
      connectTimeout: 10s

  # API documentation
  - hostname: $FULL_DOMAIN
    path: /docs*
    service: http://localhost:$SERVICE_PORT
    originRequest:
      httpHostHeader: $FULL_DOMAIN

  # Admin interface
  - hostname: $FULL_DOMAIN
    path: /admin*
    service: http://localhost:$SERVICE_PORT
    originRequest:
      httpHostHeader: $FULL_DOMAIN

  # All other endpoints
  - hostname: $FULL_DOMAIN
    service: http://localhost:$SERVICE_PORT
    originRequest:
      httpHostHeader: $FULL_DOMAIN
      connectTimeout: 30s
      tlsTimeout: 10s
      tcpKeepAlive: 30s
      keepAliveTimeout: 90s
      keepAliveConnections: 10

  # Catch-all rule (required)
  - service: http_status:404

# Logging configuration
loglevel: info
logfile: /var/log/cloudflared.log

# Metrics endpoint for monitoring
metrics: localhost:8080

# Auto-update settings
autoupdate-freq: 24h
EOF

    # Copy credentials to system location
    TUNNEL_CREDS="$HOME/.cloudflared/$TUNNEL_ID.json"
    if [[ -f "$TUNNEL_CREDS" ]]; then
        sudo cp "$TUNNEL_CREDS" "$CONFIG_DIR/"
        sudo chmod 600 "$CONFIG_DIR/$TUNNEL_ID.json"
        log "✅ Tunnel configuration created"
        return 0
    else
        error "Tunnel credentials not found at $TUNNEL_CREDS"
        error "This should have been handled during tunnel creation"
        error "Please try running the tunnel setup again"

        # List available credential files for debugging
        log "Available credential files:"
        ls -la "$HOME/.cloudflared/"*.json 2>/dev/null || log "No credential files found"

        return 1
    fi
}

create_systemd_service() {
    log "🔧 Creating systemd service..."

    sudo tee "/etc/systemd/system/$SERVICE_NAME.service" > /dev/null <<EOF
[Unit]
Description=Cloudflare Tunnel for Wix POS Printer
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/cloudflared tunnel --config $CONFIG_DIR/config.yml run
ExecReload=/bin/kill -USR1 \$MAINPID
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillMode=mixed

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log
PrivateTmp=true

# Environment
Environment=TUNNEL_ORIGIN_CERT=$HOME/.cloudflared/cert.pem

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME

    log "✅ Systemd service created and enabled"
}

start_and_validate_service() {
    log "🚀 Starting cloudflared service..."

    if sudo systemctl start $SERVICE_NAME; then
        log "Service start command executed"
    else
        error "Failed to start service"
        return 1
    fi

    # Wait for service to start
    sleep 5

    # Check if service is running
    if systemctl is-active --quiet $SERVICE_NAME; then
        log "✅ Cloudflared service is running"

        # Wait for tunnel to establish
        log "⏳ Waiting for tunnel to establish connection..."
        sleep 10

        return 0
    else
        error "Service failed to start properly"
        log "Service status:"
        sudo systemctl status $SERVICE_NAME --no-pager -l
        return 1
    fi
}

test_tunnel_connectivity() {
    log "🧪 Testing tunnel connectivity..."

    # Test health endpoint
    if curl -s -f -m 15 "https://$FULL_DOMAIN/health" >/dev/null 2>&1; then
        log "✅ Tunnel is working correctly!"
        return 0
    else
        warn "Tunnel connectivity test failed"
        log "This might be normal if the service isn't running yet"
        log "You can test manually later with: curl https://$FULL_DOMAIN/health"
        return 1
    fi
}

update_service_config() {
    log "⚙️ Updating service configuration..."

    # Update .env file if it exists
    ENV_FILE="/opt/wix-printer-service/.env"
    if [[ -f "$ENV_FILE" ]]; then
        if grep -q "PUBLIC_DOMAIN=" "$ENV_FILE"; then
            sudo sed -i "s/PUBLIC_DOMAIN=.*/PUBLIC_DOMAIN=$FULL_DOMAIN/" "$ENV_FILE"
        else
            echo "PUBLIC_DOMAIN=$FULL_DOMAIN" | sudo tee -a "$ENV_FILE" >/dev/null
        fi
        log "✅ Environment configuration updated"
    else
        warn "Service .env file not found at $ENV_FILE"
    fi

    # Also try current directory
    if [[ -f ".env" ]]; then
        if grep -q "PUBLIC_DOMAIN=" ".env"; then
            sed -i "s/PUBLIC_DOMAIN=.*/PUBLIC_DOMAIN=$FULL_DOMAIN/" ".env"
        else
            echo "PUBLIC_DOMAIN=$FULL_DOMAIN" >> ".env"
        fi
        log "✅ Local .env file updated"
    fi
}

show_summary() {
    echo ""
    header "🎉 CLOUDFLARE TUNNEL SETUP COMPLETE!"
    header "====================================="
    echo ""
    header "✅ CONFIGURATION SUMMARY:"
    echo "   • Tunnel Name: $TUNNEL_NAME"
    echo "   • Tunnel ID: $TUNNEL_ID"
    echo "   • Public URL: https://$FULL_DOMAIN"
    echo "   • Webhook URL: https://$FULL_DOMAIN/webhook/orders"
    echo ""
    header "🔧 MANAGEMENT COMMANDS:"
    echo "   • Check status: sudo systemctl status $SERVICE_NAME"
    echo "   • View logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "   • Restart: sudo systemctl restart $SERVICE_NAME"
    echo "   • Test URL: curl https://$FULL_DOMAIN/health"
    echo ""
    header "📊 MONITORING:"
    echo "   • Service logs: /var/log/cloudflared.log"
    echo "   • Metrics: http://localhost:8080/metrics"
    echo ""
    header "🌐 WIX WEBHOOK CONFIGURATION:"
    echo "   Configure your Wix webhook URL as:"
    echo "   👉 https://$FULL_DOMAIN/webhook/orders"
    echo ""
    header "✅ Your printer service is now accessible from anywhere!"
    header "   No router configuration or static IP needed!"
    echo ""
}

show_status() {
    clear
    header "📊 CLOUDFLARE TUNNEL STATUS"
    header "============================"
    echo ""

    # Check if cloudflared is installed
    if ! command -v cloudflared >/dev/null 2>&1; then
        error "cloudflared is not installed"
        return
    fi

    # Check service status
    echo "🔧 Service Status:"
    if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
        echo -e "   Status: ${GREEN}Running${NC}"
        echo "   Uptime: $(systemctl show -p ActiveEnterTimestamp $SERVICE_NAME --value | cut -d' ' -f2-3)"
    else
        echo -e "   Status: ${RED}Stopped${NC}"
    fi

    echo ""
    echo "📋 Configuration:"
    if [[ -f "$CONFIG_DIR/config.yml" ]]; then
        TUNNEL_ID=$(grep "^tunnel:" "$CONFIG_DIR/config.yml" | cut -d' ' -f2)
        HOSTNAME=$(grep -A 20 "ingress:" "$CONFIG_DIR/config.yml" | grep "hostname:" | head -1 | awk '{print $3}')
        echo "   Tunnel ID: $TUNNEL_ID"
        echo "   Hostname: $HOSTNAME"
        echo "   Config: $CONFIG_DIR/config.yml"
    else
        echo -e "   ${RED}No configuration found${NC}"
    fi

    echo ""
    echo "🌐 Tunnel List:"
    cloudflared tunnel list 2>/dev/null || echo "   Could not retrieve tunnel list"

    echo ""
    read -p "Press ENTER to continue..."
}

test_tunnel() {
    clear
    header "🧪 TUNNEL CONNECTIVITY TEST"
    header "=========================="
    echo ""

    if [[ ! -f "$CONFIG_DIR/config.yml" ]]; then
        error "No tunnel configuration found"
        read -p "Press ENTER to continue..."
        return
    fi

    HOSTNAME=$(grep -A 20 "ingress:" "$CONFIG_DIR/config.yml" | grep "hostname:" | head -1 | awk '{print $3}')

    if [[ -z "$HOSTNAME" ]]; then
        error "Could not determine hostname from configuration"
        read -p "Press ENTER to continue..."
        return
    fi

    log "Testing tunnel connectivity for: $HOSTNAME"
    echo ""

    # Test health endpoint
    echo "🏥 Testing health endpoint..."
    if curl -s -f -m 10 -w "Response time: %{time_total}s\n" "https://$HOSTNAME/health"; then
        log "✅ Health endpoint: OK"
    else
        error "❌ Health endpoint: FAILED"
    fi

    echo ""

    # Test webhook endpoint (expect failure due to validation)
    echo "🎣 Testing webhook endpoint..."
    if curl -s -f -m 10 -X POST "https://$HOSTNAME/webhook/orders" \
        -H "Content-Type: application/json" \
        -d '{"test": true}' 2>/dev/null; then
        log "✅ Webhook endpoint: Accessible"
    else
        warn "⚠️  Webhook endpoint: Protected (expected)"
    fi

    echo ""

    # Test docs endpoint
    echo "📚 Testing docs endpoint..."
    if curl -s -f -m 10 "https://$HOSTNAME/docs" >/dev/null 2>&1; then
        log "✅ Docs endpoint: OK"
    else
        warn "⚠️  Docs endpoint: Not accessible"
    fi

    echo ""
    read -p "Press ENTER to continue..."
}

show_logs() {
    clear
    header "📜 CLOUDFLARE TUNNEL LOGS"
    header "========================"
    echo ""
    echo "Showing last 50 log entries (Press Ctrl+C to exit)"
    echo ""

    sudo journalctl -u $SERVICE_NAME -n 50 -f
}

setup_new_tunnel() {
    log "🚀 Starting new tunnel setup..."

    # Check if cloudflared is properly installed and functional
    if ! command -v cloudflared >/dev/null 2>&1; then
        log "cloudflared not found, installing..."
        install_cloudflared
    elif ! cloudflared version >/dev/null 2>&1; then
        log "cloudflared found but not functional, reinstalling..."
        install_cloudflared
    else
        log "✅ cloudflared is already installed and functional"
    fi

    # Get domain configuration
    get_domain_info

    # Clean up any existing configuration
    cleanup_old_tunnel

    # Browser authentication
    if ! browser_authentication; then
        error "Authentication failed. Please try again."
        read -p "Press ENTER to continue..."
        return 1
    fi

    # Create tunnel
    if ! create_tunnel; then
        error "Tunnel creation failed"
        read -p "Press ENTER to continue..."
        return 1
    fi

    # Create/Update DNS record (may need to update if tunnel ID changed)
    if ! create_dns_record; then
        warn "DNS record creation failed, but continuing with tunnel setup"
        warn "You may need to manually update your DNS record"
    fi

    # Create configuration
    if ! create_tunnel_config; then
        error "Configuration creation failed"

        # If tunnel was recreated, we need to update DNS as well
        if [[ "${TUNNEL_RECREATED:-}" == "true" ]]; then
            log "Since tunnel was recreated, attempting DNS update again..."
            create_dns_record || warn "DNS update still failed - manual intervention may be needed"
        fi

        read -p "Press ENTER to continue..."
        return 1
    fi

    # Create systemd service
    if ! create_systemd_service; then
        error "Service creation failed"
        read -p "Press ENTER to continue..."
        return 1
    fi

    # Start and validate service
    if ! start_and_validate_service; then
        error "Service startup failed"
        read -p "Press ENTER to continue..."
        return 1
    fi

    # Update service configuration
    update_service_config

    # Test connectivity
    test_tunnel_connectivity

    # Show summary
    show_summary

    read -p "Press ENTER to continue..."
}

update_tunnel() {
    log "🔄 Updating tunnel configuration..."

    # Check if tunnel exists
    if [[ ! -f "$CONFIG_DIR/config.yml" ]]; then
        error "No existing tunnel configuration found"
        error "Please run 'New Tunnel Setup' first"
        read -p "Press ENTER to continue..."
        return 1
    fi

    # Get domain info (may be different)
    get_domain_info

    # Get current tunnel ID
    TUNNEL_ID=$(grep "^tunnel:" "$CONFIG_DIR/config.yml" | cut -d' ' -f2)

    log "Updating configuration for tunnel: $TUNNEL_ID"

    # Update DNS record
    create_dns_record

    # Recreate configuration
    create_tunnel_config

    # Restart service
    log "Restarting service with new configuration..."
    sudo systemctl restart $SERVICE_NAME

    # Validate
    start_and_validate_service

    # Update service config
    update_service_config

    # Test
    test_tunnel_connectivity

    log "✅ Tunnel update completed"
    read -p "Press ENTER to continue..."
}

reset_tunnel() {
    warn "🧹 This will completely reset the tunnel configuration"
    warn "All current settings will be lost!"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Reset cancelled"
        read -p "Press ENTER to continue..."
        return
    fi

    complete_cleanup

    log "✅ Tunnel reset completed"
    log "You can now run 'New Tunnel Setup' to configure a fresh tunnel"
    read -p "Press ENTER to continue..."
}

# API Token functions for DNS management
validate_api_token() {
    local token="$1"

    if [[ -z "$token" ]]; then
        return 1
    fi

    # Test the token
    local test_response
    test_response=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json")

    if echo "$test_response" | grep -q '"success":true'; then
        return 0
    else
        return 1
    fi
}

get_zone_id() {
    local domain="$1"
    local token="$2"

    local zone_response
    zone_response=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$domain" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json")

    echo "$zone_response" | python3 - <<'PY'
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('success') and data.get('result'):
        zone = data['result'][0]
        zone_id = zone.get('id', '')
        print(zone_id)
except Exception:
    pass
PY
}

list_tunnel_dns_records() {
    local domain="$1"
    local token="$2"

    local zone_id
    zone_id=$(get_zone_id "$domain" "$token")

    if [[ -z "$zone_id" ]]; then
        error "Could not get zone ID for domain: $domain"
        return 1
    fi

    log "Zone ID: $zone_id"

    local dns_response
    dns_response=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json")

    echo "$dns_response" | python3 - <<'PY'
import json
import sys

tunnel_keywords = ['printer', 'wix', 'pos', 'tunnel']

try:
    data = json.load(sys.stdin)
    if data.get('success'):
        records = data.get('result', [])
        tunnel_records = []

        for record in records:
            name = record.get('name', '').lower()
            content = record.get('content', '').lower()
            record_type = record.get('type', '')

            # Look for tunnel-related records
            is_tunnel_record = False

            # Check if it's a CNAME pointing to cfargotunnel.com
            if record_type == 'CNAME' and 'cfargotunnel.com' in content:
                is_tunnel_record = True

            # Check for tunnel-related keywords in name
            for keyword in tunnel_keywords:
                if keyword in name:
                    is_tunnel_record = True
                    break

            if is_tunnel_record:
                tunnel_records.append({
                    'id': record.get('id'),
                    'name': record.get('name'),
                    'type': record.get('type'),
                    'content': record.get('content'),
                    'ttl': record.get('ttl')
                })

        for record in tunnel_records:
            record_id = record['id']
            record_name = record['name']
            record_type = record['type']
            record_content = record['content']
            record_ttl = record['ttl']
            print(f"{record_id}|{record_name}|{record_type}|{record_content}|{record_ttl}")

except Exception as e:
    pass
PY
}

delete_dns_record() {
    local record_id="$1"
    local zone_id="$2"
    local token="$3"

    local delete_response
    delete_response=$(curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$zone_id/dns_records/$record_id" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json")

    if echo "$delete_response" | grep -q '"success":true'; then
        return 0
    else
        return 1
    fi
}

dns_cleanup_menu() {
    clear
    header "🗑️ DNS-RECORDS BEREINIGEN"
    header "=========================="
    echo ""
    echo "Diese Funktion bereinigt tunnel-bezogene DNS-Records in Cloudflare."
    echo "Benötigt einen API-Token mit Zone:DNS:Edit Berechtigung."
    echo ""
    header "📋 API-TOKEN ERSTELLEN:"
    echo "   1. Gehe zu https://dash.cloudflare.com/profile/api-tokens"
    echo "   2. Klicke 'Create Token'"
    echo "   3. Wähle 'Custom Token'"
    echo "   4. Berechtigungen: Zone:Zone:Read, Zone:DNS:Edit"
    echo "   5. Zone Resources: Include → Specific zone → deine-domain.com"
    echo ""

    echo -n "Enter your domain name (e.g., example.com): "
    read CLEANUP_DOMAIN

    if [[ -z "$CLEANUP_DOMAIN" ]]; then
        error "Domain name is required"
        read -p "Press ENTER to continue..."
        return
    fi

    echo -n "Enter your Cloudflare API Token: "
    read -s CLEANUP_API_TOKEN
    echo ""

    if [[ -z "$CLEANUP_API_TOKEN" ]]; then
        error "API Token is required"
        read -p "Press ENTER to continue..."
        return
    fi

    log "Validating API token..."
    if ! validate_api_token "$CLEANUP_API_TOKEN"; then
        error "Invalid API token or insufficient permissions"
        read -p "Press ENTER to continue..."
        return
    fi

    log "✅ API token is valid"

    log "Searching for tunnel-related DNS records..."
    local zone_id
    zone_id=$(get_zone_id "$CLEANUP_DOMAIN" "$CLEANUP_API_TOKEN")

    if [[ -z "$zone_id" ]]; then
        error "Could not get zone ID for domain: $CLEANUP_DOMAIN"
        read -p "Press ENTER to continue..."
        return
    fi

    local records
    records=$(list_tunnel_dns_records "$CLEANUP_DOMAIN" "$CLEANUP_API_TOKEN")

    if [[ -z "$records" ]]; then
        log "✅ No tunnel-related DNS records found"
        read -p "Press ENTER to continue..."
        return
    fi

    echo ""
    header "🔍 GEFUNDENE TUNNEL-RECORDS:"
    echo "-----------------------------"

    declare -a record_ids
    declare -a record_names
    local counter=1

    while IFS='|' read -r record_id record_name record_type record_content record_ttl; do
        if [[ -n "$record_id" ]]; then
            record_ids[counter]="$record_id"
            record_names[counter]="$record_name"
            printf "   %d) %s (%s) → %s\n" "$counter" "$record_name" "$record_type" "$record_content"
            ((counter++))
        fi
    done <<< "$records"

    if [[ $counter -eq 1 ]]; then
        log "✅ No tunnel-related DNS records found"
        read -p "Press ENTER to continue..."
        return
    fi

    echo ""
    echo "Optionen:"
    echo -e "   ${BOLD}a)${NC} Alle Records löschen"
    echo -e "   ${BOLD}s)${NC} Spezifische Records auswählen"
    echo -e "   ${BOLD}c)${NC} Abbrechen"
    echo ""

    read -p "Wähle eine Option (a/s/c): " cleanup_choice

    case $cleanup_choice in
        a|A)
            echo ""
            warn "WARNUNG: Alle tunnel-bezogenen DNS-Records werden gelöscht!"
            read -p "Sind Sie sicher? (y/N): " -r
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log "Abgebrochen"
                read -p "Press ENTER to continue..."
                return
            fi

            log "Lösche alle gefundenen Records..."
            for i in $(seq 1 $((counter-1))); do
                if delete_dns_record "${record_ids[i]}" "$zone_id" "$CLEANUP_API_TOKEN"; then
                    log "✅ Deleted: ${record_names[i]}"
                else
                    error "❌ Failed to delete: ${record_names[i]}"
                fi
            done
            ;;

        s|S)
            echo ""
            echo "Geben Sie die Nummern der zu löschenden Records ein (z.B. 1,3,5):"
            read -p "Records: " selected_records

            if [[ -z "$selected_records" ]]; then
                log "Keine Records ausgewählt"
                read -p "Press ENTER to continue..."
                return
            fi

            IFS=',' read -ra ADDR <<< "$selected_records"
            for num in "${ADDR[@]}"; do
                num=$(echo "$num" | xargs)  # trim whitespace
                if [[ "$num" =~ ^[0-9]+$ ]] && [[ $num -ge 1 ]] && [[ $num -lt $counter ]]; then
                    if delete_dns_record "${record_ids[num]}" "$zone_id" "$CLEANUP_API_TOKEN"; then
                        log "✅ Deleted: ${record_names[num]}"
                    else
                        error "❌ Failed to delete: ${record_names[num]}"
                    fi
                else
                    warn "Invalid record number: $num"
                fi
            done
            ;;

        *)
            log "Abgebrochen"
            ;;
    esac

    echo ""
    read -p "Press ENTER to continue..."
}

# Main menu loop
main() {
    while true; do
        show_menu
        read -p "Choose an option (0-7): " choice
        echo ""

        case $choice in
            1)
                setup_new_tunnel
                ;;
            2)
                update_tunnel
                ;;
            3)
                reset_tunnel
                ;;
            4)
                show_status
                ;;
            5)
                test_tunnel
                ;;
            6)
                show_logs
                ;;
            7)
                dns_cleanup_menu
                ;;
            0)
                log "Exiting Cloudflare Tunnel Manager"
                exit 0
                ;;
            *)
                error "Invalid option. Please choose 0-7."
                read -p "Press ENTER to continue..."
                ;;
        esac
    done
}

# Check if script is run with sudo (warn but don't exit)
if [[ $EUID -eq 0 ]]; then
    warn "This script should not be run as root directly"
    warn "It will use sudo when needed"
    echo ""
fi

# Start main menu
main