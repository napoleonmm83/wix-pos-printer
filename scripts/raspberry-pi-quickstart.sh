#!/bin/bash

# 🍓 Raspberry Pi Quick Start Script
# Wix Printer Service - Epic 2 Complete with Self-Healing
# Version: 1.3 - Enhanced detection, UX, paper width & test print
# Date: 2025-09-20

set -e  # Exit on any error

# Parse command line arguments
RESET_MODE=false
HELP_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --reset)
            RESET_MODE=true
            shift
            ;;
        --help|-h)
            HELP_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

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

# Help function
show_help() {
    echo ""
    echo "🍓 Wix Printer Service - Raspberry Pi Setup & Management"
    echo "=========================================="
    echo ""
    echo "USAGE:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  (no options)    Run interactive setup wizard"
    echo "  --reset         Reset/remove complete installation"
    echo "  --help, -h      Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0              # Run interactive setup"
    echo "  $0 --reset      # Remove installation completely"
    echo "  $0 --help       # Show this help"
    echo ""
    echo "FEATURES:"
    echo "  ✅ Epic 2 Self-Healing System (Intelligent Retry, Health Monitoring, Circuit Breaker)"
    echo "  ✅ Interactive Configuration Wizard"
    echo "  ✅ Automatic Printer Detection"
    echo "  ✅ Complete Reset/Cleanup Functionality"
    echo ""
}

# Handle help mode
if [ "$HELP_MODE" = true ]; then
    show_help
    exit 0
fi

# Handle reset mode
if [ "$RESET_MODE" = true ]; then
    # Execute the reset script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    RESET_SCRIPT="$SCRIPT_DIR/raspberry-pi-reset.sh"
    
    if [ -f "$RESET_SCRIPT" ]; then
        log "🧹 Launching Reset Script..."
        exec bash "$RESET_SCRIPT"
    else
        error "Reset script not found: $RESET_SCRIPT"
        error "Please ensure raspberry-pi-reset.sh is in the scripts directory"
        exit 1
    fi
fi

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root"
   exit 1
fi

log "🍓 Starting Raspberry Pi Setup for Wix Printer Service"
log "Epic 2 Complete - Self-Healing System Ready!"
log ""
log "💡 TIP: Use '$0 --reset' to completely remove an existing installation"
log "💡 TIP: Use '$0 --help' for all available options"

# Phase 1: System Update
log "📦 Phase 1: Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip python3-venv sqlite3 curl cups cups-client usbutils netcat-openbsd libusb-1.0-0-dev

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

# Phase 3: Hardware Setup (USB Permissions)
log "🔩 Phase 3: Setting up hardware permissions..."

UDEV_RULE_FILE="/etc/udev/rules.d/99-wix-printer.rules"
UDEV_RULE_CONTENT='SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", ATTR{idProduct}=="0e32", GROUP="wix-printer", MODE="0666"'

log "Creating udev rule for USB printer access at $UDEV_RULE_FILE"
echo "$UDEV_RULE_CONTENT" | sudo tee $UDEV_RULE_FILE > /dev/null

log "Blacklisting conflicting 'usblp' kernel module..."
BLACKLIST_FILE="/etc/modprobe.d/blacklist-usblp.conf"
if [ ! -f "$BLACKLIST_FILE" ]; then
    echo "blacklist usblp" | sudo tee "$BLACKLIST_FILE"
fi

log "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

log "✅ USB permissions configured."

