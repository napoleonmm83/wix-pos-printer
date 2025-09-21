#!/bin/bash

# 🌐 Domain Configuration Script
# Wix Printer Service - Domain and DNS Setup Helper
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
echo "🌐 DOMAIN CONFIGURATION HELPER"
echo "=========================================="
echo ""

# Get current public IP
log "🔍 Detecting current public IP address..."
PUBLIC_IP=$(curl -s -4 ifconfig.me || curl -s -4 icanhazip.com || echo "Unable to detect")

if [[ "$PUBLIC_IP" == "Unable to detect" ]]; then
    warn "Could not automatically detect public IP address"
    echo -n "Please enter your public IP address manually: "
    read PUBLIC_IP
fi

log "Current public IP: $PUBLIC_IP"

# Check if domain is provided as argument
DOMAIN="$1"
if [[ -z "$DOMAIN" ]]; then
    echo -n "Enter your domain name (e.g., printer.example.com): "
    read DOMAIN
fi

if [[ -z "$DOMAIN" ]]; then
    error "Domain name is required"
    exit 1
fi

echo ""
log "Domain: $DOMAIN"
log "Public IP: $PUBLIC_IP"
echo ""

# DNS Configuration Instructions
echo "📋 DNS CONFIGURATION INSTRUCTIONS:"
echo "=================================="
echo ""
echo "To configure DNS for your domain '$DOMAIN', you need to:"
echo ""
echo "1. 🌐 Log in to your DNS provider (e.g., Cloudflare, GoDaddy, etc.)"
echo "2. 📝 Create an A record with the following settings:"
echo "   • Name/Host: $(echo $DOMAIN | cut -d'.' -f1)"
echo "   • Type: A"
echo "   • Value/Points to: $PUBLIC_IP"
echo "   • TTL: 300 (5 minutes) or Auto"
echo ""
echo "3. 💾 Save the DNS record"
echo "4. ⏱️  Wait for DNS propagation (usually 5-30 minutes)"
echo ""

# DNS Testing
echo "🔍 DNS TESTING:"
echo "==============="
echo ""

# Test current DNS resolution
log "Testing current DNS resolution for $DOMAIN..."
RESOLVED_IP=$(dig +short $DOMAIN 2>/dev/null || echo "")

if [[ -n "$RESOLVED_IP" ]]; then
    if [[ "$RESOLVED_IP" == "$PUBLIC_IP" ]]; then
        log "✅ DNS is correctly configured!"
        log "   $DOMAIN resolves to $RESOLVED_IP (matches public IP)"
    else
        warn "DNS mismatch detected:"
        warn "   $DOMAIN resolves to: $RESOLVED_IP"
        warn "   Expected (public IP): $PUBLIC_IP"
        warn "   Please update your DNS A record"
    fi
else
    warn "DNS not configured yet:"
    warn "   $DOMAIN does not resolve to any IP"
    warn "   Please create the DNS A record as instructed above"
fi

# Router Configuration Instructions
echo ""
echo "🔧 ROUTER CONFIGURATION INSTRUCTIONS:"
echo "====================================="
echo ""
echo "To enable external access, configure port forwarding on your router:"
echo ""
echo "1. 🌐 Access your router's admin interface (usually http://192.168.1.1)"
echo "2. 🔍 Find 'Port Forwarding' or 'Virtual Server' settings"
echo "3. ➕ Add the following port forwarding rules:"
echo ""
echo "   Rule 1 - HTTP:"
echo "   • External Port: 80"
echo "   • Internal Port: 80"
echo "   • Internal IP: $(hostname -I | awk '{print $1}')"
echo "   • Protocol: TCP"
echo ""
echo "   Rule 2 - HTTPS:"
echo "   • External Port: 443"
echo "   • Internal Port: 443"
echo "   • Internal IP: $(hostname -I | awk '{print $1}')"
echo "   • Protocol: TCP"
echo ""
echo "4. 💾 Save and apply the settings"
echo "5. 🔄 Restart your router if required"
echo ""

