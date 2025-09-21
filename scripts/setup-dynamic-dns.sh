#!/bin/bash

# 🌐 Dynamic DNS Setup Script
# Wix Printer Service - Dynamic IP Solution with DDNS
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

echo ""
echo "=========================================="
echo "🌐 DYNAMIC DNS (DDNS) SETUP"
echo "=========================================="
echo ""
echo "This script will set up Dynamic DNS for your Wix Printer Service."
echo "This allows your domain to automatically update when your IP changes."
echo ""
echo "✅ SUPPORTED PROVIDERS:"
echo "   • Cloudflare (recommended)"
echo "   • No-IP"
echo "   • DuckDNS"
echo "   • Dynu"
echo "   • FreeDNS"
echo ""

# Choose DDNS provider
echo "📋 DDNS PROVIDER SELECTION:"
echo "----------------------------------------"
echo ""
echo "1️⃣ Cloudflare (recommended)"
echo "   • Professional DNS management"
echo "   • Fast propagation"
echo "   • Free SSL certificates"
echo ""
echo "2️⃣ No-IP"
echo "   • Popular DDNS service"
echo "   • Free tier available"
echo "   • Easy setup"
echo ""
echo "3️⃣ DuckDNS"
echo "   • Completely free"
echo "   • Simple setup"
echo "   • Reliable service"
echo ""

while true; do
    read -p "Choose DDNS provider (1-3): " provider_choice
    case $provider_choice in
        1)
            DDNS_PROVIDER="cloudflare"
            break
            ;;
        2)
            DDNS_PROVIDER="noip"
            break
            ;;
        3)
            DDNS_PROVIDER="duckdns"
            break
            ;;
        *)
            echo "❌ Please enter 1, 2, or 3"
            ;;
    esac
done

log "Selected provider: $DDNS_PROVIDER"

# Install ddclient
log "📦 Installing ddclient..."
sudo apt update
sudo apt install -y ddclient curl

# Configure based on provider
case $DDNS_PROVIDER in
    "cloudflare")
        echo ""
        echo "🔐 CLOUDFLARE CONFIGURATION:"
        echo "----------------------------------------"
        echo ""
        echo "📋 REQUIRED INFORMATION:"
        echo "   1. Cloudflare email address"
        echo "   2. Global API Key or API Token"
        echo "   3. Domain name"
        echo "   4. Subdomain (e.g., printer)"
        echo ""
        
        echo -n "Enter your Cloudflare email: "
        read CF_EMAIL
        
        echo -n "Enter your Cloudflare Global API Key: "
        read -s CF_API_KEY
        echo ""
        
        echo -n "Enter your domain (e.g., example.com): "
        read DOMAIN
        
        echo -n "Enter subdomain (default: printer): "
        read SUBDOMAIN
        if [[ -z "$SUBDOMAIN" ]]; then
            SUBDOMAIN="printer"
        fi
        
        FULL_DOMAIN="$SUBDOMAIN.$DOMAIN"
        
        # Create ddclient config
        sudo tee /etc/ddclient.conf > /dev/null <<EOF
# Cloudflare DDNS Configuration
daemon=300
syslog=yes
mail=root
mail-failure=root
pid=/var/run/ddclient.pid
ssl=yes

# Cloudflare
use=web, web=checkip.dyndns.com/, web-skip='IP Address'
protocol=cloudflare
server=www.cloudflare.com
login=$CF_EMAIL
password=$CF_API_KEY
zone=$DOMAIN
$FULL_DOMAIN
EOF
        ;;
        
    "noip")
        echo ""
        echo "🔐 NO-IP CONFIGURATION:"
        echo "----------------------------------------"
        echo ""
        echo "📋 SETUP INSTRUCTIONS:"
        echo "   1. Create account at https://www.noip.com"
        echo "   2. Create hostname (e.g., printer.ddns.net)"
        echo "   3. Get username and password"
        echo ""
        
        echo -n "Enter your No-IP username: "
        read NOIP_USER
        
        echo -n "Enter your No-IP password: "
        read -s NOIP_PASS
        echo ""
        
        echo -n "Enter your hostname (e.g., printer.ddns.net): "
        read FULL_DOMAIN
        
        # Create ddclient config
        sudo tee /etc/ddclient.conf > /dev/null <<EOF
# No-IP DDNS Configuration
daemon=300
syslog=yes
mail=root
mail-failure=root
pid=/var/run/ddclient.pid
ssl=yes

# No-IP
use=web, web=checkip.dyndns.com/, web-skip='IP Address'
protocol=noip
server=dynupdate.no-ip.com
login=$NOIP_USER
password=$NOIP_PASS
$FULL_DOMAIN
EOF
        ;;
        
    "duckdns")
        echo ""
        echo "🔐 DUCKDNS CONFIGURATION:"
        echo "----------------------------------------"
        echo ""
        echo "📋 SETUP INSTRUCTIONS:"
        echo "   1. Go to https://www.duckdns.org"
        echo "   2. Sign in with social account"
        echo "   3. Create subdomain (e.g., myprinter)"
        echo "   4. Get your token"
        echo ""
        
        echo -n "Enter your DuckDNS token: "
        read -s DUCK_TOKEN
        echo ""
        
        echo -n "Enter your subdomain (e.g., myprinter): "
        read DUCK_SUBDOMAIN
        
        FULL_DOMAIN="$DUCK_SUBDOMAIN.duckdns.org"
        
        # Create ddclient config
        sudo tee /etc/ddclient.conf > /dev/null <<EOF
# DuckDNS DDNS Configuration
daemon=300
syslog=yes
mail=root
mail-failure=root
pid=/var/run/ddclient.pid
ssl=yes

