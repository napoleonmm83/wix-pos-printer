# Cache permission groups to avoid multiple API calls
CF_PERMISSION_GROUPS_JSON=""
CF_PERMISSION_GROUPS_FILE=""

fetch_permission_groups() {
    if [[ -n "$CF_PERMISSION_GROUPS_JSON" ]]; then
        return 0
    fi

    if [[ -z "$CF_EMAIL" || -z "$CF_GLOBAL_KEY" ]]; then
        error "DEBUG: CF_EMAIL or CF_GLOBAL_KEY is empty"
        return 1
    fi

    log "DEBUG: Calling Cloudflare permission groups API..."
    CF_PERMISSION_GROUPS_JSON=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/permission_groups" \
        -H "X-Auth-Email: $CF_EMAIL" \
        -H "X-Auth-Key: $CF_GLOBAL_KEY" \
        -H "Content-Type: application/json")

    if [[ -z "$CF_PERMISSION_GROUPS_JSON" ]]; then
        error "Cloudflare permission group call returned empty response"
        return 1
    fi

    log "DEBUG: API response length: ${#CF_PERMISSION_GROUPS_JSON} characters"
    
    if ! echo "$CF_PERMISSION_GROUPS_JSON" | grep -q '"success":true'; then
        error "Unable to fetch Cloudflare permission groups."
        echo "DEBUG: Full API response:"
        echo "$CF_PERMISSION_GROUPS_JSON"
        CF_PERMISSION_GROUPS_JSON=""
        return 1
    fi

    log "DEBUG: Permission groups fetched successfully"

    if [[ -z "$CF_PERMISSION_GROUPS_FILE" ]]; then
        CF_PERMISSION_GROUPS_FILE=$(mktemp)
        trap '[[ -n "$CF_PERMISSION_GROUPS_FILE" && -f "$CF_PERMISSION_GROUPS_FILE" ]] && rm -f "$CF_PERMISSION_GROUPS_FILE"' EXIT
    fi

    printf '%s' "$CF_PERMISSION_GROUPS_JSON" > "$CF_PERMISSION_GROUPS_FILE"
    return 0
}

get_permission_group_id() {
    local name="$1"
    [[ -z "$name" ]] && return 1

    fetch_permission_groups || return 1

    local id
    id=$(python3 - "$name" "$CF_PERMISSION_GROUPS_FILE" <<'PY'
import json
import sys

if len(sys.argv) < 3:
    sys.exit(1)

name = sys.argv[1]
file_path = sys.argv[2]

NAME_ALIASES = {
    "Zone:Zone:Read": ["Zone:Zone:Read", "Zone Read"],
    "Zone:DNS:Edit": ["Zone:DNS:Edit", "DNS Write", "DNS Edit"],
    "Cloudflare Tunnel:Edit": ["Cloudflare Tunnel:Edit", "Cloudflare Tunnel Write", "Cloudflare Tunnel Read"],
}

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception:
    sys.exit(1)

aliases = NAME_ALIASES.get(name, [name])

for candidate in aliases:
    for item in data.get("result", []):
        if item.get("name") == candidate:
            print(item.get("id", ""))
            sys.exit(0)

sys.exit(1)
PY
)

    if [[ -z "$id" ]]; then
        error "Permission group '$name' not found or could not be parsed."
        echo "$CF_PERMISSION_GROUPS_JSON"
        return 1
    fi

    echo "$id"
    return 0
}
#!/bin/bash

# 🌐 Cloudflare Tunnel Setup Script
# Wix Printer Service - Dynamic IP Solution
# Version: 1.0
# Date: 2025-09-21

set -e  # Exit on any error

# Debug mode - uncomment for troubleshooting
# set -x

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

echo ""
echo "=========================================="
echo "🌐 CLOUDFLARE TUNNEL SETUP"
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
echo "✅ BENEFITS:"
echo "   • Works with any internet connection"
echo "   • Automatic SSL certificates"
echo "   • Built-in DDoS protection"
echo "   • No router configuration needed"
echo "   • Enterprise-grade security"
echo ""

# Prerequisites check
echo "📋 PREREQUISITES:"
echo "   1. Cloudflare account (free)"
echo "   2. Domain name added to Cloudflare"
echo "   3. Cloudflare API token or login credentials"
echo ""

