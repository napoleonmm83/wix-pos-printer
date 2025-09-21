# Public URL Setup Guide

## Overview

This guide provides comprehensive instructions for setting up public internet access for your Wix Printer Service, enabling real-time webhook reception from Wix for automated order processing.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup Process](#detailed-setup-process)
4. [Configuration Options](#configuration-options)
5. [Security Considerations](#security-considerations)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)

## Prerequisites

### Required Access
- **Router Admin Access**: Ability to configure port forwarding
- **Domain Name**: Registered domain or subdomain
- **SSL Certificate**: Let's Encrypt (automated) or commercial certificate
- **Internet Connection**: Stable broadband connection

### Technical Requirements
- **Raspberry Pi**: Running Wix Printer Service
- **Static Local IP**: Recommended for consistent port forwarding
- **Firewall Access**: Ability to configure UFW or iptables
- **SSH Access**: For remote configuration

### Network Information Needed
- **Public IP Address**: Your router's external IP
- **Local IP Address**: Raspberry Pi's internal IP
- **Domain Name**: The domain you'll use (e.g., printer.yourdomain.com)
- **Email Address**: For SSL certificate notifications

## Quick Start

### 1. Run the Automated Setup Script

```bash
# Navigate to the project directory
cd /path/to/wix-pos-order

# Make scripts executable
chmod +x scripts/setup-public-access.sh
chmod +x scripts/configure-domain.sh

# Run domain configuration helper
./scripts/configure-domain.sh your-domain.com

# Run the main setup script
./scripts/setup-public-access.sh
```

### 2. Configure Your Router

1. **Access Router Admin Panel**
   - Usually at `http://192.168.1.1` or `http://192.168.0.1`
   - Login with admin credentials

2. **Set Up Port Forwarding**
   - Forward port 80 (HTTP) to your Raspberry Pi
   - Forward port 443 (HTTPS) to your Raspberry Pi
   - Use your Pi's local IP address

3. **Save and Apply Settings**

### 3. Configure DNS

1. **Log in to Your DNS Provider**
   - Cloudflare, GoDaddy, Namecheap, etc.

2. **Create A Record**
   - Name: `printer` (or your chosen subdomain)
   - Type: `A`
   - Value: Your public IP address
   - TTL: `300` (5 minutes)

3. **Wait for DNS Propagation**
   - Usually takes 5-30 minutes

### 4. Test Your Setup

```bash
# Test external access
curl https://your-domain.com/health

# Check webhook endpoint
curl -X POST https://your-domain.com/webhook/orders \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Monitor public URL status
curl https://your-domain.com/public-url/status
```

## Detailed Setup Process

### Step 1: Network Configuration

#### 1.1 Configure Static IP (Recommended)

```bash
# Edit network configuration
sudo nano /etc/dhcpcd.conf

# Add these lines (adjust for your network)
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

#### 1.2 Configure Firewall

```bash
# Enable UFW
sudo ufw enable

# Allow SSH (important!)
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80
sudo ufw allow 443

# Allow local network access to service port
sudo ufw allow from 192.168.0.0/16 to any port 8000

# Check status
sudo ufw status
```

### Step 2: SSL Certificate Setup

#### 2.1 Install Certbot

```bash
# Update packages
sudo apt update

# Install certbot and nginx plugin
sudo apt install certbot python3-certbot-nginx
```

#### 2.2 Generate Certificate

```bash
# Generate certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Step 3: Reverse Proxy Configuration

#### 3.1 Install and Configure Nginx

```bash
# Install Nginx
sudo apt install nginx

# Create site configuration
sudo nano /etc/nginx/sites-available/wix-printer
```

#### 3.2 Nginx Configuration Template

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL configuration (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=webhook:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    
    # Webhook endpoint
    location /webhook/ {
        limit_req zone=webhook burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API endpoints
    location / {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }
}
```

#### 3.3 Enable Site

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/wix-printer /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Step 4: Security Hardening

#### 4.1 Configure fail2ban

```bash
# Install fail2ban
sudo apt install fail2ban

# Create nginx jail
sudo nano /etc/fail2ban/jail.d/nginx.conf
```

```ini
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
```

```bash
# Restart fail2ban
sudo systemctl restart fail2ban
sudo systemctl enable fail2ban
```

#### 4.2 Configure Log Rotation

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/wix-printer
```

```
/var/log/nginx/wix-printer-*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload nginx
    endscript
}
```

### Step 5: Environment Configuration

#### 5.1 Update Environment Variables

```bash
# Edit environment file
nano .env

# Add public URL configuration
PUBLIC_DOMAIN=your-domain.com
PUBLIC_URL_TIMEOUT=10
PUBLIC_URL_CHECK_INTERVAL=300
```

#### 5.2 Restart Service

```bash
# Restart the Wix Printer Service
sudo systemctl restart wix-printer.service

# Check status
sudo systemctl status wix-printer.service
```

## Configuration Options

### DNS Configuration Options

#### Option 1: Subdomain (Recommended)
```
Type: A
Name: printer
Value: YOUR_PUBLIC_IP
Result: printer.yourdomain.com
```

#### Option 2: Root Domain
```
Type: A
Name: @
Value: YOUR_PUBLIC_IP
Result: yourdomain.com
```

#### Option 3: CNAME (if using CDN)
```
Type: CNAME
Name: printer
Value: your-cdn-endpoint.com
```

### Public Access Options

#### Option 1: Router Port Forwarding
- **Pros**: Direct access, full control
- **Cons**: Requires router configuration, security responsibility
- **Best for**: Technical users with router access

#### Option 2: Cloudflare Tunnel
- **Pros**: No port forwarding, DDoS protection, easy setup
- **Cons**: Dependency on Cloudflare, potential latency
- **Best for**: Users without router access

```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb

# Create tunnel
cloudflared tunnel --url http://localhost:8000
```

#### Option 3: ngrok (Development Only)
- **Pros**: Very easy setup, good for testing
- **Cons**: Not suitable for production, URL changes
- **Best for**: Development and testing

```bash
# Install ngrok
sudo snap install ngrok

# Create tunnel
ngrok http 8000
```

### SSL Certificate Options

#### Option 1: Let's Encrypt (Recommended)
- **Pros**: Free, automatic renewal, widely trusted
- **Cons**: Rate limits, requires domain validation
- **Setup**: Automated via certbot

#### Option 2: Commercial Certificate
- **Pros**: Higher trust, extended validation options
- **Cons**: Cost, manual renewal process
- **Setup**: Manual installation

#### Option 3: Self-Signed (Development Only)
- **Pros**: No external dependencies
- **Cons**: Browser warnings, not trusted
- **Setup**: OpenSSL generation

## Security Considerations

### Network Security

#### Firewall Configuration
```bash
# Minimal firewall rules
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw deny incoming
sudo ufw allow outgoing
```

#### Port Security
- **Only expose necessary ports** (80, 443)
- **Use non-standard SSH port** if possible
- **Implement rate limiting** at multiple levels
- **Monitor access logs** regularly

### SSL Security

#### Certificate Management
- **Use strong encryption** (TLS 1.2+)
- **Enable HSTS** for browser security
- **Monitor certificate expiry** (automated alerts)
- **Use proper cipher suites**

#### Security Headers
```nginx
# Essential security headers
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Referrer-Policy "strict-origin-when-cross-origin";
```

### Application Security

#### Webhook Security
- **Validate webhook signatures** (HMAC-SHA256)
- **Implement rate limiting** (100 req/min)
- **Log all webhook attempts**
- **Use CORS restrictions**

#### Access Control
- **Restrict admin endpoints** to local network
- **Implement IP whitelisting** for sensitive operations
- **Use strong authentication** for configuration changes

## Monitoring and Maintenance

### Health Monitoring

#### Built-in Monitoring
```bash
# Check public URL status
curl https://your-domain.com/public-url/status

# Get detailed statistics
curl https://your-domain.com/public-url/statistics

# Force health check
curl -X POST https://your-domain.com/public-url/check
```

#### System Monitoring
```bash
# Check service status
sudo systemctl status wix-printer.service

# Monitor logs
sudo journalctl -u wix-printer.service -f

# Check Nginx status
sudo systemctl status nginx

# Monitor Nginx logs
sudo tail -f /var/log/nginx/wix-printer-access.log
```

### Automated Monitoring

#### SSL Certificate Monitoring
```bash
# Check certificate expiry
openssl x509 -in /etc/letsencrypt/live/your-domain.com/cert.pem -text -noout | grep "Not After"

# Automated check script
#!/bin/bash
DOMAIN="your-domain.com"
EXPIRY_DATE=$(echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates | grep notAfter | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
CURRENT_EPOCH=$(date +%s)
DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))

if [ $DAYS_UNTIL_EXPIRY -lt 30 ]; then
    echo "WARNING: SSL certificate expires in $DAYS_UNTIL_EXPIRY days"
fi
```

#### DNS Monitoring
```bash
# Check DNS resolution
nslookup your-domain.com

# Check from multiple DNS servers
dig @8.8.8.8 your-domain.com
dig @1.1.1.1 your-domain.com
dig @208.67.222.222 your-domain.com
```

### Maintenance Tasks

#### Weekly Tasks
- [ ] Check SSL certificate status
- [ ] Review access logs for anomalies
- [ ] Verify webhook success rates
- [ ] Test external accessibility

#### Monthly Tasks
- [ ] Update system packages
- [ ] Review firewall logs
- [ ] Check disk space usage
- [ ] Verify backup procedures

#### Quarterly Tasks
- [ ] Review security configuration
- [ ] Update SSL certificate if needed
- [ ] Audit access permissions
- [ ] Test disaster recovery

## Troubleshooting

### Common Issues

#### 1. DNS Not Resolving

**Symptoms**:
- Domain doesn't resolve to your IP
- `nslookup` returns no results

**Solutions**:
```bash
# Check DNS configuration
nslookup your-domain.com

# Test with different DNS servers
nslookup your-domain.com 8.8.8.8

# Check DNS propagation
dig your-domain.com +trace
```

#### 2. Port Forwarding Not Working

**Symptoms**:
- External access fails
- Connection timeouts

**Solutions**:
```bash
# Check if ports are listening locally
netstat -tlnp | grep :80
netstat -tlnp | grep :443

# Test port forwarding
telnet your-public-ip 80
telnet your-public-ip 443

# Check router configuration
# - Verify port forwarding rules
# - Check firewall settings
# - Confirm target IP address
```

#### 3. SSL Certificate Issues

**Symptoms**:
- Browser SSL warnings
- Certificate validation errors

**Solutions**:
```bash
# Check certificate status
openssl x509 -in /etc/letsencrypt/live/your-domain.com/cert.pem -text -noout

# Test SSL connection
openssl s_client -connect your-domain.com:443

# Renew certificate
sudo certbot renew

# Check certificate chain
curl -I https://your-domain.com
```

#### 4. Webhook Not Receiving

**Symptoms**:
- Wix webhooks not arriving
- Webhook endpoint returns errors

**Solutions**:
```bash
# Check webhook endpoint
curl -X POST https://your-domain.com/webhook/orders \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Check webhook logs
sudo journalctl -u wix-printer.service | grep webhook

# Verify webhook configuration in Wix
# - Check webhook URL
# - Verify webhook secret
# - Confirm event types
```

#### 5. Rate Limiting Issues

**Symptoms**:
- 429 Too Many Requests errors
- Legitimate requests blocked

**Solutions**:
```bash
# Check rate limiting configuration
sudo nginx -T | grep limit_req

# Monitor rate limiting
sudo tail -f /var/log/nginx/error.log | grep limit_req

# Adjust rate limits if needed
sudo nano /etc/nginx/sites-available/wix-printer
```

### Diagnostic Commands

#### Network Diagnostics
```bash
# Check public IP
curl ifconfig.me

# Test DNS resolution
nslookup your-domain.com
dig your-domain.com

# Test port connectivity
telnet your-domain.com 80
telnet your-domain.com 443

# Check routing
traceroute your-domain.com
```

#### Service Diagnostics
```bash
# Check service status
sudo systemctl status wix-printer.service
sudo systemctl status nginx
sudo systemctl status fail2ban

# Check service logs
sudo journalctl -u wix-printer.service -n 50
sudo journalctl -u nginx -n 50

# Check configuration
sudo nginx -t
python -m wix_printer_service.config_validator
```

#### SSL Diagnostics
```bash
# Test SSL configuration
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Check certificate chain
curl -I https://your-domain.com

# Verify certificate details
openssl x509 -in /etc/letsencrypt/live/your-domain.com/cert.pem -text -noout
```

## Advanced Configuration

### Custom Domain Configuration

#### Multiple Domains
```nginx
server {
    listen 443 ssl http2;
    server_name printer.domain1.com printer.domain2.com;
    
    # SSL certificates for multiple domains
    ssl_certificate /etc/letsencrypt/live/printer.domain1.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/printer.domain1.com/privkey.pem;
    
    # Rest of configuration...
}
```

#### Wildcard Certificates
```bash
# Generate wildcard certificate
sudo certbot --nginx -d "*.yourdomain.com" -d "yourdomain.com"
```

### Load Balancing

#### Multiple Service Instances
```nginx
upstream wix_printer_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001 backup;
}

server {
    # ... SSL configuration ...
    
    location / {
        proxy_pass http://wix_printer_backend;
        # ... proxy headers ...
    }
}
```

### CDN Integration

#### Cloudflare Configuration
1. **Add site to Cloudflare**
2. **Update nameservers**
3. **Configure SSL/TLS settings**
4. **Set up page rules**

#### CDN-Specific Headers
```nginx
# Real IP detection with CDN
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
real_ip_header CF-Connecting-IP;
```

### Monitoring Integration

#### Prometheus Metrics
```python
# Add to your service
from prometheus_client import Counter, Histogram, generate_latest

webhook_requests = Counter('webhook_requests_total', 'Total webhook requests')
webhook_response_time = Histogram('webhook_response_seconds', 'Webhook response time')

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

#### Grafana Dashboard
- **Import webhook metrics**
- **Create SSL expiry alerts**
- **Monitor response times**
- **Track error rates**

## Support and Resources

### Documentation Links
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Wix Webhooks Documentation](https://dev.wix.com/api/rest/webhooks)

### Community Resources
- [Wix Printer Service GitHub](https://github.com/your-repo/wix-pos-order)
- [Community Forum](https://community.example.com)
- [Discord Server](https://discord.gg/example)

### Professional Support
For professional setup and support services, contact:
- **Email**: support@example.com
- **Phone**: +1-555-0123
- **Website**: https://support.example.com

---

**Last Updated**: 2025-09-21  
**Version**: 1.0  
**Author**: Wix Printer Service Team
