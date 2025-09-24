#!/bin/bash

# 🖨️ Printer Setup and Configuration Script
# Version: 1.0
# Supports: USB Thermal Printers (Epson TM-T88, Star TSP, etc.)

echo ""
echo "🖨️ PRINTER SETUP & CONFIGURATION"
echo "================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}⚠️  This script should not be run as root for initial setup${NC}"
   echo "   Will use sudo when needed for permissions."
   echo ""
fi

# Function to detect USB printers
detect_usb_printer() {
    echo "🔍 Detecting USB printers..."
    echo ""

    # Reset global variables
    DETECTED_VENDOR=""
    DETECTED_PRODUCT=""
    DETECTED_NAME=""

    # Check for USB printer devices (expand search to include all printer classes)
    USB_PRINTERS=$(lsusb | grep -i -E "epson|star|bixolon|citizen|printer|canon|hp|brother")

    if [ ! -z "$USB_PRINTERS" ]; then
        echo -e "${GREEN}✅ USB printer(s) detected:${NC}"
        echo "$USB_PRINTERS"
        echo ""

        # Get the first detected printer
        USB_INFO=$(echo "$USB_PRINTERS" | head -1)
        VENDOR_ID=$(echo $USB_INFO | sed -n 's/.*ID \([0-9a-f]*\):.*/\1/p')
        PRODUCT_ID=$(echo $USB_INFO | sed -n 's/.*ID [0-9a-f]*:\([0-9a-f]*\).*/\1/p')

        # Store detected values globally
        DETECTED_VENDOR="0x${VENDOR_ID}"
        DETECTED_PRODUCT="0x${PRODUCT_ID}"
        DETECTED_NAME=$(echo $USB_INFO | cut -d' ' -f7-)

        echo "  Auto-detected printer:"
        echo "    Name:       $DETECTED_NAME"
        echo "    Vendor ID:  $DETECTED_VENDOR"
        echo "    Product ID: $DETECTED_PRODUCT"
        return 0
    else
        echo -e "${YELLOW}⚠️  No obvious printer devices detected via lsusb${NC}"
        echo ""
        echo "  Checking USB device class 7 (printers)..."

        # Alternative: Check for USB device class 7 (printer class)
        USB_CLASS7=$(lsusb -v 2>/dev/null | grep -B5 -A5 "bInterfaceClass.*7 Printer" | grep "idVendor\|idProduct" | head -2)

        if [ ! -z "$USB_CLASS7" ]; then
            VENDOR_LINE=$(echo "$USB_CLASS7" | grep "idVendor" | head -1)
            PRODUCT_LINE=$(echo "$USB_CLASS7" | grep "idProduct" | head -1)

            if [ ! -z "$VENDOR_LINE" ] && [ ! -z "$PRODUCT_LINE" ]; then
                VENDOR_ID=$(echo $VENDOR_LINE | sed -n 's/.*idVendor.*0x\([0-9a-f]*\).*/\1/p')
                PRODUCT_ID=$(echo $PRODUCT_LINE | sed -n 's/.*idProduct.*0x\([0-9a-f]*\).*/\1/p')

                DETECTED_VENDOR="0x${VENDOR_ID}"
                DETECTED_PRODUCT="0x${PRODUCT_ID}"
                DETECTED_NAME="USB Printer Class Device"

                echo -e "${GREEN}✅ Found printer class USB device:${NC}"
                echo "    Vendor ID:  $DETECTED_VENDOR"
                echo "    Product ID: $DETECTED_PRODUCT"
                return 0
            fi
        fi

        echo -e "${RED}❌ No USB printer detected${NC}"
        echo ""
        echo "  Please check:"
        echo "  1. Printer is powered on"
        echo "  2. USB cable is connected properly"
        echo "  3. Printer is not in error state"
        echo "  4. USB cable is not faulty"
        echo ""
        echo "  You can still configure manually if you know the printer IDs"
        return 1
    fi
}