# DuckDNS
use=web, web=checkip.dyndns.com/, web-skip='IP Address'
protocol=duckdns
server=www.duckdns.org
login=nouser
password=$DUCK_TOKEN
$FULL_DOMAIN
EOF
        ;;
esac

# Set proper permissions
sudo chmod 600 /etc/ddclient.conf
sudo chown root:root /etc/ddclient.conf

# Start and enable ddclient
log "🔧 Starting ddclient service..."
sudo systemctl restart ddclient
sudo systemctl enable ddclient

# Wait for initial update
log "⏳ Waiting for initial DNS update..."
sleep 30

# Test DNS resolution
log "🧪 Testing DNS resolution..."
if nslookup "$FULL_DOMAIN" >/dev/null 2>&1; then
    RESOLVED_IP=$(nslookup "$FULL_DOMAIN" | grep -A1 "Name:" | tail -1 | awk '{print $2}')
    log "✅ DNS resolution successful: $FULL_DOMAIN → $RESOLVED_IP"
else
    warn "DNS resolution failed - may need more time to propagate"
fi

# Now run the standard public access setup with the dynamic domain
log "🚀 Setting up public access with dynamic domain..."

# Update the setup-public-access.sh to use our dynamic domain
if [[ -f "setup-public-access.sh" ]]; then
    # Run with our domain
    DOMAIN="$FULL_DOMAIN" bash setup-public-access.sh
else
    warn "setup-public-access.sh not found - you'll need to run SSL setup manually"
fi

# Create monitoring script for DDNS
log "📊 Creating DDNS monitoring..."

sudo tee /usr/local/bin/check-ddns-status.sh > /dev/null <<EOF
#!/bin/bash

DOMAIN="$FULL_DOMAIN"
LOG_FILE="/var/log/ddns-health.log"

# Create log directory if it doesn't exist
mkdir -p /var/log

# Function to log with timestamp
log_with_timestamp() {
    echo "\$(date +'%Y-%m-%d %H:%M:%S') - \$1" >> \$LOG_FILE
}

# Get current public IP
CURRENT_IP=\$(curl -s checkip.dyndns.com | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}')

# Get DNS resolved IP
RESOLVED_IP=\$(nslookup "\$DOMAIN" | grep -A1 "Name:" | tail -1 | awk '{print \$2}' 2>/dev/null || echo "")

# Check ddclient service
if systemctl is-active --quiet ddclient; then
    SERVICE_STATUS="running"
else
    SERVICE_STATUS="stopped"
    log_with_timestamp "ERROR: ddclient service is not running"
fi

# Check IP match
if [[ "\$CURRENT_IP" == "\$RESOLVED_IP" ]]; then
    IP_STATUS="synced"
    log_with_timestamp "SUCCESS: DNS is synced - \$DOMAIN → \$CURRENT_IP"
else
    IP_STATUS="out_of_sync"
    log_with_timestamp "WARNING: DNS out of sync - Current: \$CURRENT_IP, DNS: \$RESOLVED_IP"
fi

# Output status
echo "DDNS Service: \$SERVICE_STATUS"
echo "IP Sync Status: \$IP_STATUS"
echo "Current IP: \$CURRENT_IP"
echo "DNS IP: \$RESOLVED_IP"
echo "Domain: \$DOMAIN"
echo "Last Check: \$(date)"

# Exit with error if service is down
if [[ "\$SERVICE_STATUS" != "running" ]]; then
    exit 1
fi
EOF

sudo chmod +x /usr/local/bin/check-ddns-status.sh

# Create systemd timer for DDNS monitoring
sudo tee /etc/systemd/system/ddns-health.service > /dev/null <<EOF
[Unit]
Description=DDNS Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/check-ddns-status.sh
EOF

sudo tee /etc/systemd/system/ddns-health.timer > /dev/null <<EOF
[Unit]
Description=Run DDNS Health Check every 10 minutes
Requires=ddns-health.service

[Timer]
OnCalendar=*:0/10
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ddns-health.timer
sudo systemctl start ddns-health.timer

# Update environment configuration
ENV_FILE="/opt/wix-printer-service/.env"
if [[ -f "$ENV_FILE" ]]; then
    if grep -q "PUBLIC_DOMAIN=" "$ENV_FILE"; then
        sudo sed -i "s/PUBLIC_DOMAIN=.*/PUBLIC_DOMAIN=$FULL_DOMAIN/" "$ENV_FILE"
    else
        echo "PUBLIC_DOMAIN=$FULL_DOMAIN" | sudo tee -a "$ENV_FILE" >/dev/null
    fi
    log "✅ Environment configuration updated"
fi

echo ""
echo "🎉 DYNAMIC DNS SETUP COMPLETE!"
echo "=============================="
echo ""
echo "✅ CONFIGURATION SUMMARY:"
echo "   • Provider: $DDNS_PROVIDER"
echo "   • Domain: $FULL_DOMAIN"
echo "   • Webhook URL: https://$FULL_DOMAIN/webhook/orders"
echo ""
echo "🔧 MANAGEMENT COMMANDS:"
echo "   • Check DDNS status: sudo systemctl status ddclient"
echo "   • View DDNS logs: sudo journalctl -u ddclient -f"
echo "   • Force update: sudo ddclient -force"
echo "   • Test DNS: nslookup $FULL_DOMAIN"
echo ""
echo "📊 MONITORING:"
echo "   • DDNS health checks run every 10 minutes"
echo "   • Logs: /var/log/ddns-health.log"
echo "   • Manual check: /usr/local/bin/check-ddns-status.sh"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "   1. Configure router port forwarding (80, 443)"
echo "   2. Wait for DNS propagation (5-30 minutes)"
echo "   3. Test public access: curl https://$FULL_DOMAIN/health"
echo ""

log "Dynamic DNS setup completed successfully!"
