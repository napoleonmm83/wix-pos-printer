#!/bin/bash

# 🌐 Public Access Setup Script
# Wix Printer Service - Network and Firewall Configuration
# Version: 1.0
# Date: 2025-09-21

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for safety. Use sudo for individual commands."
   exit 1
fi

# Display header
echo ""
echo "=========================================="
echo "🌐 WIX PRINTER SERVICE - PUBLIC ACCESS SETUP"
echo "=========================================="
echo ""
echo "This script will configure your Raspberry Pi for public internet access"
echo "to enable Wix webhook reception."
echo ""
echo "⚠️  IMPORTANT: This script will:"
echo "   • Configure firewall rules"
echo "   • Set up network configuration"
echo "   • Prepare for SSL certificate installation"
echo "   • Configure security settings"
echo ""
echo "📋 PREREQUISITES:"
echo "   • Router access for port forwarding"
echo "   • Domain name or dynamic DNS service"
echo "   • Internet connection"
echo ""

# Interactive confirmation
read -p "❓ Do you want to proceed with public access setup? (y/N): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Setup cancelled by user"
    exit 0
fi

# Configuration variables
DOMAIN=""
EMAIL=""
SERVICE_PORT=8000
HTTP_PORT=80
HTTPS_PORT=443

# Get domain information
echo "🌐 DOMAIN CONFIGURATION:"
echo "----------------------------------------"
while [[ -z "$DOMAIN" ]]; do
    echo -n "Enter your domain name (e.g., printer.example.com): "
    read DOMAIN
    if [[ -z "$DOMAIN" ]]; then
        warn "Domain name is required"
    fi
done

# Get email for SSL certificate
echo ""
while [[ -z "$EMAIL" ]]; do
    echo -n "Enter your email address for SSL certificate notifications: "
    read EMAIL
    if [[ -z "$EMAIL" ]]; then
        warn "Email address is required for Let's Encrypt"
    fi
done

echo ""
log "Configuration:"
log "  Domain: $DOMAIN"
log "  Email: $EMAIL"
log "  Service Port: $SERVICE_PORT"
log "  HTTP Port: $HTTP_PORT"
log "  HTTPS Port: $HTTPS_PORT"
echo ""

# Phase 1: Update system packages
log "📦 Phase 1: Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Phase 2: Install required packages
log "🔧 Phase 2: Installing required packages..."
sudo apt install -y nginx certbot python3-certbot-nginx ufw fail2ban

# Phase 3: Configure UFW firewall
log "🔥 Phase 3: Configuring UFW firewall..."

# Enable UFW if not already enabled
if ! sudo ufw status | grep -q "Status: active"; then
    log "Enabling UFW firewall..."
    sudo ufw --force enable
fi

# Allow SSH (important to not lock ourselves out)
sudo ufw allow ssh
log "✅ SSH access allowed"

# Allow HTTP and HTTPS
sudo ufw allow $HTTP_PORT
sudo ufw allow $HTTPS_PORT
log "✅ HTTP ($HTTP_PORT) and HTTPS ($HTTPS_PORT) allowed"

# Allow local service port (for internal access)
sudo ufw allow from 192.168.0.0/16 to any port $SERVICE_PORT
sudo ufw allow from 10.0.0.0/8 to any port $SERVICE_PORT
sudo ufw allow from 172.16.0.0/12 to any port $SERVICE_PORT
log "✅ Local network access to service port ($SERVICE_PORT) allowed"

# Deny all other traffic by default
sudo ufw --force default deny incoming
sudo ufw --force default allow outgoing
log "✅ Default firewall rules configured"

# Show firewall status
echo ""
info "Current firewall status:"
sudo ufw status numbered

# Phase 4: Configure fail2ban
log "🛡️  Phase 4: Configuring fail2ban for DDoS protection..."

# Create nginx jail configuration
sudo tee /etc/fail2ban/jail.d/nginx.conf > /dev/null <<EOF
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
findtime = 600
bantime = 7200

[nginx-botsearch]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
EOF

# Restart fail2ban
sudo systemctl restart fail2ban
sudo systemctl enable fail2ban
log "✅ fail2ban configured and started"

# Phase 5: Basic Nginx configuration
log "🔧 Phase 5: Creating basic Nginx configuration..."

# Create Nginx site configuration
sudo tee /etc/nginx/sites-available/wix-printer > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    # Redirect all HTTP traffic to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL configuration (will be updated by certbot)
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=webhook:10m rate=100r/m;
    limit_req_zone \$binary_remote_addr zone=api:10m rate=60r/m;
    
    # Webhook endpoint (higher rate limit)
    location /webhook/ {
        limit_req zone=webhook burst=20 nodelay;
        
        proxy_pass http://127.0.0.1:$SERVICE_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Webhook-specific settings
        proxy_read_timeout 30s;
        proxy_connect_timeout 10s;
    }
    
    # API endpoints (standard rate limit)
    location / {
        limit_req zone=api burst=10 nodelay;
        
        proxy_pass http://127.0.0.1:$SERVICE_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Standard timeouts
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }
    
    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:$SERVICE_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        access_log off;
    }
    
    # Access and error logs
    access_log /var/log/nginx/wix-printer-access.log;
    error_log /var/log/nginx/wix-printer-error.log;
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/wix-printer /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
if sudo nginx -t; then
    log "✅ Nginx configuration is valid"
    sudo systemctl restart nginx
    sudo systemctl enable nginx
