#!/bin/bash

# 🚀 Wix Printer Service - One-Command Setup
# Version: 1.0
# Date: 2025-09-21

echo ""
echo "🍓 WIX PRINTER SERVICE - SETUP"
echo "=============================="
echo ""

# Make all scripts executable first
echo "🔧 Making scripts executable..."
chmod +x scripts/*.sh

echo "✅ Scripts are now executable!"
echo ""

echo "📋 SETUP OPTIONS:"
echo "1️⃣ Complete Setup (Raspberry Pi + Public URL)"
echo "2️⃣ Public URL Setup Only"
echo "3️⃣ Raspberry Pi Setup Only"
echo "4️⃣ Update Configuration (Auto-Check Settings)"
echo "5️⃣ Printer Setup & Configuration 🖨️"
echo ""

while true; do
    read -p "👉 Choose setup option (1-5): " setup_choice
    case $setup_choice in
        1)
            echo "🚀 Starting complete setup..."
            echo ""
            exec ./scripts/raspberry-pi-quickstart.sh
            ;;
        2)
            echo "🌐 Starting public URL setup..."
            echo ""
            exec ./scripts/setup-public-url-menu.sh
            ;;
        3)
            echo "🍓 Starting Raspberry Pi setup..."
            echo ""
            # Run quickstart but skip public URL setup
            SKIP_PUBLIC_URL=1 exec ./scripts/raspberry-pi-quickstart.sh
            ;;
        4)
            echo "⚙️ Starting configuration update..."
            echo ""
            exec ./scripts/update-config.sh
            ;;
        5)
            echo "🖨️ Starting printer setup..."
            echo ""
            exec ./scripts/setup-printer.sh
            ;;
        *)
            echo "❌ Please enter 1, 2, 3, 4, or 5"
            ;;
    esac
done
