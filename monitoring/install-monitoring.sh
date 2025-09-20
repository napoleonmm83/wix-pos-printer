#!/bin/bash
# Recovery Monitoring Installation Script

echo "Installing Recovery Monitoring Services..."

# Copy service files
sudo cp E:\Git\wix-pos-order\monitoring\systemd/*.service /etc/systemd/system/
sudo cp E:\Git\wix-pos-order\monitoring\systemd/*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable recovery-health-check.timer
sudo systemctl start recovery-health-check.timer

sudo systemctl enable recovery-performance-monitor.service
sudo systemctl start recovery-performance-monitor.service

echo "✓ Recovery monitoring services installed and started"
echo "✓ Health checks will run every 5 minutes"
echo "✓ Performance monitoring is running continuously"

# Show status
echo ""
echo "Service Status:"
sudo systemctl status recovery-health-check.timer --no-pager -l
sudo systemctl status recovery-performance-monitor.service --no-pager -l
