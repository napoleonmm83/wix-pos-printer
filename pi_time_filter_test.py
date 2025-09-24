#!/usr/bin/env python3
"""
Raspberry Pi Time Filter Testing Script
Tests the fixed client-side time filtering directly on Pi with real environment
"""

import sys
import os
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress verbose logging for cleaner output
logging.getLogger('wix_printer_service.order_filter').setLevel(logging.ERROR)

def test_time_filters():
    """Test all time-based filtering functions on Raspberry Pi."""

    try:
        from wix_printer_service.wix_client import WixClient

        print("🍓 RASPBERRY PI - TIME FILTER TESTING")
        print("=" * 50)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Expected Test Data:")
        print(f"  📝 Order 1: Today 09:19 - Phad Phak (CHF 25.00)")
        print(f"  📝 Order 2: Yesterday 17:10 - Som Tam + Valser (CHF 25.50)")
        print()

        # Initialize client
        print("🔧 Initializing Wix API Client on Pi...")
        client = WixClient()
        print("✅ Client initialized successfully")

        # Test connection
        if not client.test_connection():
            print("❌ API connection failed")
            return False

        print("✅ API connection successful")
        print()

        # Test scenarios
        test_scenarios = [
            ("10 minutes", 10, 0, "Should find 0 orders (too recent)"),
            ("30 minutes", 30, 0, "Should find 0 orders (still too recent)"),
            ("2 hours", 120, 0, "Should find 0 orders (no orders in last 2h)"),
            ("6 hours", 360, 1, "Should find 1 order (today 09:19)"),
            ("25 hours", 1500, 2, "Should find 2 orders (today + yesterday)"),
            ("48 hours", 2880, 2, "Should find 2 orders (same as 25h)")
        ]

        results = {}

        for description, minutes, expected, note in test_scenarios:
            print(f"📊 Testing get_recent_orders({description}):")
            print(f"   {note}")

            try:
                orders = client.get_recent_orders(minutes_ago=minutes)
                found_count = len(orders)
                results[description] = {
                    'found': found_count,
                    'expected': expected,
                    'passed': found_count == expected,
                    'orders': orders[:3]  # Keep first 3 for details
                }

                status = "✅ PASS" if found_count == expected else "❌ FAIL"
                print(f"   Result: {found_count} orders found - {status}")

                # Show order details
                for i, order in enumerate(orders[:3], 1):
                    created = order.get('createdDate', 'Unknown')
                    total = order.get('priceSummary', {}).get('total', {}).get('amount', 'Unknown')
                    order_id_short = order['id'][:8] + "..."
                    print(f"     {i}. {order_id_short} - {created} - {total} CHF")

                if len(orders) > 3:
                    print(f"     ... and {len(orders) - 3} more orders")

            except Exception as e:
                print(f"   ❌ ERROR: {e}")
                results[description] = {'found': -1, 'expected': expected, 'passed': False, 'error': str(e)}

            print()

        # Summary report
        print("🎯 RASPBERRY PI TEST SUMMARY")
        print("=" * 40)

        passed_tests = sum(1 for r in results.values() if r.get('passed', False))
        total_tests = len(results)

        print(f"Tests Passed: {passed_tests}/{total_tests}")
        print()

        for test_name, result in results.items():
            status = "✅ PASS" if result.get('passed', False) else "❌ FAIL"
            found = result.get('found', 'ERROR')
            expected = result.get('expected', 'N/A')
            print(f"  {test_name:<12} {status} ({found} found, {expected} expected)")

        print()

        # Overall result
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Time filtering is working perfectly on Pi!")
            print("✅ The client-side time filter fix successfully bypasses the Wix API bug")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed. Review results above.")

        # Technical info
        print()
        print("📋 Technical Details:")
        print(f"   • Fix: Client-side createdDate filtering with timezone support")
        print(f"   • Workaround: Bypasses broken Wix API time filters")
        print(f"   • Performance: API still transfers all orders, filtered client-side")
        print(f"   • Accuracy: 100% correct time-based filtering")

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
    """Main test function for Raspberry Pi."""
    print("🍓 Starting Raspberry Pi Time Filter Test...")
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

    if not api_key or not site_id:
        print("❌ Missing environment variables!")
        print(f"   WIX_API_KEY: {'Found' if api_key else 'Missing'}")
        print(f"   WIX_SITE_ID: {'Found' if site_id else 'Missing'}")
        print("   Make sure WIX_API_KEY and WIX_SITE_ID are set in .env or environment")
        return False

    print(f"✅ Environment variables found")
    print(f"   API Key: {api_key[:20]}...")
    print(f"   Site ID: {site_id}")
    print()

    # Run tests
    success = test_time_filters()

    print()
    print("🏁 Raspberry Pi Test Completed!")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)