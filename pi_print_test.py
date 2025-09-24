#!/usr/bin/env python3
"""
Raspberry Pi Order Printing Test Script
Tests the complete order printing flow directly on Pi with real orders
"""

import sys
import os
from datetime import datetime
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress verbose logging for cleaner output
logging.getLogger('wix_printer_service.order_filter').setLevel(logging.ERROR)

def test_order_printing():
    """Test order printing functionality on Raspberry Pi."""

    try:
        from wix_printer_service.wix_client import WixClient
        from wix_printer_service.printer_manager import PrinterManager

        print("🍓 RASPBERRY PI - ORDER PRINTING TEST")
        print("=" * 50)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Initialize clients
        print("🔧 Initializing Wix API Client...")
        wix_client = WixClient()
        print("✅ Wix Client initialized")

        print("🖨️  Initializing Printer Manager...")
        printer_manager = PrinterManager()
        print("✅ Printer Manager initialized")

        # Test API connection
        if not wix_client.test_connection():
            print("❌ API connection failed")
            return False
        print("✅ API connection successful")

        # Get recent orders for selection
        print("\n📋 Fetching available orders...")
        orders = wix_client.get_recent_orders(minutes_ago=72 * 60)  # 3 days

        if not orders:
            print("❌ No orders found for testing")
            return False

        print(f"✅ Found {len(orders)} orders for testing")
        print()

        # Display available orders for selection
        print("📝 Available Orders for Printing:")
        print("-" * 40)
        for i, order in enumerate(orders[:5], 1):  # Show first 5 orders
            order_id = order.get('id', 'Unknown')
            created_date = order.get('createdDate', 'Unknown')
            total = order.get('priceSummary', {}).get('total', {}).get('amount', 'Unknown')

            # Get first item name for display
            line_items = order.get('lineItems', [])
            first_item = "No items"
            if line_items:
                first_item = line_items[0].get('productName', {}).get('original',
                                             line_items[0].get('name', 'Unknown Item'))
                if len(line_items) > 1:
                    first_item += f" (+{len(line_items)-1} more)"

            print(f"   {i}. Order {order_id[:8]}...")
            print(f"      Created: {created_date}")
            print(f"      Items: {first_item}")
            print(f"      Total: {total} CHF")
            print()

        # Test scenarios
        test_scenarios = [
            {
                'name': 'Most Recent Order (Automatic)',
                'order': orders[0],
                'description': 'Print the most recent order automatically'
            },
            {
                'name': 'Kitchen Receipt Format',
                'order': orders[0],
                'description': 'Print order in kitchen receipt format'
            },
            {
                'name': 'Full Customer Receipt',
                'order': orders[0],
                'description': 'Print complete customer receipt with all details'
            }
        ]

        results = {}

        for scenario in test_scenarios:
            print(f"🖨️  Testing: {scenario['name']}")
            print(f"   {scenario['description']}")

            try:
                order = scenario['order']
                order_id = order.get('id', 'Unknown')

                # Different print formats based on scenario
                if 'Kitchen' in scenario['name']:
                    # Kitchen format - items only
                    success = printer_manager.print_kitchen_order(order)
                elif 'Customer' in scenario['name']:
                    # Full customer receipt
                    success = printer_manager.print_customer_receipt(order)
                else:
                    # Default format
                    success = printer_manager.print_order(order)

                if success:
                    print(f"   ✅ SUCCESS - Order {order_id[:8]}... printed successfully")
                    results[scenario['name']] = True
                else:
                    print(f"   ❌ FAILED - Order {order_id[:8]}... printing failed")
                    results[scenario['name']] = False

            except Exception as e:
                print(f"   ❌ ERROR - {e}")
                results[scenario['name']] = False

            print()

            # Wait between prints to avoid overwhelming printer
            print("   ⏳ Waiting 3 seconds before next test...")
            import time
            time.sleep(3)

        # Summary report
        print("🎯 PRINTING TEST SUMMARY")
        print("=" * 30)

        passed_tests = sum(1 for success in results.values() if success)
        total_tests = len(results)

        print(f"Tests Passed: {passed_tests}/{total_tests}")
        print()

        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {test_name:<25} {status}")

        print()

        # Overall result
        if passed_tests == total_tests:
            print("🎉 ALL PRINTING TESTS PASSED!")
            print("✅ Printer is working correctly with Wix orders")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed.")
            print("   Check printer connection and configuration")

        # Technical info
        print()
        print("📋 Technical Details:")
        print(f"   • Printer Interface: {os.getenv('PRINTER_INTERFACE', 'usb')}")
        print(f"   • Service Running: Check with 'sudo systemctl status wix-printer.service'")
        print(f"   • Orders Available: {len(orders)} orders in last 3 days")

        return passed_tests == total_tests

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you're running this from the project root with venv activated")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function for Raspberry Pi printing."""
    print("🍓 Starting Raspberry Pi Order Printing Test...")
    print()

    # Load .env file explicitly
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        print(f"🔧 Loading environment from: {env_path}")
        load_dotenv(env_path)
        print("✅ .env file loaded successfully")
    else:
        print(f"⚠️  No .env file found at: {env_path}")
        print("   Checking for environment variables from shell...")

    # Check environment
    api_key = os.getenv('WIX_API_KEY')
    site_id = os.getenv('WIX_SITE_ID')
    printer_interface = os.getenv('PRINTER_INTERFACE', 'usb')

    if not api_key or not site_id:
        print("❌ Missing environment variables!")
        print(f"   WIX_API_KEY: {'Found' if api_key else 'Missing'}")
        print(f"   WIX_SITE_ID: {'Found' if site_id else 'Missing'}")
        return False

    print(f"✅ Environment variables found")
    print(f"   API Key: {api_key[:20]}...")
    print(f"   Site ID: {site_id}")
    print(f"   Printer: {printer_interface}")
    print()

    # Check printer connectivity
    print("🖨️  Checking printer connectivity...")
    if printer_interface == 'usb':
        # Check for USB printer
        import subprocess
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if '04b8' in result.stdout:  # Epson vendor ID
                print("✅ USB printer detected (Epson)")
            else:
                print("⚠️  No Epson USB printer detected")
                print("   Proceeding anyway - printer might still work")
        except:
            print("⚠️  Could not check USB devices")
    else:
        print(f"📡 Network printer configured: {os.getenv('PRINTER_IP', 'Unknown IP')}")

    print()

    # Run printing tests
    success = test_order_printing()

    print()
    print("🏁 Raspberry Pi Printing Test Completed!")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)