read -p "❓ Do you have a Cloudflare account and domain ready? (y/N): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "📚 SETUP INSTRUCTIONS:"
    echo ""
    echo "1️⃣ CREATE CLOUDFLARE ACCOUNT:"
    echo "   • Go to https://cloudflare.com"
    echo "   • Sign up for free account"
    echo ""
    echo "2️⃣ ADD YOUR DOMAIN:"
    echo "   • Add your domain to Cloudflare"
    echo "   • Update nameservers at your domain registrar"
    echo "   • Wait for DNS propagation (5-30 minutes)"
    echo ""
    echo "3️⃣ GET API TOKEN:"
    echo "   • Go to Cloudflare Dashboard → My Profile → API Tokens"
    echo "   • Create Token → Custom Token"
    echo "   • Permissions: Zone:Zone:Read, Zone:DNS:Edit"
    echo "   • Zone Resources: Include → Specific zone → your-domain.com"
    echo ""
    echo "💡 Come back and run this script when ready!"
    exit 0
fi

# Get domain information
echo "🌐 DOMAIN CONFIGURATION:"
echo "----------------------------------------"
while [[ -z "$DOMAIN" ]]; do
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
log "  Full Domain: $FULL_DOMAIN"
log "  This will be your webhook URL: https://$FULL_DOMAIN/webhook/orders"
echo ""

# Install cloudflared
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

curl -L --output cloudflared "$CLOUDFLARED_URL"
sudo mv cloudflared /usr/local/bin/
sudo chmod +x /usr/local/bin/cloudflared

log "✅ cloudflared installed successfully"

# Authenticate with Cloudflare
echo ""
echo "🔐 CLOUDFLARE AUTHENTICATION:"
echo "----------------------------------------"
echo ""
echo "You have three options to authenticate:"
echo ""
echo "1️⃣ AUTOMATIC API SETUP (RECOMMENDED) ⭐"
echo "   • Fully automated with API token"
echo "   • No browser interaction needed"
echo "   • Creates API token automatically"
echo "   • Most secure and reliable"
echo ""
echo "2️⃣ MANUAL API TOKEN"
echo "   • Use your existing API token"
echo "   • No browser required"
echo "   • Advanced users"
echo ""
echo "3️⃣ BROWSER LOGIN"
echo "   • Interactive browser login"
echo "   • Good for first-time users"
echo "   • Requires manual interaction"
echo ""

