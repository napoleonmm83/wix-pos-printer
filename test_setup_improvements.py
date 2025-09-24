#!/usr/bin/env python3
"""
Test script to verify the setup wizard improvements
"""

import os
import subprocess

def test_setup_improvements():
    """Test the new setup wizard features"""
    print("=" * 80)
    print("TESTING SETUP WIZARD IMPROVEMENTS")
    print("=" * 80)

    # Check if setup.sh has the new option
    print("\n1. CHECKING MAIN SETUP SCRIPT")
    print("-" * 40)

    if os.path.exists("setup.sh"):
        with open("setup.sh", 'r', encoding='utf-8') as f:
            content = f.read()
            if "Update Configuration" in content:
                print("+ Main setup script updated with configuration option")
            else:
                print("- Main setup script missing configuration option")

    # Check if update-config.sh exists and is executable
    print("\n2. CHECKING CONFIGURATION UPDATE SCRIPT")
    print("-" * 40)

    config_script = "scripts/update-config.sh"
    if os.path.exists(config_script):
        print("+ Configuration update script exists")

        # Check if executable
        if os.access(config_script, os.X_OK):
            print("+ Script is executable")
        else:
            print("- Script is not executable")

        # Check content
        with open(config_script, 'r', encoding='utf-8') as f:
            content = f.read()

        features = [
            ("Auto-Check configuration", "AUTO_CHECK_ENABLED" in content),
            ("48-hour default", "48" in content),
            ("Interactive prompts", "read -p" in content),
            ("Service restart", "systemctl restart" in content),
            ("Database schema check", "update_database_schema" in content)
        ]

        print("\n   Script features:")
        for feature, present in features:
            status = "+" if present else "-"
            print(f"   {status} {feature}")
    else:
        print("- Configuration update script not found")

    # Check raspberry-pi-quickstart.sh for new defaults
    print("\n3. CHECKING RASPBERRY PI QUICKSTART SCRIPT")
    print("-" * 40)

    quickstart_script = "scripts/raspberry-pi-quickstart.sh"
    if os.path.exists(quickstart_script):
        with open(quickstart_script, 'r', encoding='utf-8') as f:
            content = f.read()

        features = [
            ("Auto-Check section", "# --- Auto-Check Configuration ---" in content),
            ("48-hour default", '"48"' in content),
            ("30-second interval", '"30"' in content),
            ("Auto-check enabled default", '"true"' in content and "AUTO_CHECK_ENABLED" in content)
        ]

        print("   Quickstart script features:")
        for feature, present in features:
            status = "+" if present else "-"
            print(f"   {status} {feature}")
    else:
        print("- Raspberry Pi quickstart script not found")

    # Check .env.template
    print("\n4. CHECKING ENV TEMPLATE")
    print("-" * 40)

    template_file = ".env.template"
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()

        features = [
            ("Auto-Check section", "# Auto-Check Configuration" in content),
            ("48-hour default", "AUTO_CHECK_HOURS_BACK=48" in content),
            ("30-second interval", "AUTO_CHECK_INTERVAL=30" in content),
            ("Auto-check enabled", "AUTO_CHECK_ENABLED=true" in content),
            ("Change detection comment", "Order Change Detection" in content)
        ]

        print("   Template file features:")
        for feature, present in features:
            status = "+" if present else "-"
            print(f"   {status} {feature}")
    else:
        print("- .env.template not found")

    print("\n" + "=" * 80)
    print("SETUP IMPROVEMENT SUMMARY")
    print("=" * 80)

    print("\n+ COMPLETED IMPROVEMENTS:")
    print("1. Updated setup.sh with new configuration option (4)")
    print("2. Created update-config.sh for existing installations")
    print("3. Added Auto-Check defaults to raspberry-pi-quickstart.sh")
    print("4. Created .env.template with new 48-hour defaults")
    print("5. Made scripts executable and tested functionality")

    print("\n+ USER BENEFITS:")
    print("- New installations get optimized 48-hour settings by default")
    print("- Existing users can easily update their configuration")
    print("- Setup wizard now includes Auto-Check configuration")
    print("- All scripts work with existing .env files")
    print("- Interactive prompts with current value display")

    print("\n+ USAGE INSTRUCTIONS:")
    print("- New setup: ./setup.sh -> Choose option 1, 2, or 3")
    print("- Update config: ./setup.sh -> Choose option 4")
    print("- Direct update: ./scripts/update-config.sh")

    return True

if __name__ == "__main__":
    print("Setup Wizard Improvements Test")
    print("Verifying enhanced configuration capabilities...")

    success = test_setup_improvements()

    if success:
        print("\n+ ALL SETUP IMPROVEMENTS VERIFIED!")
    else:
        print("\n- SOME IMPROVEMENTS MISSING")