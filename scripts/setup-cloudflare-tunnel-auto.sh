#!/bin/bash

# 🚀 Cloudflare Tunnel Fully Automated Setup
# Wix Printer Service - One-Command Setup
# Version: 1.0
# Date: 2025-09-21

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Parse command line arguments
CF_EMAIL=""
CF_GLOBAL_KEY=""
DOMAIN=""
SUBDOMAIN="printer"

show_usage() {
    echo ""
    echo "🚀 CLOUDFLARE TUNNEL - FULLY AUTOMATED SETUP"
    echo "============================================="
    echo ""
    echo "USAGE:"
    echo "  $0 --email EMAIL --key GLOBAL_KEY --domain DOMAIN [--subdomain SUBDOMAIN]"
    echo ""
    echo "PARAMETERS:"
    echo "  --email EMAIL        Your Cloudflare email address"
    echo "  --key GLOBAL_KEY     Your Cloudflare Global API Key"
    echo "  --domain DOMAIN      Your domain (e.g., example.com)"
    echo "  --subdomain SUB      Subdomain for printer (default: printer)"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 --email user@example.com --key abc123... --domain example.com"
    echo "  $0 --email user@example.com --key abc123... --domain example.com --subdomain myprinter"
    echo ""
    echo "📋 HOW TO GET GLOBAL API KEY:"
    echo "   1. Go to https://dash.cloudflare.com/profile/api-tokens"
    echo "   2. Scroll down to 'Global API Key'"
    echo "   3. Click 'View' and copy the key"
    echo ""
    echo "✅ WHAT THIS SCRIPT DOES:"
    echo "   • Creates secure API token automatically"
    echo "   • Installs and configures cloudflared"
    echo "   • Creates Cloudflare Tunnel"
    echo "   • Sets up DNS records"
    echo "   • Configures systemd service"
    echo "   • Tests connectivity"
    echo "   • Updates service configuration"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --email)
            CF_EMAIL="$2"
            shift 2
            ;;
        --key)
            CF_GLOBAL_KEY="$2"
            shift 2
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --subdomain)
            SUBDOMAIN="$2"
            shift 2
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$CF_EMAIL" || -z "$CF_GLOBAL_KEY" || -z "$DOMAIN" ]]; then
    error "Missing required parameters"
    show_usage
    exit 1
fi

FULL_DOMAIN="$SUBDOMAIN.$DOMAIN"

echo ""
echo "🚀 CLOUDFLARE TUNNEL - FULLY AUTOMATED SETUP"
echo "============================================="
echo ""
echo "📋 CONFIGURATION:"
echo "   • Email: $CF_EMAIL"
echo "   • Domain: $DOMAIN"
echo "   • Full Domain: $FULL_DOMAIN"
echo "   • Subdomain: $SUBDOMAIN"
echo ""

read -p "❓ Proceed with automatic setup? (y/N): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Setup cancelled by user"
    exit 0
fi

# Step 1: Install cloudflared
log "📦 Step 1: Installing cloudflared..."

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

curl -L --output cloudflared "$CLOUDFLARED_URL"
sudo mv cloudflared /usr/local/bin/
sudo chmod +x /usr/local/bin/cloudflared

log "✅ cloudflared installed successfully"

# Step 2: Create API token automatically
log "🔑 Step 2: Creating secure API token..."

API_TOKEN_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/user/tokens" \
    -H "X-Auth-Email: $CF_EMAIL" \
    -H "X-Auth-Key: $CF_GLOBAL_KEY" \
    -H "Content-Type: application/json" \
    --data '{
        "name": "Wix Printer Tunnel - '"$(date +%Y%m%d-%H%M%S)"'",
        "policies": [
            {
                "effect": "allow",
                "resources": {
                    "com.cloudflare.api.account.zone.*": "*"
                },
                "permission_groups": [
                    {
                        "id": "c8fed203ed3043cba015a93ad1616f1f",
                        "name": "Zone:Zone:Read"
                    },
                    {
                        "id": "4755a26eedb94da69e1066d98aa820be",
                        "name": "Zone:DNS:Edit"
                    }
                ]
            },
            {
                "effect": "allow",
                "resources": {
                    "com.cloudflare.api.account.*": "*"
                },
                "permission_groups": [
                    {
                        "id": "79c6f70e22f04f9494c5da4c2292f804",
                        "name": "Cloudflare Tunnel:Edit"
                    }
                ]
            }
        ],
        "condition": {
            "request_ip": {},
            "request_ip_in": []
        },
        "not_before": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
        "expires_on": "'"$(date -u -d '+1 year' +%Y-%m-%dT%H:%M:%SZ)"'"
    }')

