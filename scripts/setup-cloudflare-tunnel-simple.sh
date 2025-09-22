#!/bin/bash

# 🌐 Cloudflare Tunnel Simple Setup Script
# Wix Printer Service - Robust Version with Error Handling
# Version: 1.1
# Date: 2025-09-21

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

# Function to handle errors gracefully
handle_error() {
    local exit_code=$?
    local line_number=$1
    error "Script failed at line $line_number with exit code $exit_code"
    echo ""
    echo "🔍 TROUBLESHOOTING STEPS:"
    echo "1. Check your internet connection"
    echo "2. Verify Cloudflare credentials are correct"
    echo "3. Ensure domain is added to your Cloudflare account"
    echo "4. Try running with debug mode: bash -x $0"
    echo ""
    echo "💡 You can also try the manual setup:"
    echo "   ./setup-public-access.sh (for static IP)"
    echo "   ./setup-dynamic-dns.sh (for dynamic IP with DDNS)"
    echo ""
    exit $exit_code
}

# Set up error handling
trap 'handle_error $LINENO' ERR

echo ""
echo "=========================================="
echo "🌐 CLOUDFLARE TUNNEL SETUP (SIMPLE)"
echo "=========================================="
echo ""
echo "This script will set up a secure Cloudflare Tunnel for your"
echo "Wix Printer Service, eliminating the need for:"
echo ""
echo "❌ Static IP addresses"
echo "❌ Router port forwarding"
echo "❌ Manual SSL certificate management"
echo "❌ Firewall configuration"
echo ""

# Check prerequisites
log "🔍 Checking prerequisites..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for security reasons"
   exit 1
fi

# Check internet connectivity
if ! ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    error "No internet connection detected"
    exit 1
fi

log "✅ Prerequisites check passed"

# Get domain information
echo ""
echo "🌐 DOMAIN CONFIGURATION:"
echo "----------------------------------------"

while [[ -z "$DOMAIN" ]]; do
    echo ""
    echo "📋 DOMAIN REQUIREMENTS:"
    echo "   • Domain must be added to your Cloudflare account"
    echo "   • Nameservers must point to Cloudflare"
    echo "   • Example: example.com (not printer.example.com)"
    echo ""
    read -p "Enter your domain name (e.g., example.com): " DOMAIN
    
    if [[ -z "$DOMAIN" ]]; then
        warn "Domain name is required"
        continue
    fi
    
    # Basic domain validation
    if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$ ]]; then
        warn "Invalid domain format. Please enter just the domain (e.g., example.com)"
        DOMAIN=""
        continue
    fi
    
    break
done

echo ""
read -p "Enter subdomain for printer service (default: printer): " SUBDOMAIN
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

read -p "❓ Does this look correct? (y/N): " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Setup cancelled by user"
    exit 0
fi

# Get Cloudflare credentials
echo ""
echo "🔐 CLOUDFLARE CREDENTIALS:"
echo "----------------------------------------"
echo ""
echo "We need your Cloudflare credentials to set up the tunnel automatically."
echo ""
echo "📋 REQUIRED:"
echo "   • Cloudflare email address"
echo "   • Cloudflare Global API Key"
echo ""
echo "ℹ️  HOW TO GET GLOBAL API KEY:"
echo "   1. Go to https://dash.cloudflare.com/profile/api-tokens"
echo "   2. Scroll down to 'Global API Key'"
echo "   3. Click 'View' and enter your password"
echo "   4. Copy the key"
echo ""

while [[ -z "$CF_EMAIL" ]]; do
    read -p "Enter your Cloudflare email: " CF_EMAIL
    if [[ -z "$CF_EMAIL" ]]; then
        warn "Email is required"
    else
        log "✅ Email received: ${CF_EMAIL}"
    fi
done

echo ""
echo "Now we need your Cloudflare Global API Key..."
echo "👉 The key will be hidden as you type for security"
echo ""

while [[ -z "$CF_GLOBAL_KEY" ]]; do
    echo -n "Enter your Cloudflare Global API Key: "
    read -s CF_GLOBAL_KEY
    echo ""
    if [[ -z "$CF_GLOBAL_KEY" ]]; then
        warn "Global API Key is required"
        echo "Please try again..."
    else
        log "✅ API Key received (hidden for security)"
    fi
done

log "✅ Credentials collected"

# Install dependencies (jq)
echo ""
log "📦 Installing dependencies (jq)..."
if ! command -v jq >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y jq
    log "✅ jq installed successfully."
else
    log "jq is already installed."
fi

# Install cloudflared
echo ""
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

# Check if cloudflared is already installed
if command -v cloudflared >/dev/null 2>&1; then
    log "cloudflared is already installed"
