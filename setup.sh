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

# Run the main quickstart script
echo "🚀 Starting main setup..."
echo ""

exec ./scripts/raspberry-pi-quickstart.sh
