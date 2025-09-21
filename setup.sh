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
echo ""

while true; do
    read -p "👉 Choose setup option (1-3): " setup_choice
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
        *)
            echo "❌ Please enter 1, 2, or 3"
            ;;
    esac
done