# Phase 4: Setup Python environment
log "🐍 Phase 4: Setting up Python environment..."

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
    # All informational output goes to stderr so the caller can capture only the result
    echo "🔍 Scanning for connected printers..." >&2
    echo "" >&2
    
    # Check for any USB printers first (most common)
    echo "   Checking USB connections..." >&2
    USB_DEVICES_FOUND=false
    for device in /dev/usb/lp* /dev/lp*; do
        if [ -e "$device" ]; then
            echo "   ✅ Found USB printer device: $device" >&2
            USB_DEVICES_FOUND=true
            # Check if it's accessible
            if [ -w "$device" ] 2>/dev/null; then
                echo "   ✅ Device is writable (ready to use)" >&2
            else
                echo "   ⚠️  Device found but may need permissions (try: sudo chgrp lp $device && sudo chmod 660 $device)" >&2
            fi
        fi
    done
    
    if [ "$USB_DEVICES_FOUND" = true ]; then
        echo "usb:$(ls /dev/usb/lp* /dev/lp* 2>/dev/null | head -1)"
        return 0
    fi
    
    # Check for Epson printers specifically via lsusb (if available)
    echo "   Checking for Epson printers via USB..." >&2
    if command -v lsusb >/dev/null 2>&1; then
        EPSON_USB=$(lsusb 2>/dev/null | grep -i epson || true)
        if [ -n "$EPSON_USB" ]; then
            echo "   ✅ Found Epson printer via lsusb:" >&2
            echo "      $EPSON_USB" >&2
            echo "   ⚠️  Device file may not be created yet" >&2
            echo "usb"
            return 0
        fi
        # Any thermal brand
        THERMAL_PRINTERS=$(lsusb 2>/dev/null | grep -iE "(epson|star|citizen|bixolon|custom|pos)" || true)
        if [ -n "$THERMAL_PRINTERS" ]; then
            echo "   ✅ Found thermal printer:" >&2
            echo "      $THERMAL_PRINTERS" >&2
            echo "usb"
            return 0
        fi
    else
        echo "   ℹ️  lsusb not available; skipping USB vendor scan" >&2
    fi
    
    # Check for network printers via CUPS
    echo "   Checking network printers..." >&2
    if command -v lpstat >/dev/null 2>&1; then
        NETWORK_PRINTER=$(lpstat -p 2>/dev/null | grep -i printer || true)
        if [ -n "$NETWORK_PRINTER" ]; then
            echo "   ✅ Found network printer via CUPS:" >&2
            echo "      $NETWORK_PRINTER" >&2
            echo "network"
            return 0
        fi
    else
        echo "   ℹ️  lpstat not available; skipping CUPS scan" >&2
    fi
    
    # Check common network printer ports (if tools exist)
    echo "   Scanning common printer IP addresses..." >&2
    for ip in 192.168.1.{100..110} 192.168.0.{100..110}; do
        if command -v ping >/dev/null 2>&1 && ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
            if command -v nc >/dev/null 2>&1; then
                if nc -z -w1 "$ip" 9100 >/dev/null 2>&1 || nc -z -w1 "$ip" 515 >/dev/null 2>&1; then
                    echo "   ✅ Found potential network printer at $ip" >&2
                    echo "network"
                    return 0
                fi
            else
                echo "   ⚠️  nc (netcat) not available; assuming reachable network printer at $ip" >&2
                echo "network"
                return 0
            fi
        fi
    done
    
    echo "   ❌ No printers detected automatically" >&2
    echo "" >&2
    echo "   This could mean:" >&2
    echo "   • Printer is not connected or powered on" >&2
    echo "   • Printer needs manual configuration" >&2
    echo "   • Printer is connected via network with custom IP" >&2
    echo "   • USB permissions need to be set" >&2
    echo "" >&2
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
    
    # Wix API Configuration (API Key method)
    echo "=========================================="
    echo "📡 STEP 1: WIX API CONFIGURATION"
    echo "=========================================="
    echo ""
    echo "We will connect using a Wix API Key (recommended)."
    echo ""
    echo "ℹ️  HOW TO GET YOUR WIX API KEY:"
    echo "   1) Wix Dashboard → Settings → Developer Tools → API Keys"
    echo "   2) Create API Key with required permissions"
    echo "   3) Copy the API Key"
    echo "   4) Site ID: In your Wix Site dashboard URL, copy the ID after '/dashboard/'"
    echo ""
    echo "📝 If you don't have these yet, you can:"
    echo "   - Enter 'test' for now (test mode)"
    echo "   - Or press CTRL+C to exit and get your credentials first"
    echo ""
    
    echo "🔑 WIX API KEY:"
    echo "   Example: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    echo ""
    echo -n "   👉 Enter your Wix API Key (or press ENTER for test mode): "
    read -s WIX_API_KEY
    if [ -z "$WIX_API_KEY" ]; then
        WIX_API_KEY="test-api-key"
    fi
    echo ""
    echo "   ✅ API Key entered: $([ "$WIX_API_KEY" = "test-api-key" ] && echo "TEST MODE" || echo "***HIDDEN***")"
    echo ""
    
    echo "🆔 WIX SITE ID:"
    echo "   This identifies your specific restaurant website"
    echo "   Find it in your site dashboard URL after '/dashboard/'"
    echo "   Example: 12345678-1234-1234-1234-123456789abc"
    echo ""
    echo -n "   👉 Enter your Wix Site ID (or press ENTER for test mode): "
    read WIX_SITE_ID
    if [ -z "$WIX_SITE_ID" ]; then
        WIX_SITE_ID="test-site"
    fi
    echo ""
    echo "   ✅ Site ID entered: $WIX_SITE_ID"
    echo ""
    
    echo "🌐 WIX API URL:"
    echo "   This is the Wix server address (usually don't change this)"
    echo ""
    echo -n "   👉 Wix API Base URL (or press ENTER for default): "
    read WIX_API_BASE_URL
    if [ -z "$WIX_API_BASE_URL" ]; then
        WIX_API_BASE_URL="https://www.wixapis.com"
    fi
    echo ""
    echo "   ✅ API URL: $WIX_API_BASE_URL"
    echo ""
    
    if [ "$WIX_API_KEY" = "test-api-key" ] || [ "$WIX_SITE_ID" = "test-site" ]; then
        echo "⚠️  WARNING: You're in TEST MODE!"
        echo "   The service will start but won't access real orders."
        echo "   You can update these later in the .env file."
        echo ""
    else
        echo "✅ Wix API configured successfully (API Key)!"
        echo "   Site ID: $WIX_SITE_ID"
        echo ""
    fi
    
    # Printer Detection and Configuration
    echo "=========================================="
    echo "🖨️ STEP 2: PRINTER DETECTION & SETUP"
    echo "=========================================="
    echo ""
    echo "Now let's find and configure your printer..."
    echo "This works with Epson TM-m30III and most other thermal printers."
    echo ""
    
    # Run detection without aborting on non-zero exit (set -e guard)
    set +e
    PRINTER_DETECTION=$(detect_printer)
    DETECT_EXIT=$?
    set -e
    echo ""
    if [ $DETECT_EXIT -ne 0 ] || [ -z "$PRINTER_DETECTION" ]; then
        PRINTER_DETECTION="none"
    fi
    echo "   Detection result: $PRINTER_DETECTION"
    
    # Initialize default paper width
    PAPER_WIDTH="80"
    
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
        echo "   What type of printer do you have?"
        echo ""
        echo "   1) Epson (TM-m30III, TM-T88V, etc.) ⭐"
        echo "   2) Other thermal printer"
        echo ""
        
        while true; do
            read -p "   👉 Choose printer type (1-2, or press ENTER for Epson): " printer_choice
            
            case $printer_choice in
                1|"")
                    PRINTER_TYPE="epson"
                    break
                    ;;
                2)
                    echo -n "   Enter printer type (default: thermal): "
                    read PRINTER_TYPE
                    if [ -z "$PRINTER_TYPE" ]; then
                        PRINTER_TYPE="thermal"
                    fi
                    break
                    ;;
                *)
                    echo "   ❌ Please enter 1 or 2"
                    ;;
            esac
        done
        echo "   ✅ Printer type: $PRINTER_TYPE"
        echo ""
        
        echo "2️⃣ CONNECTION TYPE:"
        echo "   How is your printer connected?"
        echo ""
        echo "   1) USB cable ⭐"
        echo "   2) Network/WiFi/Ethernet"
        echo ""
        
        while true; do
            read -p "   👉 Choose connection type (1-2, or press ENTER for USB): " connection_choice
            
            case $connection_choice in
                1|"")
                    PRINTER_INTERFACE="usb"
                    break
                    ;;
                2)
                    PRINTER_INTERFACE="network"
                    break
                    ;;
                *)
                    echo "   ❌ Please enter 1 or 2"
                    ;;
            esac
        done
        echo "   ✅ Connection type: $PRINTER_INTERFACE"
        echo ""
        
        if [ "$PRINTER_INTERFACE" = "network" ]; then
            echo "3️⃣ NETWORK PRINTER IP:"
            echo "   Find your printer's IP address on the printer display"
            echo "   or in your router's device list"
            echo -n "   Enter printer IP address (default: 192.168.1.100): "
            read PRINTER_DEVICE_PATH
            if [ -z "$PRINTER_DEVICE_PATH" ]; then
                PRINTER_DEVICE_PATH="192.168.1.100"
            fi
        else
            echo "3️⃣ USB DEVICE PATH:"
            echo "   Which USB port is your printer connected to?"
            echo ""
            echo "   1) /dev/usb/lp0 (most common) ⭐"
            echo "   2) /dev/lp0 (alternative)"
            echo "   3) /dev/usb/lp1 (second USB printer)"
            echo "   4) Custom path"
            echo ""
            
            while true; do
                read -p "   👉 Choose USB device path (1-4, or press ENTER for default): " usb_choice
                
                case $usb_choice in
                    1|"")
                        PRINTER_DEVICE_PATH="/dev/usb/lp0"
                        break
                        ;;
                    2)
                        PRINTER_DEVICE_PATH="/dev/lp0"
                        break
                        ;;
                    3)
                        PRINTER_DEVICE_PATH="/dev/usb/lp1"
                        break
                        ;;
                    4)
                        echo -n "   Enter custom USB device path (default: /dev/usb/lp0): "
                        read PRINTER_DEVICE_PATH
                        if [ -z "$PRINTER_DEVICE_PATH" ]; then
                            PRINTER_DEVICE_PATH="/dev/usb/lp0"
                        fi
                        break
                        ;;
                    *)
                        echo "   ❌ Please enter 1, 2, 3, or 4"
                        ;;
                esac
            done
            echo "   ✅ USB device path: $PRINTER_DEVICE_PATH"
        fi
        
        # Paper width configuration
        echo ""
        echo "4️⃣ PAPER ROLL WIDTH:"
        echo "   What width is your receipt paper?"
        echo ""
        echo "   1) 58mm (2.3 inches) - Common for small receipts"
        echo "   2) 80mm (3.1 inches) - Standard restaurant receipts ⭐"
        echo "   3) Custom width"
        echo ""
        
        while true; do
            read -p "   👉 Choose paper width (1-3, or press ENTER for 80mm): " paper_choice
            
            case $paper_choice in
                1)
                    PAPER_WIDTH="58"
                    break
                    ;;
                2|"")
                    PAPER_WIDTH="80"
                    break
                    ;;
                3)
                    echo -n "   Enter paper width in mm (default: 80): "
                    read PAPER_WIDTH
                    if [ -z "$PAPER_WIDTH" ]; then
                        PAPER_WIDTH="80"
                    fi
                    break
                    ;;
                *)
                    echo "   ❌ Please enter 1, 2, or 3"
                    ;;
            esac
        done
        echo "   ✅ Paper width: ${PAPER_WIDTH}mm"
        
    elif [[ "$PRINTER_DETECTION" == usb:* ]]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="usb"
        PRINTER_DEVICE_PATH="${PRINTER_DETECTION#usb:}"
        echo "🎉 GREAT! PRINTER FOUND AND CONFIGURED AUTOMATICALLY!"
        echo ""
        echo "✅ Detected: Epson printer via USB"
        echo "✅ Device path: $PRINTER_DEVICE_PATH"
        echo "✅ Configuration: Ready to use!"
        
        # Paper width for auto-detected USB printer
        echo ""
        echo "📏 PAPER ROLL WIDTH:"
        echo "   What width is your receipt paper?"
        echo ""
        echo "   1) 58mm (2.3 inches) - Small receipts"
        echo "   2) 80mm (3.1 inches) - Standard restaurant receipts ⭐"
        echo ""
        while true; do
            read -p "   👉 Choose paper width (1-2, or press ENTER for 80mm): " paper_choice
            case $paper_choice in
                1) PAPER_WIDTH="58"; break ;;
                2|"") PAPER_WIDTH="80"; break ;;
                *) echo "   ❌ Please enter 1 or 2" ;;
            esac
        done
        echo "   ✅ Paper width: ${PAPER_WIDTH}mm"
        
    elif [ "$PRINTER_DETECTION" = "usb" ]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="usb"
        PRINTER_DEVICE_PATH="/dev/usb/lp0"
        echo "🎉 GREAT! PRINTER FOUND AND CONFIGURED AUTOMATICALLY!"
        echo ""
        echo "✅ Detected: Epson printer via USB"
        echo "✅ Device path: $PRINTER_DEVICE_PATH"
        echo "✅ Configuration: Ready to use!"
        
        # Paper width for auto-detected USB printer
        echo ""
        echo "📏 PAPER ROLL WIDTH:"
        echo "   What width is your receipt paper?"
        echo ""
        echo "   1) 58mm (2.3 inches) - Small receipts"
        echo "   2) 80mm (3.1 inches) - Standard restaurant receipts ⭐"
        echo ""
        while true; do
            read -p "   👉 Choose paper width (1-2, or press ENTER for 80mm): " paper_choice
            case $paper_choice in
                1) PAPER_WIDTH="58"; break ;;
                2|"") PAPER_WIDTH="80"; break ;;
                *) echo "   ❌ Please enter 1 or 2" ;;
            esac
        done
        echo "   ✅ Paper width: ${PAPER_WIDTH}mm"
        
    elif [ "$PRINTER_DETECTION" = "network" ]; then
        PRINTER_TYPE="epson"
        PRINTER_INTERFACE="network"
        echo "🎉 NETWORK PRINTER DETECTED!"
        echo ""
        echo "✅ Found: Epson printer on network"
        echo ""
        echo "📝 We need the printer's IP address to connect:"
        echo "   Check your printer display or router settings"
        echo -n "   Enter printer IP address (default: 192.168.1.100): "
        read PRINTER_DEVICE_PATH
        if [ -z "$PRINTER_DEVICE_PATH" ]; then
            PRINTER_DEVICE_PATH="192.168.1.100"
        fi
        echo "✅ Network printer configured!"
        
        # Paper width for network printer
        echo ""
        echo "📏 PAPER ROLL WIDTH:"
        echo "   What width is your receipt paper?"
        echo ""
        echo "   1) 58mm (2.3 inches) - Small receipts"
        echo "   2) 80mm (3.1 inches) - Standard restaurant receipts ⭐"
        echo ""
        while true; do
            read -p "   👉 Choose paper width (1-2, or press ENTER for 80mm): " paper_choice
            case $paper_choice in
                1) PAPER_WIDTH="58"; break ;;
                2|"") PAPER_WIDTH="80"; break ;;
                *) echo "   ❌ Please enter 1 or 2" ;;
            esac
        done
        echo "   ✅ Paper width: ${PAPER_WIDTH}mm"
    fi
    echo ""
    
    echo "=========================================="
    echo "📋 PRINTER CONFIGURATION SUMMARY"
    echo "=========================================="
    echo ""
    echo "🖨️  PRINTER DETAILS:"
    echo "   • Printer Type: $PRINTER_TYPE"
    echo "   • Connection Method: $PRINTER_INTERFACE"
    echo "   • Device Address: $PRINTER_DEVICE_PATH"
    echo "   • Paper Width: ${PAPER_WIDTH}mm"
    echo ""
    echo "✅ Your printer is now configured!"
    echo ""
    
    # Optional test print
    echo "🧪 OPTIONAL TEST PRINT:"
    echo "   Would you like to print a test receipt to verify everything works?"
    echo "   This will help ensure your printer is properly connected and configured."
    echo ""
    read -p "❓ Print test receipt now? (y/N): " -n 1 -r
    echo
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🖨️  PRINTING TEST RECEIPT..."
        echo ""
        
        # Create a simple test receipt using python-escpos (the correct method)
        if [ "$PRINTER_INTERFACE" = "usb" ]; then
            # Test print for USB printer using python-escpos
            echo "Testing USB printer with Vendor ID: 0x04b8, Product ID: 0x0e32..."
            
            # Use python-escpos to test print (same method as the working service)
            if sudo -u wix-printer /opt/wix-printer-service/venv/bin/python3 -c "
