#!/bin/bash

# 🔧 Make All Scripts Executable
# Wix Printer Service - Setup Helper
# Version: 1.0
# Date: 2025-09-21

echo "🔧 Making all scripts executable..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make all .sh files executable
chmod +x "$SCRIPT_DIR"/*.sh

echo "✅ All scripts are now executable!"
echo ""
echo "📋 Available scripts:"
ls -la "$SCRIPT_DIR"/*.sh | awk '{print "   " $9 " (" $1 ")"}'
echo ""
echo "🚀 You can now run any script directly, for example:"
echo "   ./scripts/raspberry-pi-quickstart.sh"
echo "   ./scripts/setup-cloudflare-tunnel-simple.sh"
echo ""