# Testing Tools
echo "🧪 TESTING TOOLS:"
echo "================"
echo ""
echo "Use these commands to test your configuration:"
echo ""
echo "1. Test DNS resolution:"
echo "   nslookup $DOMAIN"
echo "   dig $DOMAIN"
echo ""
echo "2. Test external HTTP access (after setup):"
echo "   curl -I http://$DOMAIN"
echo ""
echo "3. Test external HTTPS access (after SSL setup):"
echo "   curl -I https://$DOMAIN/health"
echo ""
echo "4. Test from external network:"
echo "   Use online tools like https://www.whatsmydns.net/"
echo "   Search for: $DOMAIN"
echo ""

# Automated testing function
test_connectivity() {
    echo ""
    log "🔍 Running connectivity tests..."
    
    # Test local service
    if curl -s -f http://localhost:8000/health > /dev/null; then
        log "✅ Local service is running"
    else
        error "❌ Local service is not responding"
        return 1
    fi
    
    # Test DNS resolution
    if RESOLVED_IP=$(dig +short $DOMAIN 2>/dev/null) && [[ -n "$RESOLVED_IP" ]]; then
        if [[ "$RESOLVED_IP" == "$PUBLIC_IP" ]]; then
            log "✅ DNS resolution is correct"
        else
            warn "⚠️  DNS resolves to $RESOLVED_IP, expected $PUBLIC_IP"
        fi
    else
        warn "⚠️  DNS not configured or not propagated yet"
    fi
    
    # Test external access (if DNS is configured)
    if [[ -n "$RESOLVED_IP" && "$RESOLVED_IP" == "$PUBLIC_IP" ]]; then
        log "Testing external HTTP access..."
        if timeout 10 curl -s -f http://$DOMAIN/health > /dev/null 2>&1; then
            log "✅ External HTTP access working"
        else
            warn "⚠️  External HTTP access failed (check port forwarding)"
        fi
        
        log "Testing external HTTPS access..."
        if timeout 10 curl -s -f https://$DOMAIN/health > /dev/null 2>&1; then
            log "✅ External HTTPS access working"
        else
            warn "⚠️  External HTTPS access failed (SSL may not be configured yet)"
        fi
    fi
}

# Offer to run tests
echo ""
read -p "❓ Would you like to run connectivity tests now? (y/N): " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    test_connectivity
fi

# Configuration summary
echo ""
echo "📋 CONFIGURATION SUMMARY:"
echo "========================"
echo ""
echo "Domain: $DOMAIN"
echo "Public IP: $PUBLIC_IP"
echo "Local IP: $(hostname -I | awk '{print $1}')"
echo "Service Port: 8000"
echo ""
echo "Required DNS Record:"
echo "  Type: A"
echo "  Name: $(echo $DOMAIN | cut -d'.' -f1)"
echo "  Value: $PUBLIC_IP"
echo ""
echo "Required Port Forwarding:"
echo "  Port 80 → $(hostname -I | awk '{print $1}'):80"
echo "  Port 443 → $(hostname -I | awk '{print $1}'):443"
echo ""

# Save configuration for later use
CONFIG_FILE="/opt/wix-printer-service/public-url.conf"
if [[ -d "/opt/wix-printer-service" ]]; then
    log "💾 Saving configuration to $CONFIG_FILE"
    sudo tee $CONFIG_FILE > /dev/null <<EOF
# Wix Printer Service Public URL Configuration
# Generated on $(date)

DOMAIN=$DOMAIN
PUBLIC_IP=$PUBLIC_IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
SERVICE_PORT=8000
HTTP_PORT=80
HTTPS_PORT=443
EOF
    log "✅ Configuration saved"
else
    warn "Service directory not found, configuration not saved"
fi

echo ""
log "Domain configuration helper completed!"
echo ""
echo "🎯 NEXT STEPS:"
echo "1. Configure DNS A record as shown above"
echo "2. Set up router port forwarding"
echo "3. Run the main setup script: ./setup-public-access.sh"
echo "4. Test connectivity with: curl https://$DOMAIN/health"
echo ""