else
    error "Nginx configuration test failed"
    exit 1
fi

# Phase 6: SSL Certificate setup
log "🔐 Phase 6: Setting up SSL certificate with Let's Encrypt..."

# Install SSL certificate
if sudo certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --non-interactive --redirect; then
    log "✅ SSL certificate installed successfully"
else
    warn "SSL certificate installation failed. You may need to:"
    warn "  1. Ensure DNS is properly configured"
    warn "  2. Check that ports 80 and 443 are accessible from internet"
    warn "  3. Verify domain ownership"
fi

# Set up automatic renewal
sudo systemctl enable certbot.timer
log "✅ Automatic SSL certificate renewal configured"

# Phase 7: Create monitoring script
log "📊 Phase 7: Creating monitoring and health check scripts..."

# Create public URL health check script
sudo tee /usr/local/bin/check-public-url.sh > /dev/null <<EOF
#!/bin/bash

DOMAIN="$DOMAIN"
SERVICE_URL="https://\$DOMAIN/health"
LOG_FILE="/var/log/wix-printer/public-url-health.log"

# Create log directory if it doesn't exist
mkdir -p /var/log/wix-printer

# Function to log with timestamp
log_with_timestamp() {
    echo "\$(date +'%Y-%m-%d %H:%M:%S') - \$1" >> \$LOG_FILE
}

# Check public URL accessibility
if curl -s -f -m 10 "\$SERVICE_URL" > /dev/null; then
    log_with_timestamp "SUCCESS: Public URL is accessible"
    exit 0
else
    log_with_timestamp "FAILED: Public URL is not accessible"
    exit 1
fi
EOF

sudo chmod +x /usr/local/bin/check-public-url.sh

# Create systemd service for health monitoring
sudo tee /etc/systemd/system/wix-printer-public-health.service > /dev/null <<EOF
[Unit]
Description=Wix Printer Public URL Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/check-public-url.sh
User=wix-printer
Group=wix-printer

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer for regular health checks
sudo tee /etc/systemd/system/wix-printer-public-health.timer > /dev/null <<EOF
[Unit]
Description=Run Wix Printer Public URL Health Check every 5 minutes
Requires=wix-printer-public-health.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start the health check timer
sudo systemctl daemon-reload
sudo systemctl enable wix-printer-public-health.timer
sudo systemctl start wix-printer-public-health.timer

log "✅ Public URL health monitoring configured"

# Phase 8: Final verification
log "🔍 Phase 8: Final verification and testing..."

# Test local service accessibility
if curl -s -f http://localhost:$SERVICE_PORT/health > /dev/null; then
    log "✅ Local service is accessible"
else
    warn "Local service is not responding on port $SERVICE_PORT"
fi

# Test Nginx
if sudo nginx -t; then
    log "✅ Nginx configuration is valid"
else
    error "Nginx configuration has issues"
fi

# Show service status
echo ""
info "Service Status:"
sudo systemctl status nginx --no-pager -l
echo ""
sudo systemctl status fail2ban --no-pager -l

# Phase 9: Summary and next steps
echo ""
echo "🎉 PUBLIC ACCESS SETUP COMPLETED!"
echo "=================================="
echo ""
log "✅ Firewall configured with UFW"
log "✅ Nginx reverse proxy installed and configured"
log "✅ SSL certificate installed (if DNS was ready)"
log "✅ fail2ban configured for DDoS protection"
log "✅ Health monitoring configured"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Configure your router to forward ports 80 and 443 to this Raspberry Pi"
echo "2. Set up DNS A record for '$DOMAIN' pointing to your public IP"
echo "3. Test public access: https://$DOMAIN/health"
echo "4. Configure Wix webhook URL: https://$DOMAIN/webhook/orders"
echo ""
echo "🔧 CONFIGURATION FILES CREATED:"
echo "   • Nginx config: /etc/nginx/sites-available/wix-printer"
echo "   • fail2ban config: /etc/fail2ban/jail.d/nginx.conf"
echo "   • Health check script: /usr/local/bin/check-public-url.sh"
echo ""
echo "📊 MONITORING:"
echo "   • Public URL health checks run every 5 minutes"
echo "   • Logs: /var/log/wix-printer/public-url-health.log"
echo "   • Nginx logs: /var/log/nginx/wix-printer-*.log"
echo ""
echo "⚠️  IMPORTANT SECURITY NOTES:"
echo "   • Only ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) are open"
echo "   • Rate limiting is configured (100 req/min for webhooks)"
echo "   • fail2ban will ban IPs after repeated failed attempts"
echo "   • SSL certificate will auto-renew via certbot"
echo ""

log "Setup script completed successfully!"
echo ""
