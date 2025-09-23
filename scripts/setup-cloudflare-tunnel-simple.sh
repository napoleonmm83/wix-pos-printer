#!/bin/bash

# 🌐 Cloudflare Tunnel Simple Setup Script
# Wix Printer Service - Robust Version with Error Handling
# Version: 1.2

# ... (error handling and other functions remain the same) ...

# Create tunnel configuration
log "⚙️ Creating tunnel configuration..."

TUNNEL_CONFIG_DIR="/etc/cloudflared"
sudo mkdir -p "$TUNNEL_CONFIG_DIR"

# Correctly write the simplified config file pointing to port 5000
sudo tee "$TUNNEL_CONFIG_DIR/config.yml" > /dev/null <<EOF
ingress:
  - hostname: $FULL_DOMAIN
    service: http://localhost:5000
  - service: http_status:404
EOF

log "✅ Tunnel configuration file created correctly."

# ... (copy credentials logic remains the same) ...

# Create systemd service
log "🔧 Creating systemd service..."

# Correctly write the service file with the TUNNEL_ID in ExecStart
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

# ... (rest of the script remains the same) ...