# Function to setup USB permissions
setup_usb_permissions() {
    echo "🔧 Setting up USB permissions..."
    echo ""

    # Add user to required groups
    CURRENT_USER=${SUDO_USER:-$USER}
    echo "  Adding user '$CURRENT_USER' to printer groups..."

    sudo usermod -a -G dialout,lp $CURRENT_USER 2>/dev/null

    # Create udev rule for USB printers
    echo "  Creating udev rules for USB printers..."

    # Create rule file
    UDEV_RULE="/etc/udev/rules.d/99-usb-printer.rules"

    # Common printer vendor IDs
    cat << EOF | sudo tee $UDEV_RULE > /dev/null
# USB Printer Permissions
# Epson printers
SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", MODE="0666", GROUP="lp"
# Star Micronics printers
SUBSYSTEM=="usb", ATTRS{idVendor}=="0519", MODE="0666", GROUP="lp"
# Bixolon printers
SUBSYSTEM=="usb", ATTRS{idVendor}=="1504", MODE="0666", GROUP="lp"
# Citizen printers
SUBSYSTEM=="usb", ATTRS{idVendor}=="1d90", MODE="0666", GROUP="lp"
# Generic USB printer class
SUBSYSTEM=="usb", ATTR{bInterfaceClass}=="07", ATTR{bInterfaceSubClass}=="01", MODE="0666", GROUP="lp"
EOF

    # Reload udev rules
    echo "  Reloading udev rules..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger

    echo -e "${GREEN}✅ USB permissions configured${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Note: You may need to logout and login again for group changes to take effect${NC}"
}

# Function to test printer connection
test_printer_connection() {
    echo "🧪 Testing printer connection..."
    echo ""

    # Check if python escpos is installed (try both venv and system)
    PYTHON_CMD=""
    if [ -d "/opt/wix-printer-service/venv" ]; then
        if /opt/wix-printer-service/venv/bin/python -c "import escpos" 2>/dev/null; then
            PYTHON_CMD="/opt/wix-printer-service/venv/bin/python"
            echo "  Testing with python-escpos (venv)..."
        fi
    fi

    # Fallback to system python
    if [ -z "$PYTHON_CMD" ] && python3 -c "import escpos" 2>/dev/null; then
        PYTHON_CMD="python3"
        echo "  Testing with python-escpos (system)..."
    fi

    if [ ! -z "$PYTHON_CMD" ]; then
        # Create test script
        cat << 'EOF' > /tmp/test_printer.py
#!/usr/bin/env python3
import sys
import os
from dotenv import load_dotenv

try:
    from escpos.printer import Usb

    # Load environment variables
    load_dotenv("/opt/wix-printer-service/.env")

    # Get printer IDs from environment
    env_vendor = os.getenv("PRINTER_USB_VENDOR_ID")
    env_product = os.getenv("PRINTER_USB_PRODUCT_ID")

    printers = []

    # Add environment configured printer first
    if env_vendor and env_product:
        try:
            vendor_id = int(env_vendor, 16) if env_vendor.startswith('0x') else int(env_vendor)
            product_id = int(env_product, 16) if env_product.startswith('0x') else int(env_product)
            printers.append((vendor_id, product_id, f"Configured Printer ({env_vendor}:{env_product})"))
        except ValueError:
            pass

    # Add common printer vendor/product IDs as fallback
    printers.extend([
        (0x04b8, 0x0202, "Epson TM-m30III"),
        (0x04b8, 0x0e15, "Epson TM-T88V"),
        (0x04b8, 0x0e03, "Epson TM-T20"),
        (0x0519, 0x0001, "Star Micronics"),
        (0x1504, 0x0006, "Bixolon"),
    ])

    found = False
    for vendor, product, name in printers:
        try:
            p = Usb(vendor, product)
            print(f"✅ Connected to {name}")
            p.text("=== Printer Test ===\n")
            p.text("Connection successful!\n")
            p.text(f"Model: {name}\n")
            p.text(f"Vendor: 0x{vendor:04x}\n")
            p.text(f"Product: 0x{product:04x}\n")
            p.text("====================\n\n")
            p.cut()
            p.close()
            found = True
            break
        except Exception as e:
            print(f"Failed to connect to {name}: {e}")
            continue

    if not found:
        print("❌ Could not connect to any printer")
        print("   Check USB permissions and cable")
        print("   Current ENV config:")
        print(f"     PRINTER_USB_VENDOR_ID={env_vendor}")
        print(f"     PRINTER_USB_PRODUCT_ID={env_product}")
        sys.exit(1)

    sys.exit(0)

except ImportError:
    print("❌ python-escpos not installed")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

        # Run test with the correct Python command
        if $PYTHON_CMD /tmp/test_printer.py; then
            echo -e "${GREEN}✅ Printer connection test successful!${NC}"
            echo "   A test receipt should have been printed."
            return 0
        else
            echo -e "${RED}❌ Printer connection test failed${NC}"
            echo "   Try running the test with sudo if USB permissions are still needed:"
            echo "   sudo $PYTHON_CMD /tmp/test_printer.py"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  python-escpos not installed, skipping test${NC}"
        echo "   Run option 5 (Install Dependencies) first"
        return 2
    fi
}