else
    log "Downloading cloudflared for $ARCH..."
    
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CLOUDFLARED_ARCH"
    
    if ! curl -L --output /tmp/cloudflared "$CLOUDFLARED_URL"; then
        error "Failed to download cloudflared"
        exit 1
    fi
    
    sudo mv /tmp/cloudflared /usr/local/bin/
    sudo chmod +x /usr/local/bin/cloudflared
    
    log "✅ cloudflared installed successfully"
fi

# Test Cloudflare API connectivity
echo ""
log "🔗 Testing Cloudflare API connectivity..."

API_TEST=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user" \
    -H "X-Auth-Email: $CF_EMAIL" \
    -H "X-Auth-Key: $CF_GLOBAL_KEY" \
    -H "Content-Type: application/json")

if echo "$API_TEST" | grep -q '"success":true'; then
    log "✅ Cloudflare API connection successful"
else
    error "Failed to connect to Cloudflare API"
    echo "Response: $API_TEST"
    echo ""
    echo "🔍 POSSIBLE ISSUES:"
    echo "   • Incorrect email or Global API Key"
    echo "   • API key doesn't have sufficient permissions"
    echo "   • Network connectivity issues"
    exit 1
fi

# Check if domain exists in Cloudflare
log "🌐 Checking domain in Cloudflare..."

ZONE_CHECK=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
    -H "X-Auth-Email: $CF_EMAIL" \
    -H "X-Auth-Key: $CF_GLOBAL_KEY" \
    -H "Content-Type: application/json")

if echo "$ZONE_CHECK" | grep -q '"success":true' && echo "$ZONE_CHECK" | grep -q '"name":"'$DOMAIN'"'; then
    log "✅ Domain $DOMAIN found in Cloudflare"
else
    error "Domain $DOMAIN not found in your Cloudflare account"
    echo ""
    echo "🔍 REQUIRED STEPS:"
    echo "   1. Add $DOMAIN to your Cloudflare account"
    echo "   2. Update nameservers at your domain registrar"
    echo "   3. Wait for DNS propagation (5-30 minutes)"
    echo ""
    echo "📚 HELP: https://support.cloudflare.com/hc/en-us/articles/201720164"
    exit 1
fi

# Create API token for tunnel management
log "🔑 Creating secure API token for tunnel management..."

# Dynamically fetch permission group IDs
log "🔍 Fetching latest permission group IDs from Cloudflare..."
PERMISSIONS_JSON=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/permission_groups" \
    -H "X-Auth-Email: $CF_EMAIL" \
    -H "X-Auth-Key: $CF_GLOBAL_KEY" \
    -H "Content-Type: application/json")

if ! echo "$PERMISSIONS_JSON" | grep -q '"success":true'; then
    error "Failed to fetch permission groups from Cloudflare API."
    echo "Response: $PERMISSIONS_JSON"
    exit 1
fi

# Extract IDs using jq (now guaranteed to be installed)
ACCOUNT_SETTINGS_READ_ID=$(echo "$PERMISSIONS_JSON" | jq -r '.result[] | select(.name=="Account Settings Read") | .id')
ZONE_READ_ID=$(echo "$PERMISSIONS_JSON" | jq -r '.result[] | select(.name=="Zone Read") | .id')
DNS_WRITE_ID=$(echo "$PERMISSIONS_JSON" | jq -r '.result[] | select(.name=="DNS Write") | .id')
# Use a more specific 'contains' search to ensure only one ID is returned.
TUNNEL_WRITE_ID=$(echo "$PERMISSIONS_JSON" | jq -r '.result[] | select(.name | contains("Tunnel") and contains("Write")) | .id')

if [[ -z "$ACCOUNT_SETTINGS_READ_ID" || -z "$ZONE_READ_ID" || -z "$DNS_WRITE_ID" || -z "$TUNNEL_WRITE_ID" ]]; then
    error "Could not dynamically determine required permission IDs."
    echo "Account Settings Read ID: $ACCOUNT_SETTINGS_READ_ID"
    echo "Zone Read ID: $ZONE_READ_ID"
    echo "DNS Write ID: $DNS_WRITE_ID"
    echo "Tunnel Write ID: $TUNNEL_WRITE_ID"
    exit 1
fi

log "✅ Found required permission IDs successfully."

# Construct the JSON payload safely using jq
TOKEN_NAME="Wix Printer Tunnel - $(date +%Y%m%d-%H%M%S)"
NOT_BEFORE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EXPIRES_ON=$(date -u -d '+1 year' +%Y-%m-%dT%H:%M:%SZ)