# Function to create API token automatically
create_api_token_automatically() {
    echo ""
    echo "🔑 AUTOMATIC API TOKEN CREATION:"
    echo "----------------------------------------"
    echo ""
    echo "We'll create a secure API token automatically for tunnel management."
    echo ""
    echo "📋 REQUIRED CREDENTIALS:"
    echo "   • Cloudflare email address"
    echo "   • Cloudflare Global API Key (for initial setup only)"
    echo ""
    echo "ℹ️  HOW TO GET GLOBAL API KEY:"
    echo "   1. Go to https://dash.cloudflare.com/profile/api-tokens"
    echo "   2. Scroll down to 'Global API Key'"
    echo "   3. Click 'View' and copy the key"
    echo ""
    
    echo -n "Enter your Cloudflare email: "
    read CF_EMAIL
    
    echo -n "Enter your Cloudflare Global API Key: "
    read -s CF_GLOBAL_KEY
    echo ""
    
    if [[ -z "$CF_EMAIL" || -z "$CF_GLOBAL_KEY" ]]; then
        error "Email and Global API Key are required"
        return 1
    fi
    
    log "🔧 Creating dedicated API token for tunnel management..."
    
    log "DEBUG: Fetching permission group IDs..."
    local zone_read_id zone_dns_edit_id tunnel_edit_id
    
    log "DEBUG: Getting Zone:Zone:Read permission ID..."
    zone_read_id=$(get_permission_group_id "Zone:Zone:Read")
    if [[ $? -ne 0 || -z "$zone_read_id" ]]; then
        error "Failed to get Zone:Zone:Read permission ID"
        return 1
    fi
    log "DEBUG: Zone:Zone:Read ID = $zone_read_id"
    
    log "DEBUG: Getting Zone:DNS:Edit permission ID..."
    zone_dns_edit_id=$(get_permission_group_id "Zone:DNS:Edit")
    if [[ $? -ne 0 || -z "$zone_dns_edit_id" ]]; then
        error "Failed to get Zone:DNS:Edit permission ID"
        return 1
    fi
    log "DEBUG: Zone:DNS:Edit ID = $zone_dns_edit_id"
    
    log "DEBUG: Getting Cloudflare Tunnel:Edit permission ID..."
    tunnel_edit_id=$(get_permission_group_id "Cloudflare Tunnel:Edit")
    if [[ $? -ne 0 || -z "$tunnel_edit_id" ]]; then
        error "Failed to get Cloudflare Tunnel:Edit permission ID"
        return 1
    fi
    log "DEBUG: Cloudflare Tunnel:Edit ID = $tunnel_edit_id"
    
    log "DEBUG: All permission IDs retrieved successfully, creating token..."

    local token_payload_file
    token_payload_file=$(mktemp)
    trap '[[ -n "$token_payload_file" && -f "$token_payload_file" ]] && rm -f "$token_payload_file"' RETURN

    log "DEBUG: Writing token payload to $token_payload_file"
    cat > "$token_payload_file" <<EOF
{
  "name": "Wix Printer Tunnel - $(date -u +%Y%m%d-%H%M%S)",
  "policies": [
    {
      "effect": "allow",
      "resources": {
        "com.cloudflare.api.account.zone.*": "*"
      },
      "permission_groups": [
        {
          "id": "$zone_read_id",
          "name": "Zone Read"
        },
        {
          "id": "$zone_dns_edit_id",
          "name": "DNS Write"
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
          "id": "$tunnel_edit_id",
          "name": "Cloudflare Tunnel Write"
        }
      ]
    }
  ],
  "not_before": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "expires_on": "$(date -u -d '+1 year' +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    # Create API token with minimal required permissions
    API_TOKEN_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/user/tokens" \
        -H "X-Auth-Email: $CF_EMAIL" \
        -H "X-Auth-Key: $CF_GLOBAL_KEY" \
        -H "Content-Type: application/json" \
        --data @"$token_payload_file")
    
    # Check if token creation was successful
    if echo "$API_TOKEN_RESPONSE" | grep -q '"success":true'; then
        CF_API_TOKEN=$(echo "$API_TOKEN_RESPONSE" | grep -o '"value":"[^"]*' | cut -d'"' -f4)
        
        if [[ -n "$CF_API_TOKEN" ]]; then
            log "✅ API token created successfully!"
            log "Token expires: $(date -d '+1 year' '+%Y-%m-%d')"
            
            # Save token securely for cloudflared
            mkdir -p ~/.cloudflared
            echo "$CF_API_TOKEN" > ~/.cloudflared/token
            chmod 600 ~/.cloudflared/token
            
            # Set environment variable
            export CLOUDFLARE_API_TOKEN="$CF_API_TOKEN"
            
            # Create credentials file for cloudflared
            cat > ~/.cloudflared/cert.pem <<EOF
# Cloudflare API Token for Tunnel Management
# Created: $(date)
# Domain: $DOMAIN
# Token: $CF_API_TOKEN
EOF
            chmod 600 ~/.cloudflared/cert.pem
            
            return 0
        else
            error "Failed to extract API token from response"
            return 1
        fi
    else
        error "Failed to create API token"
        error "Token payload was:"
        cat "$token_payload_file" >&2
        echo "$API_TOKEN_RESPONSE"
        return 1
    fi
}

# Function to authenticate with API token
authenticate_with_api_token() {
    local token="$1"
    
    # Test the token
    TEST_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json")
    
    if echo "$TEST_RESPONSE" | grep -q '"success":true'; then
        log "✅ API token is valid!"
        
        # Set up cloudflared with API token
        export CLOUDFLARE_API_TOKEN="$token"
        
        # Save token for cloudflared
        mkdir -p ~/.cloudflared
        echo "$token" > ~/.cloudflared/token
        chmod 600 ~/.cloudflared/token
        
        return 0
    else
        error "Invalid API token"
        echo "Response: $TEST_RESPONSE"
        return 1
    fi
}

while true; do
    read -p "Choose authentication method (1-3): " auth_choice
    case $auth_choice in
        1)
            if create_api_token_automatically; then
                log "✅ Automatic API setup completed!"
                break
            else
                error "Automatic API setup failed, please try another method"
                continue
            fi
            ;;
        2)
            echo ""
            echo "🔑 MANUAL API TOKEN SETUP:"
            echo ""
            echo "📋 REQUIRED PERMISSIONS:"
            echo "   • Zone:Zone:Read"
            echo "   • Zone:DNS:Edit"
            echo "   • Cloudflare Tunnel:Edit"
            echo ""
            echo "🔗 Create token at: https://dash.cloudflare.com/profile/api-tokens"
            echo ""
            echo -n "Enter your Cloudflare API Token: "
            read -s CF_API_TOKEN
            echo ""
            
            if [[ -z "$CF_API_TOKEN" ]]; then
                error "API Token is required"
                continue
            fi
            
            if authenticate_with_api_token "$CF_API_TOKEN"; then
                break
            else
                continue
            fi
            ;;
        3)
            log "🌐 Opening browser for Cloudflare login..."
            echo ""
            echo "📋 INSTRUCTIONS:"
            echo "   1. Browser will open to Cloudflare login"
            echo "   2. Log in to your Cloudflare account"
            echo "   3. Authorize cloudflared access"
            echo "   4. Return to this terminal when done"
            echo ""
            read -p "Press ENTER to open browser..."
            
            if cloudflared tunnel login; then
                log "✅ Authentication successful!"
                break
            else
                error "Authentication failed"
                continue
            fi
            ;;
        *)
            echo "❌ Please enter 1, 2, or 3"
            ;;
    esac