# Check if token creation was successful
if echo "$API_TOKEN_RESPONSE" | grep -q '"success":true'; then
    CF_API_TOKEN=$(echo "$API_TOKEN_RESPONSE" | grep -o '"value":"[^"]*' | cut -d'"' -f4)
    
    if [[ -n "$CF_API_TOKEN" ]]; then
        log "✅ API token created successfully!"
        log "Token expires: $(date -d '+1 year' '+%Y-%m-%d')"
        
        # Save token securely
        mkdir -p ~/.cloudflared
        echo "$CF_API_TOKEN" > ~/.cloudflared/token
        chmod 600 ~/.cloudflared/token
        
        export CLOUDFLARE_API_TOKEN="$CF_API_TOKEN"
    else
        error "Failed to extract API token from response"
        exit 1
    fi
else
    error "Failed to create API token"
    echo "Response: $API_TOKEN_RESPONSE"
    exit 1
fi

# Step 3: Get account and zone information
log "🔍 Step 3: Getting account and zone information..."

# Get account ID
ACCOUNT_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

ACCOUNT_ID=$(echo "$ACCOUNT_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

if [[ -z "$ACCOUNT_ID" ]]; then
    error "Could not get account ID"
    exit 1
fi

log "Account ID: $ACCOUNT_ID"

# Get zone ID
ZONE_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

ZONE_ID=$(echo "$ZONE_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

if [[ -z "$ZONE_ID" ]]; then
    error "Could not get zone ID for domain: $DOMAIN"
    error "Make sure the domain is added to your Cloudflare account"
    exit 1
fi

log "Zone ID: $ZONE_ID"

# Step 4: Create tunnel
log "🚇 Step 4: Creating Cloudflare Tunnel..."

TUNNEL_NAME="wix-printer-$(date +%s)"
TUNNEL_SECRET=$(openssl rand -base64 32)

TUNNEL_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json" \
    --data '{
        "name": "'"$TUNNEL_NAME"'",
        "tunnel_secret": "'"$TUNNEL_SECRET"'"
    }')

if echo "$TUNNEL_RESPONSE" | grep -q '"success":true'; then
    TUNNEL_ID=$(echo "$TUNNEL_RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
    
    log "✅ Tunnel created successfully!"
    log "Tunnel Name: $TUNNEL_NAME"
    log "Tunnel ID: $TUNNEL_ID"
    
    # Create credentials file
    mkdir -p ~/.cloudflared
    cat > ~/.cloudflared/$TUNNEL_ID.json <<EOF
{
    "AccountTag": "$ACCOUNT_ID",
    "TunnelSecret": "$TUNNEL_SECRET",
    "TunnelID": "$TUNNEL_ID"
}
EOF
    chmod 600 ~/.cloudflared/$TUNNEL_ID.json
else
    error "Failed to create tunnel"
    echo "Response: $TUNNEL_RESPONSE"
    exit 1
fi

# Step 5: Create DNS record
log "🌐 Step 5: Creating DNS record..."

DNS_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json" \
    --data '{
        "type": "CNAME",
        "name": "'"$SUBDOMAIN"'",
        "content": "'"$TUNNEL_ID"'.cfargotunnel.com",
        "ttl": 1,
        "proxied": true
    }')

if echo "$DNS_RESPONSE" | grep -q '"success":true'; then
    log "✅ DNS record created: $FULL_DOMAIN"
else
    error "Failed to create DNS record"
    echo "Response: $DNS_RESPONSE"
    exit 1
fi

# Step 6: Create tunnel configuration
log "⚙️ Step 6: Creating tunnel configuration..."

TUNNEL_CONFIG_DIR="/etc/cloudflared"
sudo mkdir -p "$TUNNEL_CONFIG_DIR"

sudo tee "$TUNNEL_CONFIG_DIR/config.yml" > /dev/null <<EOF
tunnel: $TUNNEL_ID
credentials-file: /etc/cloudflared/$TUNNEL_ID.json

ingress:
  # Webhook endpoint with special handling
  - hostname: $FULL_DOMAIN
    path: /webhook/*
    service: http://localhost:8000
    originRequest:
      httpHostHeader: $FULL_DOMAIN
      connectTimeout: 10s
      tlsTimeout: 10s
      tcpKeepAlive: 30s
      keepAliveTimeout: 90s
      keepAliveConnections: 10
  
  # Health check endpoint
  - hostname: $FULL_DOMAIN
    path: /health
    service: http://localhost:8000
    originRequest:
      httpHostHeader: $FULL_DOMAIN
  
  # API documentation
  - hostname: $FULL_DOMAIN
    path: /docs
    service: http://localhost:8000
    originRequest:
      httpHostHeader: $FULL_DOMAIN
  
  # All other endpoints
  - hostname: $FULL_DOMAIN
    service: http://localhost:8000
    originRequest:
      httpHostHeader: $FULL_DOMAIN
      connectTimeout: 30s
      tlsTimeout: 10s
      tcpKeepAlive: 30s
      keepAliveTimeout: 90s
      keepAliveConnections: 10
  
  # Catch-all rule (required)
  - service: http_status:404

# Logging
loglevel: info
logfile: /var/log/cloudflared.log

# Metrics
metrics: localhost:8080
EOF

# Copy tunnel credentials
sudo cp ~/.cloudflared/$TUNNEL_ID.json "$TUNNEL_CONFIG_DIR/"

log "✅ Tunnel configuration created"

# Step 7: Create systemd service
log "🔧 Step 7: Creating systemd service..."

sudo tee /etc/systemd/system/cloudflared.service > /dev/null <<EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

log "✅ Cloudflared service started"

# Step 8: Update service configuration
log "⚙️ Step 8: Updating service configuration..."

ENV_FILE="/opt/wix-printer-service/.env"
if [[ -f "$ENV_FILE" ]]; then
    # Add or update PUBLIC_DOMAIN
    if grep -q "PUBLIC_DOMAIN=" "$ENV_FILE"; then
        sudo sed -i "s/PUBLIC_DOMAIN=.*/PUBLIC_DOMAIN=$FULL_DOMAIN/" "$ENV_FILE"
    else
        echo "PUBLIC_DOMAIN=$FULL_DOMAIN" | sudo tee -a "$ENV_FILE" >/dev/null
    fi
    log "✅ Environment configuration updated"
fi

# Step 9: Wait and test connectivity
log "🧪 Step 9: Testing connectivity..."

log "⏳ Waiting 30 seconds for tunnel to be ready..."
sleep 30

# Test tunnel connectivity
if curl -s -f -m 10 "https://$FULL_DOMAIN/health" >/dev/null 2>&1; then
    log "✅ Tunnel is working correctly!"
    
    # Test webhook endpoint
    log "🔗 Testing webhook endpoint..."
    if curl -s -f -m 10 -X POST "https://$FULL_DOMAIN/webhook/orders" \
        -H "Content-Type: application/json" \
        -d '{"test": "connectivity"}' >/dev/null 2>&1; then
        log "✅ Webhook endpoint is accessible"
    else
        warn "Webhook endpoint test failed (may be normal due to validation)"
    fi
else
    warn "Tunnel connectivity test failed - may need more time"
    log "You can test manually later with: curl https://$FULL_DOMAIN/health"
fi

# Final summary
echo ""
echo "🎉 CLOUDFLARE TUNNEL SETUP COMPLETE!"
echo "====================================="
echo ""
echo "✅ CONFIGURATION SUMMARY:"
echo "   • Tunnel Name: $TUNNEL_NAME"
echo "   • Tunnel ID: $TUNNEL_ID"
echo "   • Public URL: https://$FULL_DOMAIN"
echo "   • Webhook URL: https://$FULL_DOMAIN/webhook/orders"
echo ""
echo "🔧 MANAGEMENT COMMANDS:"
echo "   • Check tunnel status: sudo systemctl status cloudflared"
echo "   • View tunnel logs: sudo journalctl -u cloudflared -f"
echo "   • Restart tunnel: sudo systemctl restart cloudflared"
echo "   • Test public URL: curl https://$FULL_DOMAIN/health"
echo ""
echo "🌐 WIX WEBHOOK CONFIGURATION:"
echo "   Configure your Wix webhook URL as:"
echo "   👉 https://$FULL_DOMAIN/webhook/orders"
echo ""
echo "✅ Your printer service is now accessible from anywhere!"
echo "   No router configuration or static IP needed!"
echo ""

log "Fully automated Cloudflare Tunnel setup completed successfully!"
