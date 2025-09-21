#!/bin/bash

# 🌐 Public URL Setup Menu
# Wix Printer Service - Simple Menu for Public URL Setup
# Version: 1.0
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

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

echo ""
echo "🌐 PUBLIC URL SETUP MENU"
echo "========================"
echo ""
echo "Choose the best method for your network setup:"
echo ""
echo "1️⃣ CLOUDFLARE TUNNEL (RECOMMENDED) ⭐"
echo "   ✅ No static IP required"
echo "   ✅ No router configuration needed"
echo "   ✅ Automatic SSL certificates"
echo "   ✅ Built-in DDoS protection"
echo "   ✅ Works behind any firewall/NAT"
echo ""
echo "2️⃣ DYNAMIC DNS + PORT FORWARDING"
echo "   ✅ Works with dynamic IP addresses"
echo "   ⚠️  Requires router port forwarding"
echo "   ✅ Multiple DDNS providers supported"
echo "   ✅ Traditional setup method"
echo ""
echo "3️⃣ STATIC IP SETUP"
echo "   ⚠️  Requires static IP address"
echo "   ⚠️  Requires router port forwarding"
echo "   ✅ Most direct method"
echo "   ✅ Full control over configuration"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make all scripts executable
chmod +x "$SCRIPT_DIR"/*.sh

while true; do
    read -p "👉 Choose setup method (1-3): " method_choice
    case $method_choice in
        1)
            log "🚀 Starting Cloudflare Tunnel Setup..."
            echo ""
            if [ -f "$SCRIPT_DIR/setup-cloudflare-tunnel-simple.sh" ]; then
                exec "$SCRIPT_DIR/setup-cloudflare-tunnel-simple.sh"
            else
                error "Cloudflare tunnel script not found!"
                exit 1
            fi
            ;;
        2)
            log "🚀 Starting Dynamic DNS Setup..."
            echo ""
            if [ -f "$SCRIPT_DIR/setup-dynamic-dns.sh" ]; then
                exec "$SCRIPT_DIR/setup-dynamic-dns.sh"
            else
                error "Dynamic DNS script not found!"
                exit 1
            fi
            ;;
        3)
            log "🚀 Starting Static IP Setup..."
            echo ""
            if [ -f "$SCRIPT_DIR/setup-public-access.sh" ]; then
                exec "$SCRIPT_DIR/setup-public-access.sh"
            else
                error "Static IP setup script not found!"
                exit 1
            fi
            ;;
        *)
            echo "❌ Please enter 1, 2, or 3"
            ;;
    esac
done