# Function to configure printer in .env
configure_printer_env() {
    echo "📝 Configuring printer settings..."
    echo ""

    ENV_FILE="/opt/wix-printer-service/.env"

    # Ensure .env exists
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}⚠️  .env file not found, creating from template...${NC}"
        if [ -f "/opt/wix-printer-service/.env.template" ]; then
            cp /opt/wix-printer-service/.env.template $ENV_FILE
        else
            touch $ENV_FILE
        fi
    fi

    # Get current values or set defaults
    CURRENT_VENDOR=$(grep "^PRINTER_USB_VENDOR_ID=" $ENV_FILE 2>/dev/null | cut -d'=' -f2 || echo "0x04b8")
    CURRENT_PRODUCT=$(grep "^PRINTER_USB_PRODUCT_ID=" $ENV_FILE 2>/dev/null | cut -d'=' -f2 || echo "0x0202")
    CURRENT_INTERFACE=$(grep "^PRINTER_INTERFACE=" $ENV_FILE 2>/dev/null | cut -d'=' -f2 || echo "usb")

    # Ask for printer configuration
    echo "Current printer configuration:"
    echo "  Vendor ID:  $CURRENT_VENDOR"
    echo "  Product ID: $CURRENT_PRODUCT"
    echo "  Interface:  $CURRENT_INTERFACE"
    echo ""

    read -p "Do you want to update printer configuration? (y/n) [n]: " update_config

    if [[ "$update_config" == "y" ]]; then
        # If printer was auto-detected, suggest those values
        if [ ! -z "$DETECTED_VENDOR" ] && [ ! -z "$DETECTED_PRODUCT" ]; then
            echo ""
            echo "Auto-detected printer:"
            echo "  Name:    $DETECTED_NAME"
            echo "  Vendor:  $DETECTED_VENDOR"
            echo "  Product: $DETECTED_PRODUCT"
            read -p "Use auto-detected values? (y/n) [y]: " use_detected

            if [[ "$use_detected" != "n" ]]; then
                PRINTER_VENDOR="$DETECTED_VENDOR"
                PRINTER_PRODUCT="$DETECTED_PRODUCT"
                echo "  Using auto-detected values: $DETECTED_VENDOR:$DETECTED_PRODUCT"
            else
                read -p "Enter Vendor ID (e.g., 0x04b8): " PRINTER_VENDOR
                read -p "Enter Product ID (e.g., 0x0202): " PRINTER_PRODUCT
            fi
        else
            echo ""
            echo "No printer auto-detected. Manual configuration required."
            read -p "Enter Vendor ID (e.g., 0x04b8) [$CURRENT_VENDOR]: " PRINTER_VENDOR
            PRINTER_VENDOR=${PRINTER_VENDOR:-$CURRENT_VENDOR}

            read -p "Enter Product ID (e.g., 0x0202) [$CURRENT_PRODUCT]: " PRINTER_PRODUCT
            PRINTER_PRODUCT=${PRINTER_PRODUCT:-$CURRENT_PRODUCT}
        fi

        # Update .env file
        echo ""
        echo "  Updating .env file..."

        # Use the same method as other scripts for safe .env editing
        sudo touch $ENV_FILE
        sudo chown wix-printer:wix-printer $ENV_FILE 2>/dev/null || sudo chown $(whoami):$(whoami) $ENV_FILE

        # Update each value using sed (like other scripts do)
        if grep -q "^PRINTER_USB_VENDOR_ID=" $ENV_FILE; then
            sudo sed -i "s|^PRINTER_USB_VENDOR_ID=.*|PRINTER_USB_VENDOR_ID=${PRINTER_VENDOR}|" $ENV_FILE
        else
            echo "PRINTER_USB_VENDOR_ID=${PRINTER_VENDOR}" | sudo tee -a $ENV_FILE > /dev/null
        fi

        if grep -q "^PRINTER_USB_PRODUCT_ID=" $ENV_FILE; then
            sudo sed -i "s|^PRINTER_USB_PRODUCT_ID=.*|PRINTER_USB_PRODUCT_ID=${PRINTER_PRODUCT}|" $ENV_FILE
        else
            echo "PRINTER_USB_PRODUCT_ID=${PRINTER_PRODUCT}" | sudo tee -a $ENV_FILE > /dev/null
        fi

        if grep -q "^PRINTER_INTERFACE=" $ENV_FILE; then
            sudo sed -i "s|^PRINTER_INTERFACE=.*|PRINTER_INTERFACE=usb|" $ENV_FILE
        else
            echo "PRINTER_INTERFACE=usb" | sudo tee -a $ENV_FILE > /dev/null
        fi
        echo -e "${GREEN}✅ Printer configuration updated${NC}"
    fi
}