done

# Create tunnel
echo ""
log "🚇 Creating Cloudflare Tunnel..."

TUNNEL_NAME="wix-printer-$(date +%s)"
log "Tunnel name: $TUNNEL_NAME"

# Function to create tunnel via API (more reliable)
create_tunnel_via_api() {
    if [[ -n "$CLOUDFLARE_API_TOKEN" ]]; then
        log "🔧 Creating tunnel via Cloudflare API..."
        
        # Get account ID first
        ACCOUNT_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts" \
            -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
            -H "Content-Type: application/json")
        
        ACCOUNT_ID=$(echo "$ACCOUNT_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
        
        if [[ -z "$ACCOUNT_ID" ]]; then
            warn "Could not get account ID via API, falling back to cloudflared"
            return 1
        fi
        
        log "Account ID: $ACCOUNT_ID"
        
        # Create tunnel via API
        TUNNEL_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel" \
            -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
            -H "Content-Type: application/json" \
            --data '{
                "name": "'"$TUNNEL_NAME"'",
                "tunnel_secret": "'"$(openssl rand -base64 32)"'"
            }')
        
        if echo "$TUNNEL_RESPONSE" | grep -q '"success":true'; then
            TUNNEL_ID=$(echo "$TUNNEL_RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
            TUNNEL_SECRET=$(echo "$TUNNEL_RESPONSE" | grep -o '"tunnel_secret":"[^"]*' | cut -d'"' -f4)
            
            log "✅ Tunnel created via API!"
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
            
            return 0
        else
            warn "API tunnel creation failed, falling back to cloudflared"
            echo "Response: $TUNNEL_RESPONSE"
            return 1
        fi
    else
        return 1
    fi
}

# Try API first, fallback to cloudflared
if ! create_tunnel_via_api; then
    log "🔧 Creating tunnel via cloudflared..."
    if cloudflared tunnel create "$TUNNEL_NAME"; then
        log "✅ Tunnel created successfully"
        
        # Get tunnel ID
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
        if [[ -z "$TUNNEL_ID" ]]; then
            error "Could not find tunnel ID"
            exit 1
        fi
        log "Tunnel ID: $TUNNEL_ID"
    else
        error "Failed to create tunnel"
        exit 1
    fi
fi

# Create DNS record
log "🌐 Creating DNS record..."

