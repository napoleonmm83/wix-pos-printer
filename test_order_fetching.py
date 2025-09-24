#!/usr/bin/env python3
"""
Systematic testing of all Wix API order fetching functions
Test data:
- Order 1: Yesterday
- Order 2: Today 11:19
"""

import sys
import os
from datetime import datetime, timedelta
import json
import getpass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wix_printer_service.wix_client import WixClient, WixAPIError
from wix_printer_service.order_filter import WixOrderStatus, WixFulfillmentStatus, WixPaymentStatus

def print_separator(title):
    """Print a formatted separator."""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)

def print_order_summary(orders, function_name):
    """Print a summary of orders returned by a function."""
    print(f"\n📊 {function_name} Results:")
    print(f"   Orders found: {len(orders)}")

    if not orders:
        print("   ❌ No orders returned")
        return

    for i, order in enumerate(orders, 1):
        order_id = order.get('id', 'Unknown ID')
        created_date = order.get('createdDate', 'Unknown Date')
        status = order.get('status', 'Unknown Status')
        fulfillment_status = order.get('fulfillmentData', {}).get('status', 'Unknown')
        payment_status = order.get('paymentData', {}).get('status', 'Unknown')
        total = order.get('priceSummary', {}).get('total', {}).get('amount', 'Unknown')

        # Extract customer name if available
        buyer_info = order.get('buyerInfo', {})
        customer_name = f"{buyer_info.get('firstName', '')} {buyer_info.get('lastName', '')}".strip()
        if not customer_name:
            customer_name = buyer_info.get('email', 'Unknown Customer')

        print(f"   📝 Order {i}: {order_id}")
        print(f"       Customer: {customer_name}")
        print(f"       Created: {created_date}")
        print(f"       Order Status: {status}")
        print(f"       Fulfillment: {fulfillment_status}")
        print(f"       Payment: {payment_status}")
        print(f"       Total: {total}")

        # Show line items
        line_items = order.get('lineItems', [])
        if line_items:
            print(f"       Items: {len(line_items)}")
            for item in line_items[:3]:  # Show first 3 items
                item_name = item.get('productName', {}).get('original',
                                   item.get('name', 'Unknown Item'))
                quantity = item.get('quantity', 'Unknown')
                print(f"         - {item_name} (Qty: {quantity})")
            if len(line_items) > 3:
                print(f"         ... and {len(line_items) - 3} more items")
        print()

def test_connection(client):
    """Test basic API connection."""
    print_separator("API CONNECTION TEST")
    try:
        if client.test_connection():
            print("✅ API connection successful")
            return True
        else:
            print("❌ API connection failed")
            return False
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        return False

def test_search_orders_basic(client):
    """Test basic search_orders functionality."""
    print_separator("BASIC SEARCH ORDERS TEST")
    try:
        # Test basic search with no filters
        response = client.search_orders(limit=10)
        orders = response.get('orders', [])
        print_order_summary(orders, "search_orders (basic)")
        return orders
    except Exception as e:
        print(f"❌ Basic search error: {e}")
        return []

def test_time_based_functions(client):
    """Test time-based order fetching functions."""
    print_separator("TIME-BASED FUNCTIONS TEST")

    functions_to_test = [
        ("get_recent_orders(30 min)", lambda: client.get_recent_orders(minutes_ago=30)),
        ("get_recent_orders(60 min)", lambda: client.get_recent_orders(minutes_ago=60)),
        ("get_recent_orders(24 hours)", lambda: client.get_recent_orders(minutes_ago=24*60)),
        ("get_orders_for_regular_polling(6h)", lambda: client.get_orders_for_regular_polling(hours_back=6)),
        ("get_orders_for_regular_polling(24h)", lambda: client.get_orders_for_regular_polling(hours_back=24)),
        ("get_orders_for_regular_polling(48h)", lambda: client.get_orders_for_regular_polling(hours_back=48)),
    ]

    results = {}
    for func_name, func in functions_to_test:
        try:
            orders = func()
            print_order_summary(orders, func_name)
            results[func_name] = len(orders)
        except Exception as e:
            print(f"❌ {func_name} error: {e}")
            results[func_name] = -1

    return results

def test_status_based_functions(client):
    """Test status-based order fetching functions."""
    print_separator("STATUS-BASED FUNCTIONS TEST")

    functions_to_test = [
        ("get_printable_orders()", lambda: client.get_printable_orders()),
        ("get_pending_fulfillment_orders()", lambda: client.get_pending_fulfillment_orders()),
        ("get_kitchen_orders(2h)", lambda: client.get_kitchen_orders(hours_back=2)),
        ("get_kitchen_orders(24h)", lambda: client.get_kitchen_orders(hours_back=24)),
        ("get_bar_orders(2h)", lambda: client.get_bar_orders(hours_back=2)),
        ("get_bar_orders(24h)", lambda: client.get_bar_orders(hours_back=24)),
    ]

    results = {}
    for func_name, func in functions_to_test:
        try:
            orders = func()
            print_order_summary(orders, func_name)
            results[func_name] = len(orders)
        except Exception as e:
            print(f"❌ {func_name} error: {e}")
            results[func_name] = -1

    return results