# Function to install printer dependencies
install_dependencies() {
    echo "📦 Installing printer dependencies..."
    echo ""

    # Check if venv exists and is writable
    if [ -d "/opt/wix-printer-service/venv" ]; then
        echo "  Installing python-escpos in virtual environment..."

        # Check if we need sudo for venv
        if [ -w "/opt/wix-printer-service/venv/lib" ]; then
            /opt/wix-printer-service/venv/bin/pip install python-escpos pyusb pyserial
        else
            echo "  Using sudo for venv installation (permissions required)..."
            sudo /opt/wix-printer-service/venv/bin/pip install python-escpos pyusb pyserial
        fi

        # Verify installation
        if /opt/wix-printer-service/venv/bin/python -c "import escpos" 2>/dev/null; then
            echo -e "${GREEN}  ✓ python-escpos successfully installed${NC}"
        else
            echo -e "${RED}  ✗ Installation failed, trying alternative method...${NC}"
            sudo /opt/wix-printer-service/venv/bin/pip install --force-reinstall python-escpos pyusb pyserial
        fi
    else
        echo "  Installing system-wide packages..."
        sudo apt-get update
        sudo apt-get install -y python3-usb python3-serial python3-pil
        pip3 install --user python-escpos pyusb pyserial
    fi

    echo -e "${GREEN}✅ Dependencies installed${NC}"
}

# Function to restart printer service
restart_printer_service() {
    echo "🔄 Restarting printer service..."
    echo ""

    if systemctl is-active --quiet wix-printer.service; then
        sudo systemctl restart wix-printer.service
        echo -e "${GREEN}✅ Printer service restarted${NC}"

        # Check status
        echo ""
        echo "Service status:"
        sudo systemctl status wix-printer.service --no-pager | head -10
    else
        echo -e "${YELLOW}⚠️  Printer service not running${NC}"
        read -p "Start printer service now? (y/n) [y]: " start_service

        if [[ "$start_service" != "n" ]]; then
            sudo systemctl start wix-printer.service
            sudo systemctl enable wix-printer.service
            echo -e "${GREEN}✅ Printer service started${NC}"
        fi
    fi
}

# Main setup menu
show_menu() {
    echo "📋 PRINTER SETUP OPTIONS:"
    echo ""
    echo "1️⃣  Quick Setup (Auto-detect & Configure)"
    echo "2️⃣  Manual Configuration"
    echo "3️⃣  Test Printer Connection"
    echo "4️⃣  Fix USB Permissions"
    echo "5️⃣  Install Dependencies"
    echo "6️⃣  Restart Printer Service"
    echo "0️⃣  Exit"
    echo ""
}

