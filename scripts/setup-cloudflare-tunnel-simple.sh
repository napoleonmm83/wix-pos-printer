#!/bin/bash

# 🌐 Cloudflare Tunnel Simple Setup Script
# Wix Printer Service - Robust Version with Error Handling
# Version: 1.3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

command -v cloudflared >/dev/null 2>&1 || {
    error "cloudflared is not installed. Please run the full Cloudflare setup first."
    exit 1
}

log "🔍 Preparing Cloudflare tunnel configuration..."

# Prompt for tunnel information if not provided by the caller
if [[ -z "${TUNNEL_ID:-}" ]]; then
    log "📋 Available tunnels (if any):"
    if cloudflared tunnel list >/tmp/cloudflared-tunnel-list 2>&1; then
        cat /tmp/cloudflared-tunnel-list
    else
        warn "Could not list tunnels automatically. You can find the Tunnel ID with 'cloudflared tunnel list'."
    fi
    while [[ -z "${TUNNEL_ID:-}" ]]; do
        read -rp "Enter the existing Cloudflare Tunnel ID: " TUNNEL_ID
        [[ -z "$TUNNEL_ID" ]] && warn "Tunnel ID is required."
    done
fi

# Derive full domain from environment if possible
if [[ -z "${FULL_DOMAIN:-}" ]]; then
    ENV_FILE="/opt/wix-printer-service/.env"
    if [[ -f "$ENV_FILE" ]]; then
        EXISTING_DOMAIN=$(grep -E "^PUBLIC_DOMAIN=" "$ENV_FILE" | tail -1 | cut -d'=' -f2-)
        if [[ -n "$EXISTING_DOMAIN" ]]; then
            read -rp "Enter public domain for the tunnel [${EXISTING_DOMAIN}]: " FULL_DOMAIN_INPUT
            FULL_DOMAIN=${FULL_DOMAIN_INPUT:-$EXISTING_DOMAIN}
        fi
    fi
fi

while [[ -z "${FULL_DOMAIN:-}" ]]; do
    read -rp "Enter public domain for the tunnel (e.g. printer.example.com): " FULL_DOMAIN
    [[ -z "$FULL_DOMAIN" ]] && warn "Public domain is required."
done

# Determine credentials source
DEFAULT_CREDS="$HOME/.cloudflared/${TUNNEL_ID}.json"
if [[ -z "${TUNNEL_CREDENTIALS:-}" && -f "$DEFAULT_CREDS" ]]; then
    TUNNEL_CREDENTIALS="$DEFAULT_CREDS"
fi

while [[ -z "${TUNNEL_CREDENTIALS:-}" || ! -f "$TUNNEL_CREDENTIALS" ]]; do
    if [[ -n "${TUNNEL_CREDENTIALS:-}" && ! -f "$TUNNEL_CREDENTIALS" ]]; then
        warn "Credentials file '$TUNNEL_CREDENTIALS' not found."
    fi
    read -rp "Enter path to tunnel credentials JSON (${DEFAULT_CREDS}): " TUNNEL_CREDENTIALS_INPUT
    TUNNEL_CREDENTIALS=${TUNNEL_CREDENTIALS_INPUT:-$DEFAULT_CREDS}
done

log "⚙️ Creating tunnel configuration..."

TUNNEL_CONFIG_DIR="/etc/cloudflared"
sudo mkdir -p "$TUNNEL_CONFIG_DIR"

sudo tee "$TUNNEL_CONFIG_DIR/config.yml" > /dev/null <<EOF
tunnel: $TUNNEL_ID
credentials-file: /etc/cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $FULL_DOMAIN
    service: http://localhost:5000
  - service: http_status:404
EOF

log "✅ Tunnel configuration file created correctly."

log "🪪 Copying tunnel credentials..."
sudo cp "$TUNNEL_CREDENTIALS" "$TUNNEL_CONFIG_DIR/$TUNNEL_ID.json"
sudo chmod 600 "$TUNNEL_CONFIG_DIR/$TUNNEL_ID.json"
log "✅ Credentials copied to /etc/cloudflared."

log "🔧 Creating systemd service..."

sudo tee /etc/systemd/system/cloudflared.service > /dev/null <<EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run $TUNNEL_ID
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

log "✅ Systemd service file created correctly."

log "🔁 Reloading and starting cloudflared service..."
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared

if sudo systemctl is-active --quiet cloudflared; then
    log "✅ Cloudflare tunnel service is running."
else
    error "Cloudflare tunnel service failed to start. Check 'sudo journalctl -u cloudflared -b' for details."
    exit 1
fi

# Update environment configuration for convenience
ENV_FILE="/opt/wix-printer-service/.env"
if [[ -f "$ENV_FILE" ]]; then
    if grep -q "^PUBLIC_DOMAIN=" "$ENV_FILE"; then
        sudo sed -i "s/^PUBLIC_DOMAIN=.*/PUBLIC_DOMAIN=$FULL_DOMAIN/" "$ENV_FILE"
    else
        echo "PUBLIC_DOMAIN=$FULL_DOMAIN" | sudo tee -a "$ENV_FILE" >/dev/null
    fi
    log "✅ Updated PUBLIC_DOMAIN in $ENV_FILE"
fi

log "🎉 Cloudflare tunnel setup completed!"
log "   Tunnel ID: $TUNNEL_ID"
log "   Public URL: https://$FULL_DOMAIN"
log "You can review the service status with: sudo systemctl status cloudflared"