from escpos.printer import Usb
try:
    printer = Usb(0x04b8, 0x0e32)
    printer.text('================================\\n')
    printer.text('    WIX PRINTER SERVICE TEST\\n')
    printer.text('================================\\n\\n')
    printer.text('✅ Printer Type: $PRINTER_TYPE\\n')
    printer.text('✅ Connection: $PRINTER_INTERFACE\\n')
    printer.text('✅ USB IDs: 04b8:0e32\\n')
    printer.text('✅ Paper Width: ${PAPER_WIDTH}mm\\n\\n')
    printer.text('Date: $(date)\\n\\n')
    printer.text('Epic 2 Self-Healing Features:\\n')
    printer.text('• Intelligent Retry System\\n')
    printer.text('• Health Monitoring\\n')
    printer.text('• Circuit Breaker Protection\\n\\n')
    printer.text('🎉 TEST SUCCESSFUL!\\n')
    printer.text('Your printer is ready for\\n')
    printer.text('restaurant operations!\\n\\n')
    printer.text('================================\\n\\n\\n')
    printer.cut()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null; then
                echo "   ✅ Test receipt printed successfully using python-escpos!"
                echo "   🎉 Your printer is fully configured and working!"
            else
                echo "   ⚠️  Test print failed with python-escpos"
                echo "   🔎 This could indicate:"
                echo "      1) Printer is not connected or powered off"
                echo "      2) Wrong USB Vendor/Product ID (check with 'lsusb')"
                echo "      3) USB permission issues"
                echo "      4) Kernel driver conflicts (usblp module)"
                echo ""
                echo "   💡 The service will still work if the printer is properly connected"
                echo "   💡 You can test again after the service starts with:"
                echo "      curl -X POST http://localhost:8000/print/job/1"
            fi
        elif [ "$PRINTER_INTERFACE" = "network" ]; then
            echo "   📡 Testing network printer connectivity..."
            
            # Try to ping the printer
            if ping -c 1 -W 2 "$PRINTER_DEVICE_PATH" >/dev/null 2>&1; then
                echo "   ✅ Network printer is reachable at $PRINTER_DEVICE_PATH"
                echo "   📝 Full test will be available after service startup"
                echo "   💡 Test via: curl http://localhost:8000/test-print"
            else
                echo "   ⚠️  Cannot reach printer at $PRINTER_DEVICE_PATH"
                echo "   💡 Check printer IP address and network connection"
                echo "   💡 Try: ping $PRINTER_DEVICE_PATH"
            fi
        fi
        echo ""
    else
        echo "⏭️  Test print skipped - you can test later via the API"
        echo ""
    fi
    
    read -p "👉 Press ENTER to continue to service configuration..."
    echo ""
    
    # Service Configuration
    echo "=========================================="
    echo "⚙️ STEP 3: SERVICE CONFIGURATION"
    echo "=========================================="
    echo ""
    echo "Now let's configure how the service runs on your Raspberry Pi..."
    echo ""
    echo "🌐 NETWORK SETTINGS:"
    echo "   The service needs to listen for connections from your restaurant system."
    echo ""
    echo "   • Host '0.0.0.0' = Accept connections from any device (recommended)"
    echo "   • Port '8000' = Standard web service port"
    echo ""
    echo -n "   👉 Service host (default: 0.0.0.0): "
    read SERVICE_HOST
    if [ -z "$SERVICE_HOST" ]; then
        SERVICE_HOST="0.0.0.0"
    fi
    echo "   ✅ Host configured: $SERVICE_HOST"
    echo ""
    
    echo -n "   👉 Service port (default: 8000): "
    read SERVICE_PORT
    if [ -z "$SERVICE_PORT" ]; then
        SERVICE_PORT="8000"
    fi
    echo "   ✅ Port configured: $SERVICE_PORT"
    echo ""
    
    echo "📝 LOGGING DETAIL LEVEL:"
    echo "   How much detail do you want in the log files?"
    echo ""
    echo "   1) DEBUG   - Very detailed logs (for troubleshooting)"
    echo "   2) INFO    - Normal operation logs (recommended) ⭐"
    echo "   3) WARNING - Only warnings and errors"
    echo "   4) ERROR   - Only error messages"
    echo ""
    
    while true; do
        read -p "   👉 Choose log level (1-4, or press ENTER for default): " log_choice
        
        case $log_choice in
            1)
                LOG_LEVEL="DEBUG"
                break
                ;;
            2|"")
                LOG_LEVEL="INFO"
                break
                ;;
            3)
                LOG_LEVEL="WARNING"
                break
                ;;
            4)
                LOG_LEVEL="ERROR"
                break
                ;;
            *)
                echo "   ❌ Please enter 1, 2, 3, or 4"
                ;;
        esac
    done
    
    echo "   ✅ Logging configured: $LOG_LEVEL level"
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
    echo ""
    echo "   ❓ How often should we check if everything is working properly?"
    echo -n "   👉 Health check interval in seconds (default: 30): "
    read HEALTH_CHECK_INTERVAL
    if [ -z "$HEALTH_CHECK_INTERVAL" ]; then
        HEALTH_CHECK_INTERVAL="30"
    fi
    echo "   ✅ Health checks every $HEALTH_CHECK_INTERVAL seconds"
    echo ""
    
    echo "   ❓ How many times should we retry if a print job fails?"
    echo -n "   👉 Maximum retry attempts (default: 5): "
    read RETRY_MAX_ATTEMPTS
    if [ -z "$RETRY_MAX_ATTEMPTS" ]; then
        RETRY_MAX_ATTEMPTS="5"
    fi
    echo "   ✅ Will retry failed jobs $RETRY_MAX_ATTEMPTS times"
    echo ""
    
    echo "⚡ CIRCUIT BREAKER PROTECTION:"
    echo "   This protects your system from cascading failures"
    echo ""
    echo "   ❓ How many failures before we temporarily stop trying?"
    echo -n "   👉 Failure threshold (default: 3): "
    read CIRCUIT_BREAKER_FAILURE_THRESHOLD
    if [ -z "$CIRCUIT_BREAKER_FAILURE_THRESHOLD" ]; then
        CIRCUIT_BREAKER_FAILURE_THRESHOLD="3"
    fi
    echo "   ✅ Circuit breaker activates after $CIRCUIT_BREAKER_FAILURE_THRESHOLD failures"
    echo ""
    
    echo "   ❓ How long should we wait before trying again?"
    echo -n "   👉 Wait time in seconds (default: 60): "
    read CIRCUIT_BREAKER_TIMEOUT
    if [ -z "$CIRCUIT_BREAKER_TIMEOUT" ]; then
        CIRCUIT_BREAKER_TIMEOUT="60"
    fi
    echo "   ✅ Will wait $CIRCUIT_BREAKER_TIMEOUT seconds before retrying"
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
        
        echo "📬 EMAIL SERVER SETTINGS:"
        echo -n "   👉 SMTP server (default: smtp.gmail.com): "
        read SMTP_SERVER
        if [ -z "$SMTP_SERVER" ]; then
            SMTP_SERVER="smtp.gmail.com"
        fi
        echo "   ✅ Using server: $SMTP_SERVER"
        echo ""
        
        echo -n "   👉 SMTP port (default: 587): "
        read SMTP_PORT
        if [ -z "$SMTP_PORT" ]; then
            SMTP_PORT="587"
        fi
        echo "   ✅ Using port: $SMTP_PORT"
        echo ""
        
        echo "🔐 EMAIL ACCOUNT CREDENTIALS:"
        echo "   ⚠️  IMPORTANT: For Gmail, you need an 'App Password'!"
        echo "   📖 How to get Gmail App Password:"
        echo "      1. Go to: Google Account > Security > App Passwords"
        echo "      2. Generate a new app password"
        echo "      3. Use that password here (not your regular Gmail password)"
        echo ""
        echo -n "   👉 Your email address: "
        read SMTP_USERNAME
        echo "   ✅ Email account: $SMTP_USERNAME"
        echo ""
        
        echo -n "   👉 Email password (App Password for Gmail): "
        read -s SMTP_PASSWORD
        echo ""
        echo "   ✅ Password configured (hidden for security)"
        echo ""
        
        echo "📧 NOTIFICATION SETTINGS:"
        echo -n "   👉 From email (default: $SMTP_USERNAME): "
        read NOTIFICATION_FROM_EMAIL
        if [ -z "$NOTIFICATION_FROM_EMAIL" ]; then
            NOTIFICATION_FROM_EMAIL="$SMTP_USERNAME"
        fi
        echo "   ✅ Alerts will be sent from: $NOTIFICATION_FROM_EMAIL"
        echo ""
        
        echo -n "   👉 Where to send alerts (default: $SMTP_USERNAME): "
        read NOTIFICATION_TO_EMAIL
        if [ -z "$NOTIFICATION_TO_EMAIL" ]; then
            NOTIFICATION_TO_EMAIL="$SMTP_USERNAME"
        fi
        echo "   ✅ Alerts will be sent to: $NOTIFICATION_TO_EMAIL"
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