# Quick setup function
quick_setup() {
    echo "🚀 Starting Quick Printer Setup..."
    echo ""

    # Detect printer
    if detect_usb_printer; then
        echo ""
        echo "🔧 Auto-configuring detected printer:"
        echo "  Name:    $DETECTED_NAME"
        echo "  Vendor:  $DETECTED_VENDOR"
        echo "  Product: $DETECTED_PRODUCT"

        # Setup permissions
        setup_usb_permissions

        # Install dependencies
        install_dependencies

        # Auto-configure with detected values
        auto_configure_printer

        # Test connection
        test_printer_connection

        # Restart service
        restart_printer_service

        echo ""
        echo -e "${GREEN}✅ Quick printer setup completed!${NC}"
        echo -e "${GREEN}   Configured: $DETECTED_NAME ($DETECTED_VENDOR:$DETECTED_PRODUCT)${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠️  No printer auto-detected${NC}"
        echo "   You can still configure manually using option 2"
        echo ""
        read -p "Continue with manual configuration? (y/n) [n]: " manual_config
        if [[ "$manual_config" == "y" ]]; then
            configure_printer_env
        fi
    fi
}

# Function to auto-configure printer with detected values
auto_configure_printer() {
    echo "📝 Auto-configuring printer settings..."
    echo ""

    ENV_FILE="/opt/wix-printer-service/.env"

    # Ensure .env exists
    if [ ! -f "$ENV_FILE" ]; then
        echo "  Creating .env file from template..."
        if [ -f "/opt/wix-printer-service/.env.template" ]; then
            cp /opt/wix-printer-service/.env.template $ENV_FILE
        else
            touch $ENV_FILE
        fi
    fi

    echo "  Updating .env with auto-detected values..."

    # Use the same safe method as other scripts
    sudo touch $ENV_FILE
    sudo chown wix-printer:wix-printer $ENV_FILE 2>/dev/null || sudo chown $(whoami):$(whoami) $ENV_FILE

    # Update each value safely using sed
    if grep -q "^PRINTER_USB_VENDOR_ID=" $ENV_FILE; then
        sudo sed -i "s|^PRINTER_USB_VENDOR_ID=.*|PRINTER_USB_VENDOR_ID=$DETECTED_VENDOR|" $ENV_FILE
    else
        echo "PRINTER_USB_VENDOR_ID=$DETECTED_VENDOR" | sudo tee -a $ENV_FILE > /dev/null
    fi

    if grep -q "^PRINTER_USB_PRODUCT_ID=" $ENV_FILE; then
        sudo sed -i "s|^PRINTER_USB_PRODUCT_ID=.*|PRINTER_USB_PRODUCT_ID=$DETECTED_PRODUCT|" $ENV_FILE
    else
        echo "PRINTER_USB_PRODUCT_ID=$DETECTED_PRODUCT" | sudo tee -a $ENV_FILE > /dev/null
    fi

    if grep -q "^PRINTER_INTERFACE=" $ENV_FILE; then
        sudo sed -i "s|^PRINTER_INTERFACE=.*|PRINTER_INTERFACE=usb|" $ENV_FILE
    else
        echo "PRINTER_INTERFACE=usb" | sudo tee -a $ENV_FILE > /dev/null
    fi

    # Add comment if not present
    if ! grep -q "Auto-detected:" $ENV_FILE; then
        echo "# Printer Configuration (Auto-detected: $DETECTED_NAME)" | sudo tee -a $ENV_FILE > /dev/null
    fi
    echo -e "${GREEN}✅ Printer auto-configured: $DETECTED_VENDOR:$DETECTED_PRODUCT${NC}"
}

# Main execution
main() {
    while true; do
        show_menu
        read -p "👉 Choose option (0-6): " choice

        case $choice in
            1)
                quick_setup
                ;;
            2)
                configure_printer_env
                ;;
            3)
                test_printer_connection
                ;;
            4)
                setup_usb_permissions
                ;;
            5)
                install_dependencies
                ;;
            6)
                restart_printer_service
                ;;
            0)
                echo "👋 Exiting printer setup"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                ;;
        esac

        echo ""
        read -p "Press Enter to continue..."
        echo ""
    done
}

# Run main function
main