JSON_PAYLOAD=$(jq -n \
  --arg name "$TOKEN_NAME" \
  --arg nb "$NOT_BEFORE" \
  --arg eo "$EXPIRES_ON" \
  --arg asrid "$ACCOUNT_SETTINGS_READ_ID" \
  --arg zrid "$ZONE_READ_ID" \
  --arg dwid "$DNS_WRITE_ID" \
  --arg twid "$TUNNEL_WRITE_ID" \
  '{
    "name": $name,
    "policies": [
      {
        "effect": "allow",
        "resources": {"com.cloudflare.api.account.zone.*": "*"},
        "permission_groups": [{"id": $zrid}, {"id": $dwid}]
      },
      {
        "effect": "allow",
        "resources": {"com.cloudflare.api.account.*": "*"},
        "permission_groups": [{"id": $asrid}, {"id": $twid}]
      }
    ],
    "not_before": $nb,
    "expires_on": $eo
  }')

echo "--- BEGIN JSON PAYLOAD ---"
echo "$JSON_PAYLOAD"
echo "--- END JSON PAYLOAD ---"

TOKEN_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/user/tokens" \
    -H "X-Auth-Email: $CF_EMAIL" \
    -H "X-Auth-Key: $CF_GLOBAL_KEY" \
    -H "Content-Type: application/json" \
    --data-raw "$JSON_PAYLOAD")

if echo "$TOKEN_RESPONSE" | grep -q '"success":true'; then
    CF_API_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"value":"[^"]*' | cut -d'"' -f4)
    
    if [[ -n "$CF_API_TOKEN" ]]; then
        log "✅ API token created successfully!"
        
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
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi

# Get Account ID for subsequent API calls
log "🔍 Getting Cloudflare Account ID..."
ACCOUNT_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

ACCOUNT_ID=$(echo "$ACCOUNT_RESPONSE" | jq -r '.result[0].id')

if [[ -z "$ACCOUNT_ID" ]]; then
    error "Could not determine Cloudflare Account ID from API token."
    exit 1
fi
log "✅ Found Account ID: $ACCOUNT_ID"

# --- Advanced Find-or-Create Tunnel Logic ---
log ""
log "🚇 Searching for a suitable Cloudflare Tunnel..."
TUNNEL_NAME="wix-pos-printer-tunnel" # The desired static name for new tunnels

# First, get all tunnels to perform an advanced search
ALL_TUNNELS_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel?is_deleted=false" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

# Priority 1: Find an already healthy tunnel from a previous run
TUNNEL_ID=$(echo "$ALL_TUNNELS_RESPONSE" | jq -r '[.result[] | select(.name | startswith("wix-printer")) | select(.status == "healthy")] | .[0].id')

if [[ -n "$TUNNEL_ID" && "$TUNNEL_ID" != "null" ]]; then
    log "✅ Found an existing HEALTHY tunnel from a previous run. Reusing it to avoid disruption. Tunnel ID: $TUNNEL_ID"
else
    log "ℹ️ No healthy tunnel found. Searching for tunnel by static name '$TUNNEL_NAME'..."
    # Priority 2: Find a tunnel by the static name, regardless of status
    TUNNEL_ID=$(echo "$ALL_TUNNELS_RESPONSE" | jq -r --arg name "$TUNNEL_NAME" '[.result[] | select(.name == $name)] | .[0].id')

    if [[ -n "$TUNNEL_ID" && "$TUNNEL_ID" != "null" ]]; then
        log "✅ Found existing tunnel named '$TUNNEL_NAME'. Reusing it. Tunnel ID: $TUNNEL_ID"
    else
        # Priority 3: Create a new tunnel with the static name
        log "ℹ️ No suitable tunnel found. Creating a new one named '$TUNNEL_NAME'..."
        TUNNEL_SECRET=$(openssl rand -base64 32)
        TUNNEL_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel" \
            -H "Authorization: Bearer $CF_API_TOKEN" \
            -H "Content-Type: application/json" \
            --data-raw '{"name":"'$TUNNEL_NAME'","tunnel_secret":"'$TUNNEL_SECRET'"}')

        if ! echo "$TUNNEL_RESPONSE" | jq -e '.success == true' > /dev/null; then
            error "Failed to create tunnel via API."
            echo "Response: $TUNNEL_RESPONSE"
            exit 1
        fi

        TUNNEL_ID=$(echo "$TUNNEL_RESPONSE" | jq -r '.result.id')
        log "✅ Tunnel created successfully! Tunnel ID: $TUNNEL_ID"
    fi
fi

# --- Cleanup old, inactive tunnels ---
log "🧹 Cleaning up old, inactive tunnels..."
OLD_TUNNELS_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel?is_deleted=false" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

