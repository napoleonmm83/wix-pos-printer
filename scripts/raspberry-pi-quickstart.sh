#!/bin/bash

# 🍓 Raspberry Pi Quick Start Script
# Wix Printer Service - Epic 2 Complete with Self-Healing
# Version: 1.0
# Date: 2025-09-20

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
   exit 1
fi

log "🍓 Starting Raspberry Pi Setup for Wix Printer Service"
log "Epic 2 Complete - Self-Healing System Ready!"

# Phase 1: System Update
log "📦 Phase 1: Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip python3-venv sqlite3 curl cups cups-client

# Verify Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
log "Python version: $PYTHON_VERSION"

# Phase 2: Create service user and directories
log "👤 Phase 2: Setting up service user..."
if ! id "wix-printer" &>/dev/null; then
    sudo useradd -r -s /bin/bash -d /opt/wix-printer-service wix-printer
    log "Created wix-printer user"
else
    log "wix-printer user already exists"
fi

sudo mkdir -p /opt/wix-printer-service
sudo chown wix-printer:wix-printer /opt/wix-printer-service

# Add user to printer group
sudo usermod -a -G lp wix-printer

# Phase 3: Setup Python environment
log "🐍 Phase 3: Setting up Python environment..."

# First, copy the source code to the service directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

log "Copying source code from $PROJECT_DIR to /opt/wix-printer-service..."
sudo cp -r "$PROJECT_DIR"/* /opt/wix-printer-service/
sudo chown -R wix-printer:wix-printer /opt/wix-printer-service

cd /opt/wix-printer-service

# Check if we're in the right directory with source code
if [ ! -f "requirements.txt" ]; then
    error "requirements.txt not found after copying source code."
    exit 1
fi

# Create virtual environment as wix-printer user
sudo -u wix-printer python3 -m venv venv
sudo -u wix-printer bash -c "source venv/bin/activate && pip install --upgrade pip"
sudo -u wix-printer bash -c "source venv/bin/activate && pip install -r requirements.txt"

log "✅ Python environment setup complete"

# Phase 4: Create directories and set permissions
log "📁 Phase 4: Creating directories..."
sudo -u wix-printer mkdir -p data logs backups
sudo -u wix-printer chmod 755 data logs backups

# Phase 5: Database initialization
log "🗄️ Phase 5: Initializing database..."
sudo -u wix-printer bash -c "
source venv/bin/activate
python -c '
from wix_printer_service.database import Database
db = Database(\"data/wix_printer.db\")
print(\"Database initialized successfully!\")
'
"

# Phase 6: Interactive Configuration Setup
log "⚙️ Phase 6: Interactive configuration setup..."

# Function to detect printer
detect_printer() {
    log "🖨️ Detecting connected printers..."
    
    # Check for Epson printers via USB
    EPSON_USB=$(lsusb | grep -i epson | head -1)
    if [ ! -z "$EPSON_USB" ]; then
        log "✅ Found Epson printer via USB: $EPSON_USB"
        echo "usb"
        return 0
    fi
    
    # Check for network printers
    NETWORK_PRINTER=$(lpstat -p 2>/dev/null | grep -i epson | head -1)
    if [ ! -z "$NETWORK_PRINTER" ]; then
        log "✅ Found Epson printer via network: $NETWORK_PRINTER"
        echo "network"
        return 0
    fi
    
    # Check USB device paths
    for device in /dev/usb/lp* /dev/lp*; do
        if [ -e "$device" ]; then
            log "✅ Found printer device: $device"
            echo "usb:$device"
            return 0
        fi
    done
    
    warn "No Epson printer detected. Please connect your printer and try again."
    echo "none"
    return 1
}

# Function to get user input with default value
get_input() {
    local prompt="$1"
    local default="$2"
    local secret="$3"
    
    if [ "$secret" = "true" ]; then
        echo -n "$prompt"
        [ ! -z "$default" ] && echo -n " (default: ***hidden***)"
        echo -n ": "
        read -s user_input
        echo
    else
        echo -n "$prompt"
        [ ! -z "$default" ] && echo -n " (default: $default)"
        echo -n ": "
        read user_input
    fi
    
    if [ -z "$user_input" ]; then
        echo "$default"
    else
        echo "$user_input"
    fi
}

if [ ! -f ".env" ]; then
    echo ""
    echo "=========================================="
    echo "🔧 INTERACTIVE CONFIGURATION SETUP"
    echo "=========================================="
    echo ""
    echo "Let's configure your Wix Printer Service with Epic 2 Self-Healing capabilities!"
    echo ""
    
    # Wix API Configuration
    echo "📡 WIX API CONFIGURATION"
    echo "----------------------------------------"
    WIX_API_KEY=$(get_input "Enter your Wix API Key" "" "true")
    WIX_SITE_ID=$(get_input "Enter your Wix Site ID" "")
    WIX_API_BASE_URL=$(get_input "Wix API Base URL" "https://www.wixapis.com")
    echo ""
    
    # Printer Detection and Configuration
    echo "🖨️ PRINTER CONFIGURATION"
    echo "----------------------------------------"
    PRINTER_DETECTION=$(detect_printer)
    
    if [ "$PRINTER_DETECTION" = "none" ]; then
        echo "Manual printer configuration required:"
        PRINTER_TYPE=$(get_input "Printer type" "epson")
        PRINTER_INTERFACE=$(get_input "Printer interface (usb/network)" "usb")
        PRINTER_DEVICE_PATH=$(get_input "Printer device path" "/dev/usb/lp0")
    elif [[ "$PRINTER_DETECTION" == usb:* ]]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="usb"
        PRINTER_DEVICE_PATH="${PRINTER_DETECTION#usb:}"
        log "✅ Auto-configured USB printer: $PRINTER_DEVICE_PATH"
    elif [ "$PRINTER_DETECTION" = "usb" ]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="usb"
        PRINTER_DEVICE_PATH="/dev/usb/lp0"
        log "✅ Auto-configured USB printer"
    elif [ "$PRINTER_DETECTION" = "network" ]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="network"
        PRINTER_DEVICE_PATH=$(get_input "Printer IP address" "192.168.1.100")
        log "✅ Configured network printer"
    fi
    echo ""
    
    # Service Configuration
    echo "⚙️ SERVICE CONFIGURATION"
    echo "----------------------------------------"
    SERVICE_HOST=$(get_input "Service host" "0.0.0.0")
    SERVICE_PORT=$(get_input "Service port" "8000")
    LOG_LEVEL=$(get_input "Log level (DEBUG/INFO/WARNING/ERROR)" "INFO")
    echo ""
    
    # Epic 2 Self-Healing Configuration
    echo "🏥 EPIC 2 SELF-HEALING CONFIGURATION"
    echo "----------------------------------------"
    echo "Configure intelligent retry, health monitoring, and circuit breaker settings:"
    HEALTH_CHECK_INTERVAL=$(get_input "Health check interval (seconds)" "30")
    RETRY_MAX_ATTEMPTS=$(get_input "Maximum retry attempts" "5")
    CIRCUIT_BREAKER_FAILURE_THRESHOLD=$(get_input "Circuit breaker failure threshold" "3")
    CIRCUIT_BREAKER_TIMEOUT=$(get_input "Circuit breaker timeout (seconds)" "60")
    echo ""
    
    # Email Notifications
    echo "📧 EMAIL NOTIFICATIONS (Optional - can be configured later)"
    echo "----------------------------------------"
    echo "Configure email notifications for critical events:"
    read -p "Do you want to configure email notifications now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SMTP_SERVER=$(get_input "SMTP server (e.g., smtp.gmail.com)" "")
        SMTP_PORT=$(get_input "SMTP port" "587")
        SMTP_USERNAME=$(get_input "SMTP username/email" "")
        SMTP_PASSWORD=$(get_input "SMTP password" "" "true")
        NOTIFICATION_FROM_EMAIL=$(get_input "From email address" "$SMTP_USERNAME")
        NOTIFICATION_TO_EMAIL=$(get_input "To email address (for alerts)" "")
        SMTP_USE_TLS="true"
    else
        SMTP_SERVER=""
        SMTP_PORT="587"
        SMTP_USERNAME=""
        SMTP_PASSWORD=""
        NOTIFICATION_FROM_EMAIL=""
        NOTIFICATION_TO_EMAIL=""
        SMTP_USE_TLS="true"
        log "Email notifications can be configured later with: python scripts/setup-notifications.py"
    fi
    echo ""
    
    # Create .env file with user input
    log "Creating .env file with your configuration..."
    sudo -u wix-printer bash -c "cat > .env << EOF
# Database
DATABASE_URL=sqlite:///data/wix_printer.db

# Wix API Configuration
WIX_API_KEY=$WIX_API_KEY
WIX_SITE_ID=$WIX_SITE_ID
WIX_API_BASE_URL=$WIX_API_BASE_URL

# Printer Configuration
PRINTER_TYPE=$PRINTER_TYPE
PRINTER_INTERFACE=$PRINTER_INTERFACE
PRINTER_DEVICE_PATH=$PRINTER_DEVICE_PATH

# Service Configuration
SERVICE_HOST=$SERVICE_HOST
SERVICE_PORT=$SERVICE_PORT
LOG_LEVEL=$LOG_LEVEL

# Epic 2 Self-Healing Configuration
HEALTH_CHECK_INTERVAL=$HEALTH_CHECK_INTERVAL
RETRY_MAX_ATTEMPTS=$RETRY_MAX_ATTEMPTS
CIRCUIT_BREAKER_FAILURE_THRESHOLD=$CIRCUIT_BREAKER_FAILURE_THRESHOLD
CIRCUIT_BREAKER_TIMEOUT=$CIRCUIT_BREAKER_TIMEOUT
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30

# Email Notifications
SMTP_SERVER=$SMTP_SERVER
SMTP_PORT=$SMTP_PORT
SMTP_USERNAME=$SMTP_USERNAME
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_USE_TLS=$SMTP_USE_TLS
NOTIFICATION_FROM_EMAIL=$NOTIFICATION_FROM_EMAIL
NOTIFICATION_TO_EMAIL=$NOTIFICATION_TO_EMAIL
NOTIFICATION_THROTTLE_MINUTES=15

# Monitoring Configuration
ENABLE_PERFORMANCE_MONITORING=true
ENABLE_HEALTH_MONITORING=true
HEALTH_CHECK_ENDPOINT_ENABLED=true
METRICS_RETENTION_DAYS=30
EOF"
    
    log "✅ Configuration file created successfully!"
    echo ""
    echo "📋 CONFIGURATION SUMMARY:"
    echo "----------------------------------------"
    echo "Wix Site ID: $WIX_SITE_ID"
    echo "Printer: $PRINTER_TYPE ($PRINTER_INTERFACE) at $PRINTER_DEVICE_PATH"
    echo "Service: $SERVICE_HOST:$SERVICE_PORT"
    echo "Self-Healing: Enabled with Epic 2 features"
    echo "Email Notifications: $([ ! -z "$SMTP_SERVER" ] && echo "Configured" || echo "Not configured")"
    echo ""
    
else
    log ".env file already exists, skipping interactive configuration"
fi

# Phase 7: Service installation
log "🔧 Phase 7: Installing systemd service..."
if [ -f "deployment/wix-printer.service" ]; then
    sudo cp deployment/wix-printer.service /etc/systemd/system/
    sudo sed -i "s|/path/to/wix-pos-order|/opt/wix-printer-service|g" /etc/systemd/system/wix-printer.service
    sudo systemctl daemon-reload
    sudo systemctl enable wix-printer.service
    log "✅ Systemd service installed and enabled"
else
    warn "Service file not found, skipping service installation"
fi

# Phase 8: Test basic functionality
log "🧪 Phase 8: Testing basic functionality..."

# Test Python imports
sudo -u wix-printer bash -c "
source venv/bin/activate
python -c '
try:
    from wix_printer_service.database import Database
    from wix_printer_service.retry_manager import RetryManager
    from wix_printer_service.health_monitor import HealthMonitor
    from wix_printer_service.circuit_breaker import CircuitBreaker
    print(\"✅ All Epic 2 components imported successfully!\")
except ImportError as e:
    print(f\"❌ Import error: {e}\")
    exit(1)
'
"

# Test database connection
sudo -u wix-printer bash -c "
source venv/bin/activate
python -c '
from wix_printer_service.database import Database
db = Database(\"data/wix_printer.db\")
with db.get_connection() as conn:
    cursor = conn.execute(\"SELECT name FROM sqlite_master WHERE type=\\\"table\\\"\")
    tables = cursor.fetchall()
    print(f\"✅ Database has {len(tables)} tables\")
'
"

# Phase 9: Check printer connection
log "🖨️ Phase 9: Checking printer connection..."
if lsusb | grep -i epson > /dev/null; then
    log "✅ Epson printer detected via USB"
else
    warn "No Epson printer detected. Please connect your Epson TM-m30III printer"
fi

# Phase 10: Final status check
log "📊 Phase 10: Final system status..."

echo ""
echo "=========================================="
echo "🎉 RASPBERRY PI SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "✅ Epic 2 Features Ready:"
echo "   - Intelligent Retry System"
echo "   - Health Monitoring (Memory/CPU/Disk/Threads)"
echo "   - Circuit Breaker Protection"
echo "   - Self-Healing Orchestration"
echo "   - Email Notifications"
echo "   - 12 New API Endpoints"
echo ""
echo "📋 Next Steps:"
echo "1. Edit /opt/wix-printer-service/.env with your configuration"
echo "2. Run: python scripts/setup-notifications.py (for email setup)"
echo "3. Start service: sudo systemctl start wix-printer.service"
echo "4. Check status: sudo systemctl status wix-printer.service"
echo "5. Test API: curl http://localhost:8000/health"
echo ""
echo "🔧 Epic 2 Self-Healing Endpoints:"
echo "   - GET  /self-healing/status"
echo "   - POST /self-healing/trigger-check"
echo "   - GET  /health/metrics"
echo "   - GET  /circuit-breakers/status"
echo "   - GET  /retry-manager/status"
echo ""
echo "📖 Full documentation: deployment/raspberry-pi-setup-guide.md"
echo ""

# Check if service should be started
read -p "Do you want to start the service now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Starting wix-printer service..."
    sudo systemctl start wix-printer.service
    sleep 3
    
    if sudo systemctl is-active --quiet wix-printer.service; then
        log "✅ Service started successfully!"
        log "Testing API endpoints..."
        
        # Test basic endpoint
        if curl -s http://localhost:8000/health > /dev/null; then
            log "✅ API is responding"
            
            # Test Epic 2 endpoints
            echo ""
            echo "🧪 Testing Epic 2 Self-Healing Endpoints:"
            
            echo -n "  - Self-Healing Status: "
            if curl -s http://localhost:8000/self-healing/status > /dev/null; then
                echo "✅ OK"
            else
                echo "❌ Failed"
            fi
            
            echo -n "  - Health Metrics: "
            if curl -s http://localhost:8000/health/metrics > /dev/null; then
                echo "✅ OK"
            else
                echo "❌ Failed"
            fi
            
            echo -n "  - Circuit Breakers: "
            if curl -s http://localhost:8000/circuit-breakers/status > /dev/null; then
                echo "✅ OK"
            else
                echo "❌ Failed"
            fi
            
            echo -n "  - Retry Manager: "
            if curl -s http://localhost:8000/retry-manager/status > /dev/null; then
                echo "✅ OK"
            else
                echo "❌ Failed"
            fi
            
        else
            warn "API not responding yet, check service logs: sudo journalctl -u wix-printer.service -f"
        fi
    else
        error "Service failed to start, check logs: sudo journalctl -u wix-printer.service -n 20"
    fi
else
    log "Service not started. Start manually with: sudo systemctl start wix-printer.service"
fi

echo ""
log "🚀 Raspberry Pi setup complete! Your restaurant printing system is ready with full self-healing capabilities."
echo ""