# Function to create DNS record via API
create_dns_via_api() {
    if [[ -n "$CLOUDFLARE_API_TOKEN" ]]; then
        log "🔧 Creating DNS record via Cloudflare API..."
        
        # Get zone ID
        ZONE_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
            -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
            -H "Content-Type: application/json")
        
        ZONE_ID=$(echo "$ZONE_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
        
        if [[ -z "$ZONE_ID" ]]; then
            warn "Could not get zone ID via API, falling back to cloudflared"
            return 1
        fi
        
        log "Zone ID: $ZONE_ID"
        
        # Create CNAME record pointing to tunnel
        DNS_RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
            -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
            -H "Content-Type: application/json" \
            --data '{
                "type": "CNAME",
                "name": "'"$SUBDOMAIN"'",
                "content": "'"$TUNNEL_ID"'.cfargotunnel.com",
                "ttl": 1,
                "proxied": true
            }')
        
        if echo "$DNS_RESPONSE" | grep -q '"success":true'; then
            log "✅ DNS record created via API: $FULL_DOMAIN"
            return 0
        else
            warn "API DNS creation failed, falling back to cloudflared"
            echo "Response: $DNS_RESPONSE"
            return 1
        fi
    else
        return 1
    fi
}

# Try API first, fallback to cloudflared
if ! create_dns_via_api; then
    log "🔧 Creating DNS record via cloudflared..."
    if cloudflared tunnel route dns "$TUNNEL_ID" "$FULL_DOMAIN"; then
        log "✅ DNS record created: $FULL_DOMAIN"
    else
        error "Failed to create DNS record"
        exit 1
    fi
fi

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

# Wait for tunnel to be ready
log "⏳ Waiting for tunnel to be ready..."
sleep 10

# Test tunnel connectivity
log "🧪 Testing tunnel connectivity..."

if curl -s -f -m 10 "https://$FULL_DOMAIN/health" >/dev/null 2>&1; then
    log "✅ Tunnel is working correctly!"
else
    warn "Tunnel test failed - this might be normal if the service isn't running yet"
fi

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

# Create monitoring script
log "📊 Creating monitoring script..."

sudo tee /usr/local/bin/check-cloudflare-tunnel.sh > /dev/null <<EOF
#!/bin/bash

DOMAIN="$FULL_DOMAIN"
LOG_FILE="/var/log/cloudflare-tunnel-health.log"

# Create log directory if it doesn't exist
mkdir -p /var/log

# Function to log with timestamp
log_with_timestamp() {
    echo "\$(date +'%Y-%m-%d %H:%M:%S') - \$1" >> \$LOG_FILE
}

# Check tunnel status
if systemctl is-active --quiet cloudflared; then
    TUNNEL_STATUS="running"
else
    TUNNEL_STATUS="stopped"
    log_with_timestamp "ERROR: Cloudflare tunnel service is not running"
fi

# Check public URL accessibility
if curl -s -f -m 10 "https://\$DOMAIN/health" > /dev/null; then
    URL_STATUS="accessible"
    log_with_timestamp "SUCCESS: Public URL is accessible"
else
    URL_STATUS="failed"
    log_with_timestamp "ERROR: Public URL is not accessible"
fi

# Output status
echo "Tunnel Status: \$TUNNEL_STATUS"
echo "URL Status: \$URL_STATUS"
echo "Domain: \$DOMAIN"
echo "Last Check: \$(date)"

# Exit with error if either check failed
if [[ "\$TUNNEL_STATUS" != "running" || "\$URL_STATUS" != "accessible" ]]; then
    exit 1
fi
EOF

sudo chmod +x /usr/local/bin/check-cloudflare-tunnel.sh

# Create systemd timer for monitoring
sudo tee /etc/systemd/system/cloudflare-tunnel-health.service > /dev/null <<EOF
[Unit]
Description=Cloudflare Tunnel Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/check-cloudflare-tunnel.sh
EOF

sudo tee /etc/systemd/system/cloudflare-tunnel-health.timer > /dev/null <<EOF
[Unit]
Description=Run Cloudflare Tunnel Health Check every 5 minutes
Requires=cloudflare-tunnel-health.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloudflare-tunnel-health.timer
sudo systemctl start cloudflare-tunnel-health.timer

log "✅ Health monitoring configured"

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
echo "📊 MONITORING:"
echo "   • Health checks run every 5 minutes"
echo "   • Logs: /var/log/cloudflare-tunnel-health.log"
echo "   • Manual check: /usr/local/bin/check-cloudflare-tunnel.sh"
echo ""
echo "🌐 WIX WEBHOOK CONFIGURATION:"
echo "   Configure your Wix webhook URL as:"
echo "   👉 https://$FULL_DOMAIN/webhook/orders"
echo ""
echo "✅ Your printer service is now accessible from anywhere!"
echo "   No router configuration or static IP needed!"
echo ""

log "Cloudflare Tunnel setup completed successfully!"