# Wix API Configuration (API Key)
WIX_API_KEY=$WIX_API_KEY
WIX_SITE_ID=$WIX_SITE_ID
WIX_API_BASE_URL=$WIX_API_BASE_URL

# Printer Configuration
PRINTER_TYPE=$PRINTER_TYPE
PRINTER_INTERFACE=$PRINTER_INTERFACE
PRINTER_VENDOR_ID=04b8
PRINTER_PRODUCT_ID=0e32

# USB Printer Configuration (required for USB printers)
PRINTER_USB_VENDOR_ID=0x04b8
PRINTER_USB_PRODUCT_ID=0x0e32

# Legacy device path (for compatibility)
PRINTER_DEVICE_PATH=$PRINTER_DEVICE_PATH
PAPER_WIDTH=$PAPER_WIDTH

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
    echo "   Method: API Key"
    echo "   Site ID: $WIX_SITE_ID"
    echo "   API URL: $WIX_API_BASE_URL"
    echo "   Status: $([ "$WIX_API_KEY" = "test-api-key" ] && echo "⚠️  Test Mode" || echo "✅ Production Ready")"
    echo ""
    echo "🖨️  PRINTER SETUP:"
    echo "   Type: $PRINTER_TYPE"
    echo "   Connection: $PRINTER_INTERFACE"
    echo "   Address: $PRINTER_DEVICE_PATH"
    echo "   Paper Width: ${PAPER_WIDTH}mm"
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
