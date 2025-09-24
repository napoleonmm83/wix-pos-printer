#!/usr/bin/env python3
"""
Debug script to test Wix API connection and analyze returned data structure.
This will help us understand what data is being returned and debug reliability issues.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pprint import pprint

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from wix_printer_service.wix_client import WixClient, WixAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def debug_api_connection():
    """Test API connection and examine the data structure"""
    print("=" * 80)
    print("WIX API DEBUG SESSION")
    print("=" * 80)

    try:
        # Initialize client
        print("\n1. Initializing Wix Client...")
        client = WixClient()
        print("+ Client initialized successfully")

        # Test connection
        print("\n2. Testing API connection...")
        if client.test_connection():
            print("+ API connection successful")
        else:
            print("- API connection failed")
            return

        # Test simple search to get recent orders
        print("\n3. Fetching recent orders (last 50)...")
        response = client.search_orders(limit=50)

        print(f"+ API Response received")
        print(f"  - Total Count: {response.get('totalCount', 'N/A')}")
        print(f"  - Orders returned: {len(response.get('orders', []))}")

        orders = response.get('orders', [])
        if orders:
            print(f"\n4. Analyzing first order structure...")
            first_order = orders[0]

            print("\n--- FIRST ORDER RAW DATA ---")
            print(json.dumps(first_order, indent=2, default=str))

            print(f"\n--- ORDER ANALYSIS ---")
            print(f"Order ID: {first_order.get('id', 'N/A')}")
            print(f"Status: {first_order.get('status', 'N/A')}")
            print(f"Created: {first_order.get('createdDate', 'N/A')}")
            print(f"Updated: {first_order.get('updatedDate', 'N/A')}")

            # Check payment info
            payment_status = first_order.get('paymentStatus', 'N/A')
            print(f"Payment Status: {payment_status}")

            # Check fulfillment info
            fulfillment_status = first_order.get('fulfillmentStatus', 'N/A')
            print(f"Fulfillment Status: {fulfillment_status}")

            # Check totals structure
            totals = first_order.get('totals', {}) or first_order.get('priceSummary', {})
            if totals:
                print(f"Total Amount: {totals.get('total', {}).get('amount', 'N/A')} {totals.get('total', {}).get('currency', 'N/A')}")

            # Check line items
            line_items = first_order.get('lineItems', [])
            print(f"Line Items Count: {len(line_items)}")

            if line_items:
                print(f"\nFirst Line Item:")
                first_item = line_items[0]
                print(f"  - Name: {first_item.get('productName', {}).get('original', first_item.get('name', 'N/A'))}")
                print(f"  - Quantity: {first_item.get('quantity', 'N/A')}")
                print(f"  - Price: {first_item.get('price', {}).get('amount', 'N/A')}")

            # Check customer info
            buyer_info = first_order.get('buyerInfo', {})
            if buyer_info:
                print(f"\nCustomer:")
                print(f"  - Email: {buyer_info.get('email', 'N/A')}")
                print(f"  - Name: {buyer_info.get('contactDetails', {}).get('firstName', 'N/A')} {buyer_info.get('contactDetails', {}).get('lastName', 'N/A')}")

        # Test smart filtering
        print(f"\n5. Testing smart filtering - Recent orders (last 2 hours)...")
        recent_orders = client.get_recent_orders(minutes_ago=120)
        print(f"+ Smart filtering returned {len(recent_orders)} orders from last 2 hours")

        # Test auto-check function
        print(f"\n6. Testing auto-check functionality...")
        polling_orders = client.get_orders_for_regular_polling(hours_back=6)
        print(f"+ Regular polling returned {len(polling_orders)} orders from last 6 hours")

        print(f"\n7. Summary of API Structure:")
        print(f"  - Basic connection: + Working")
        print(f"  - Search orders: + Working ({len(orders)} orders found)")
        print(f"  - Smart filtering: + Working ({len(recent_orders)} recent orders)")
        print(f"  - Auto-check polling: + Working ({len(polling_orders)} polling orders)")

    except WixAPIError as e:
        print(f"- Wix API Error: {e}")
    except Exception as e:
        print(f"- Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if 'client' in locals():
            client.close()

def debug_database_connection():
    """Test database connection and structure"""
    print("\n" + "=" * 80)
    print("DATABASE DEBUG SESSION")
    print("=" * 80)

    try:
        from wix_printer_service.database import Database

        print("\n1. Initializing database connection...")
        db = Database()
        print("+ Database connection successful")

        print("\n2. Checking recent orders in database...")
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Check order count
                cursor.execute("SELECT COUNT(*) FROM orders")
                order_count = cursor.fetchone()[0]
                print(f"+ Total orders in database: {order_count}")

                # Get recent orders
                cursor.execute("""
                    SELECT wix_order_id, status, total_amount, currency, order_date, created_at
                    FROM orders
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                recent_orders = cursor.fetchall()

                if recent_orders:
                    print(f"\nRecent orders in database:")
                    for order in recent_orders:
                        print(f"  - ID: {order[0]} | Status: {order[1]} | Total: {order[2]} {order[3]} | Date: {order[4]}")

                # Check print jobs
                cursor.execute("SELECT COUNT(*) FROM print_jobs")
                job_count = cursor.fetchone()[0]
                print(f"\n+ Total print jobs in database: {job_count}")

                # Get recent print jobs
                cursor.execute("""
                    SELECT order_id, job_type, status, attempts, created_at
                    FROM print_jobs
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                recent_jobs = cursor.fetchall()

                if recent_jobs:
                    print(f"\nRecent print jobs in database:")
                    for job in recent_jobs:
                        print(f"  - Order: {job[0]} | Type: {job[1]} | Status: {job[2]} | Attempts: {job[3]} | Date: {job[4]}")

    except Exception as e:
        print(f"- Database error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("Wix POS Order Service - Debug Session")
    print("Testing API connection and data structure analysis\n")

    debug_api_connection()
    debug_database_connection()

    print("\n" + "=" * 80)
    print("DEBUG SESSION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()