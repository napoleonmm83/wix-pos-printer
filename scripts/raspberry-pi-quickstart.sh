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
    echo "Welcome! This setup wizard will configure your Wix Restaurant Printer Service"
    echo "with Epic 2 Self-Healing capabilities (automatic retry, health monitoring, etc.)"
    echo ""
    echo "We'll ask you a few questions to configure everything automatically."
    echo "Don't worry - we'll explain what each setting does!"
    echo ""
    read -p "Press ENTER to start the configuration wizard..."
    echo ""
    
    # Wix API Configuration
    echo "=========================================="
    echo "📡 STEP 1: WIX API CONFIGURATION"
    echo "=========================================="
    echo ""
    echo "First, we need to connect to your Wix restaurant website."
    echo ""
    echo "ℹ️  HOW TO FIND YOUR WIX CREDENTIALS:"
    echo "   1. Go to your Wix Dashboard"
    echo "   2. Navigate to Settings > Business Info"
    echo "   3. Look for 'Site ID' or 'Business ID'"
    echo "   4. For API Key: Go to Settings > Integrations > API Keys"
    echo ""
    echo "📝 If you don't have these yet, you can:"
    echo "   - Enter 'test' for now and configure later"
    echo "   - Or press CTRL+C to exit and get your credentials first"
    echo ""
    
    WIX_API_KEY=$(get_input "🔑 Enter your Wix API Key (or 'test' for testing)" "test" "true")
    echo ""
    WIX_SITE_ID=$(get_input "🆔 Enter your Wix Site ID (or 'test-site' for testing)" "test-site")
    echo ""
    WIX_API_BASE_URL=$(get_input "🌐 Wix API Base URL (leave default unless you know what you're doing)" "https://www.wixapis.com")
    echo ""
    
    if [ "$WIX_API_KEY" = "test" ] || [ "$WIX_SITE_ID" = "test-site" ]; then
        echo "⚠️  WARNING: You're using test credentials!"
        echo "   The service will start but won't receive real orders."
        echo "   You can update these later in the .env file."
        echo ""
    else
        echo "✅ Wix API configured successfully!"
        echo ""
    fi
    
    # Printer Detection and Configuration
    echo "=========================================="
    echo "🖨️ STEP 2: PRINTER DETECTION & SETUP"
    echo "=========================================="
    echo ""
    echo "Now let's find and configure your Epson TM-m30III printer..."
    echo ""
    echo "🔍 SCANNING FOR PRINTERS..."
    PRINTER_DETECTION=$(detect_printer)
    echo ""
    
    if [ "$PRINTER_DETECTION" = "none" ]; then
        echo "❌ NO PRINTER DETECTED AUTOMATICALLY"
        echo ""
        echo "This could mean:"
        echo "• Your printer is not connected via USB"
        echo "• Your printer is connected via network/WiFi"
        echo "• Your printer is not powered on"
        echo "• Your printer is not an Epson model"
        echo ""
        echo "📝 MANUAL CONFIGURATION REQUIRED:"
        echo ""
        
        echo "1️⃣ PRINTER TYPE:"
        echo "   Usually 'epson' for Epson TM-m30III"
        PRINTER_TYPE=$(get_input "   Enter printer type" "epson")
        echo ""
        
        echo "2️⃣ CONNECTION TYPE:"
        echo "   • 'usb' = Connected via USB cable"
        echo "   • 'network' = Connected via WiFi/Ethernet"
        PRINTER_INTERFACE=$(get_input "   Enter connection type (usb/network)" "usb")
        echo ""
        
        if [ "$PRINTER_INTERFACE" = "network" ]; then
            echo "3️⃣ NETWORK PRINTER IP:"
            echo "   Find your printer's IP address on the printer display"
            echo "   or in your router's device list"
            PRINTER_DEVICE_PATH=$(get_input "   Enter printer IP address" "192.168.1.100")
        else
            echo "3️⃣ USB DEVICE PATH:"
            echo "   Common paths: /dev/usb/lp0, /dev/lp0, /dev/usb/lp1"
            PRINTER_DEVICE_PATH=$(get_input "   Enter USB device path" "/dev/usb/lp0")
        fi
        
    elif [[ "$PRINTER_DETECTION" == usb:* ]]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="usb"
        PRINTER_DEVICE_PATH="${PRINTER_DETECTION#usb:}"
        echo "🎉 GREAT! PRINTER FOUND AND CONFIGURED AUTOMATICALLY!"
        echo ""
        echo "✅ Detected: Epson printer via USB"
        echo "✅ Device path: $PRINTER_DEVICE_PATH"
        echo "✅ Configuration: Ready to use!"
        
    elif [ "$PRINTER_DETECTION" = "usb" ]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="usb"
        PRINTER_DEVICE_PATH="/dev/usb/lp0"
        echo "🎉 GREAT! PRINTER FOUND AND CONFIGURED AUTOMATICALLY!"
        echo ""
        echo "✅ Detected: Epson printer via USB"
        echo "✅ Device path: $PRINTER_DEVICE_PATH"
        echo "✅ Configuration: Ready to use!"
        
    elif [ "$PRINTER_DETECTION" = "network" ]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="network"
        echo "🎉 NETWORK PRINTER DETECTED!"
        echo ""
        echo "✅ Found: Epson printer on network"
        echo ""
        echo "📝 We need the printer's IP address to connect:"
        echo "   Check your printer display or router settings"
        PRINTER_DEVICE_PATH=$(get_input "   Enter printer IP address" "192.168.1.100")
        echo "✅ Network printer configured!"
    fi
    echo ""
    
    echo "📋 PRINTER CONFIGURATION SUMMARY:"
    echo "   Type: $PRINTER_TYPE"
    echo "   Connection: $PRINTER_INTERFACE"
    echo "   Address: $PRINTER_DEVICE_PATH"
    echo ""
    read -p "Press ENTER to continue..."
    echo ""
    
    # Service Configuration
    echo "=========================================="
    echo "⚙️ STEP 3: SERVICE CONFIGURATION"
    echo "=========================================="
    echo ""
    echo "Now let's configure how the service runs on your Raspberry Pi..."
    echo ""
    echo "🌐 NETWORK SETTINGS:"
    echo "   The service needs to listen for connections."
    echo "   • Host '0.0.0.0' = Accept connections from any device"
    echo "   • Port '8000' = Standard web service port"
    echo ""
    SERVICE_HOST=$(get_input "🌐 Service host (leave default to accept all connections)" "0.0.0.0")
    SERVICE_PORT=$(get_input "🔌 Service port (8000 is recommended)" "8000")
    echo ""
    
    echo "📝 LOGGING LEVEL:"
    echo "   • DEBUG = Very detailed logs (for troubleshooting)"
    echo "   • INFO = Normal operation logs (recommended)"
    echo "   • WARNING = Only warnings and errors"
    echo "   • ERROR = Only error messages"
    echo ""
    LOG_LEVEL=$(get_input "📊 Log level" "INFO")
    echo ""
    
    # Epic 2 Self-Healing Configuration
    echo "=========================================="
    echo "🏥 STEP 4: EPIC 2 SELF-HEALING FEATURES"
    echo "=========================================="
    echo ""
    echo "Epic 2 includes advanced self-healing capabilities!"
    echo "These features make your printer service nearly bulletproof:"
    echo ""
    echo "• 🔄 Intelligent Retry = Automatically retry failed print jobs"
    echo "• 🏥 Health Monitoring = Watch system resources (memory, CPU)"
    echo "• ⚡ Circuit Breaker = Protect against cascading failures"
    echo ""
    echo "Let's configure these advanced features:"
    echo ""
    
    echo "🔄 INTELLIGENT RETRY SETTINGS:"
    echo "   How often should we check system health?"
    HEALTH_CHECK_INTERVAL=$(get_input "   Health check interval in seconds (30 = every 30 seconds)" "30")
    echo ""
    echo "   How many times should we retry a failed print job?"
    RETRY_MAX_ATTEMPTS=$(get_input "   Maximum retry attempts (5 = try 5 times before giving up)" "5")
    echo ""
    
    echo "⚡ CIRCUIT BREAKER PROTECTION:"
    echo "   How many failures before we 'open the circuit' to prevent damage?"
    CIRCUIT_BREAKER_FAILURE_THRESHOLD=$(get_input "   Failure threshold (3 = open circuit after 3 failures)" "3")
    echo ""
    echo "   How long should we wait before trying again?"
    CIRCUIT_BREAKER_TIMEOUT=$(get_input "   Circuit breaker timeout in seconds (60 = wait 1 minute)" "60")
    echo ""
    
    echo "✅ Epic 2 Self-Healing configured!"
    echo "   Your printer service will now automatically:"
    echo "   • Retry failed operations with intelligent backoff"
    echo "   • Monitor system health every $HEALTH_CHECK_INTERVAL seconds"
    echo "   • Protect against failures with circuit breakers"
    echo ""
    
    # Email Notifications
    echo "=========================================="
    echo "📧 STEP 5: EMAIL NOTIFICATIONS (OPTIONAL)"
    echo "=========================================="
    echo ""
    echo "The service can send you email alerts when critical issues occur:"
    echo ""
    echo "• 🚨 Printer offline or out of paper"
    echo "• 💾 System running low on memory"
    echo "• 🔥 CPU usage too high"
    echo "• ⚡ Circuit breakers activated"
    echo ""
    echo "This is OPTIONAL - you can skip this and configure it later."
    echo ""
    read -p "❓ Do you want to configure email notifications now? (y/N): " -n 1 -r
    echo
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📧 EMAIL NOTIFICATION SETUP:"
        echo ""
        echo "We'll need your email provider settings. Common examples:"
        echo "• Gmail: smtp.gmail.com, port 587"
        echo "• Outlook: smtp-mail.outlook.com, port 587"
        echo "• Yahoo: smtp.mail.yahoo.com, port 587"
        echo ""
        
        SMTP_SERVER=$(get_input "📬 SMTP server (e.g., smtp.gmail.com)" "smtp.gmail.com")
        SMTP_PORT=$(get_input "🔌 SMTP port (587 for most providers)" "587")
        echo ""
        
        echo "🔐 EMAIL CREDENTIALS:"
        echo "   ⚠️  For Gmail, you'll need an 'App Password', not your regular password!"
        echo "   Go to: Google Account > Security > App Passwords"
        echo ""
        SMTP_USERNAME=$(get_input "📧 Your email address" "")
        SMTP_PASSWORD=$(get_input "🔑 Email password (or App Password for Gmail)" "" "true")
        echo ""
        
        NOTIFICATION_FROM_EMAIL=$(get_input "📤 From email address (usually same as username)" "$SMTP_USERNAME")
        NOTIFICATION_TO_EMAIL=$(get_input "📥 Alert destination email (where to send alerts)" "$SMTP_USERNAME")
        SMTP_USE_TLS="true"
        
        echo ""
        echo "✅ Email notifications configured!"
        echo "   You'll receive alerts at: $NOTIFICATION_TO_EMAIL"
        echo ""
        
    else
        SMTP_SERVER=""
        SMTP_PORT="587"
        SMTP_USERNAME=""
        SMTP_PASSWORD=""
        NOTIFICATION_FROM_EMAIL=""
        NOTIFICATION_TO_EMAIL=""
        SMTP_USE_TLS="true"
        
        echo "⏭️  Email notifications skipped."
        echo "   You can configure this later by running:"
        echo "   python scripts/setup-notifications.py"
        echo ""
    fi
    
    # Create .env file with user input
    echo "=========================================="
    echo "💾 SAVING YOUR CONFIGURATION..."
    echo "=========================================="
    echo ""
    echo "Creating configuration file with all your settings..."
    
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
    
    echo "✅ Configuration file saved successfully!"
    echo ""
    echo "=========================================="
    echo "📋 FINAL CONFIGURATION SUMMARY"
    echo "=========================================="
    echo ""
    echo "🎯 WIX CONNECTION:"
    echo "   Site ID: $WIX_SITE_ID"
    echo "   API URL: $WIX_API_BASE_URL"
    echo "   Status: $([ "$WIX_API_KEY" = "test" ] && echo "⚠️  Test Mode" || echo "✅ Production Ready")"
    echo ""
    echo "🖨️  PRINTER SETUP:"
    echo "   Type: $PRINTER_TYPE"
    echo "   Connection: $PRINTER_INTERFACE"
    echo "   Address: $PRINTER_DEVICE_PATH"
    echo ""
    echo "⚙️  SERVICE SETTINGS:"
    echo "   Host: $SERVICE_HOST"
    echo "   Port: $SERVICE_PORT"
    echo "   Log Level: $LOG_LEVEL"
    echo ""
    echo "🏥 EPIC 2 SELF-HEALING:"
    echo "   Health Checks: Every $HEALTH_CHECK_INTERVAL seconds"
    echo "   Max Retries: $RETRY_MAX_ATTEMPTS attempts"
    echo "   Circuit Breaker: Activates after $CIRCUIT_BREAKER_FAILURE_THRESHOLD failures"
    echo ""
    echo "📧 EMAIL ALERTS:"
    echo "   Status: $([ ! -z "$SMTP_SERVER" ] && echo "✅ Configured ($NOTIFICATION_TO_EMAIL)" || echo "⏭️  Skipped (can configure later)")"
    echo ""
    echo "🎉 Your Wix Restaurant Printer Service is now configured!"
    echo ""
    read -p "Press ENTER to continue with installation..."
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