def test_specific_status_filters(client):
    """Test specific status combination filters."""
    print_separator("SPECIFIC STATUS FILTERS TEST")

    status_combinations = [
        ("APPROVED + PAID + NOT_FULFILLED",
         lambda: client.get_orders_by_status(
             order_status="APPROVED",
             payment_status="PAID",
             fulfillment_status="NOT_FULFILLED"
         )),
        ("APPROVED + NOT_PAID + NOT_FULFILLED",
         lambda: client.get_orders_by_status(
             order_status="APPROVED",
             payment_status="NOT_PAID",
             fulfillment_status="NOT_FULFILLED"
         )),
        ("Any status + FULFILLED",
         lambda: client.get_orders_by_fulfillment_status("FULFILLED", hours_back=48)),
        ("Any status + NOT_FULFILLED",
         lambda: client.get_orders_by_fulfillment_status("NOT_FULFILLED", hours_back=48)),
    ]

    results = {}
    for filter_name, func in status_combinations:
        try:
            orders = func()
            print_order_summary(orders, filter_name)
            results[filter_name] = len(orders)
        except Exception as e:
            print(f"❌ {filter_name} error: {e}")
            results[filter_name] = -1

    return results

def test_common_filters(client):
    """Test predefined common filters."""
    print_separator("COMMON FILTERS TEST")

    common_filters = [
        "printable_orders",
        "pending_fulfillment",
        "recent_paid_orders",
        "all_active_orders",
        "completed_orders"
    ]

    results = {}
    for filter_name in common_filters:
        try:
            orders = client.get_orders_with_common_filter(filter_name)
            print_order_summary(orders, f"common_filter: {filter_name}")
            results[filter_name] = len(orders)
        except Exception as e:
            print(f"❌ common_filter {filter_name} error: {e}")
            results[filter_name] = -1

    return results

def print_summary_report(all_results):
    """Print a comprehensive summary report."""
    print_separator("COMPREHENSIVE SUMMARY REPORT")

    print("📊 Function Performance Summary:")
    print("-" * 50)

    for category, results in all_results.items():
        print(f"\n🔹 {category.upper()}:")
        for func_name, count in results.items():
            if count == -1:
                status = "❌ ERROR"
            elif count == 0:
                status = "⚪ NO ORDERS"
            else:
                status = f"✅ {count} ORDERS"
            print(f"   {func_name:<40} {status}")

    # Analysis
    print("\n🔍 ANALYSIS:")
    print("-" * 30)

    # Check if we found the two test orders
    total_unique_orders = set()
    for category, results in all_results.items():
        for func_name, count in results.items():
            if count > 0:
                total_unique_orders.add(func_name)

    # Expected: We should find at least the today order (11:19) in recent functions
    print(f"✅ Expected Results:")
    print(f"   - Today's order (11:19) should appear in recent/time-based functions")
    print(f"   - Yesterday's order should appear in longer time-range functions")
    print(f"   - Status-based functions should find orders based on their actual status")

    print(f"\n📈 Recommendations:")
    if any(count > 0 for results in all_results.values() for count in results.values()):
        print(f"   ✅ API is working - orders are being found")
        print(f"   🔧 Check specific functions that returned 0 orders")
        print(f"   📊 Verify order statuses match filter criteria")
    else:
        print(f"   ⚠️  No orders found by any function - check:")
        print(f"      - API credentials (WIX_API_KEY, WIX_SITE_ID)")
        print(f"      - Order statuses (not INITIALIZED)")
        print(f"      - Time zone differences")

def setup_credentials():
    """Setup API credentials interactively if not found."""
    if not os.getenv('WIX_API_KEY'):
        print("🔑 No .env file found. Please provide your Wix API credentials:")
        api_key = getpass.getpass("WIX_API_KEY: ")
        site_id = input("WIX_SITE_ID: ")

        # Set environment variables for this session
        os.environ['WIX_API_KEY'] = api_key
        os.environ['WIX_SITE_ID'] = site_id
        os.environ['WIX_API_BASE_URL'] = 'https://www.wixapis.com'

        print("✅ Credentials set for this session")

def main():
    """Main testing function."""
    print("🚀 SYSTEMATIC WIX API ORDER FETCHING TEST")
    print("==========================================")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Expected Test Data:")
    print("  📝 Order 1: Yesterday")
    print("  📝 Order 2: Today 11:19")
    print()

    try:
        # Setup credentials if needed
        setup_credentials()

        # Initialize client
        print("🔧 Initializing Wix API Client...")
        client = WixClient()
        print("✅ Client initialized successfully")

        # Test connection first
        if not test_connection(client):
            print("❌ Cannot continue without API connection")
            return

        # Run all tests
        all_results = {}

        # Basic search test
        test_search_orders_basic(client)

        # Time-based functions
        all_results["Time-Based Functions"] = test_time_based_functions(client)

        # Status-based functions
        all_results["Status-Based Functions"] = test_status_based_functions(client)

        # Specific status filters
        all_results["Specific Status Filters"] = test_specific_status_filters(client)

        # Common filters
        all_results["Common Filters"] = test_common_filters(client)

        # Summary report
        print_summary_report(all_results)

    except WixAPIError as e:
        print(f"❌ Wix API Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"\n🏁 Test completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()