# Select tunnels with the old naming convention that are inactive
echo "$OLD_TUNNELS_RESPONSE" | jq -c '.result[] | select(.name | startswith("wix-printer-")) | select(.status != "healthy")' | while read -r tunnel_json; do
    OLD_TUNNEL_ID=$(echo "$tunnel_json" | jq -r '.id')
    OLD_TUNNEL_NAME=$(echo "$tunnel_json" | jq -r '.name')
    log "🗑️ Deleting old, inactive tunnel: $OLD_TUNNEL_NAME (ID: $OLD_TUNNEL_ID)"
    curl -s -X DELETE "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$OLD_TUNNEL_ID" \
        -H "Authorization: Bearer $CF_API_TOKEN" \
        -H "Content-Type: application/json" > /dev/null
done
log "✅ Cleanup complete."


# --- Create Credentials File ---
# We always create a new secret and credentials file to ensure the service can connect,
# even if the old credentials were lost.
log "✍️ Creating/updating tunnel credentials file..."
TUNNEL_SECRET=$(openssl rand -base64 32)

# Rotate the tunnel secret via API
curl -s -X PATCH "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json" \
    --data-raw '{"tunnel_secret":"'$TUNNEL_SECRET'"}' > /dev/null
log "✅ Tunnel secret has been rotated for security."

# Create the credentials file for the cloudflared daemon
log "✍️ Creating tunnel credentials file..."
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/"$TUNNEL_ID".json << EOF
{
  "AccountTag": "$ACCOUNT_ID",
  "TunnelID": "$TUNNEL_ID",
  "TunnelSecret": "$TUNNEL_SECRET"
}
EOF
chmod 600 ~/.cloudflared/"$TUNNEL_ID".json
log "✅ Credentials file created."

# The TUNNEL_ID is now determined by the find-or-create logic.

# Create DNS record via API
log "🌐 Creating DNS record via API..."

# Get Zone ID
ZONE_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

ZONE_ID=$(echo "$ZONE_RESPONSE" | jq -r '.result[0].id')

if [[ -z "$ZONE_ID" ]]; then
    error "Could not determine Zone ID for domain $DOMAIN."
    exit 1
fi
log "✅ Found Zone ID: $ZONE_ID"

# Clean up existing DNS records for the same name to ensure idempotency
log "🧹 Checking for and cleaning up existing DNS records for $FULL_DOMAIN..."
EXISTING_RECORDS_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$FULL_DOMAIN" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json")

EXISTING_RECORD_IDS=$(echo "$EXISTING_RECORDS_RESPONSE" | jq -r '.result[].id')

if [[ -n "$EXISTING_RECORD_IDS" ]]; then
    for RECORD_ID in $EXISTING_RECORD_IDS; do
        log "🗑️ Deleting existing DNS record with ID: $RECORD_ID"
        DELETE_RESPONSE=$(curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
            -H "Authorization: Bearer $CF_API_TOKEN" \
            -H "Content-Type: application/json")
        if ! echo "$DELETE_RESPONSE" | jq -e '.success == true' > /dev/null; then
            warn "Failed to delete existing DNS record $RECORD_ID. This might cause issues."
        else
            log "✅ Existing DNS record deleted."
        fi
    done
else
    log "✅ No existing DNS records found. Proceeding to create a new one."
fi

# Create CNAME record pointing to the tunnel
DNS_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: application/json" \
    --data-raw '{
        "type": "CNAME",
        "name": "'$SUBDOMAIN'",
        "content": "'$TUNNEL_ID'.cfargotunnel.com",
        "ttl": 1,
        "proxied": true
    }')

if ! echo "$DNS_RESPONSE" | jq -e '.success == true' > /dev/null; then
    error "Failed to create DNS record via API."
    echo "Response: $DNS_RESPONSE"
    exit 1
fi
log "✅ DNS record created successfully for $FULL_DOMAIN"

# Create tunnel configuration
log "⚙️ Creating tunnel configuration..."

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
EOF

# Copy tunnel credentials
TUNNEL_CREDS="$HOME/.cloudflared/$TUNNEL_ID.json"
if [[ -f "$TUNNEL_CREDS" ]]; then
    sudo cp "$TUNNEL_CREDS" "$TUNNEL_CONFIG_DIR/"
    log "✅ Tunnel credentials configured"
else
    error "Tunnel credentials not found at $TUNNEL_CREDS"
    exit 1
fi

# Create systemd service
log "🔧 Creating systemd service..."

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

# Update environment configuration
log "⚙️ Updating service configuration..."

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

# Wait for tunnel to be ready
log "⏳ Waiting 30 seconds for tunnel to be ready..."
sleep 30

# Test tunnel connectivity
log "🧪 Testing tunnel connectivity..."

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

# Cleanup temporary files
rm -f "$TEMP_CREDS"

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
log "✅ Your printer service is now accessible from anywhere!"
log "   No router configuration or static IP needed!"

log "Cloudflare Tunnel setup completed successfully!" >&2

# Output the full domain so the parent script can capture it
echo "$FULL_DOMAIN"
