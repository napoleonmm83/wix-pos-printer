#!/usr/bin/env python3
"""
Script to find and analyze a specific order from today.
Looking for order from 19:53 with value 44.00 CHF.
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find_order_by_criteria():
    """Find the specific order from today 19:53 with 44.00 CHF"""
    print("=" * 80)
    print("SEARCHING FOR SPECIFIC ORDER")
    print("=" * 80)
    print("Looking for order from today 19:53 with value 44.00 CHF")

    try:
        client = WixClient()
        print("+ Wix Client initialized")

        # Get all orders from today
        today = datetime.now().strftime('%Y-%m-%d')
        response = client.search_orders(limit=100, filter={
            'status': {'$ne': 'INITIALIZED'},
            'createdDate': {'$gte': f'{today}T00:00:00.000Z'}
        })

        orders = response.get('orders', [])
        print(f"+ Found {len(orders)} orders from today")

        # Look for order with 44.00 CHF
        target_orders = []

        for order in orders:
            # Check price
            price_summary = order.get('priceSummary', {})
            total = price_summary.get('total', {})
            amount = total.get('amount', '0')
            currency = order.get('currency', 'N/A')

            # Check time
            created_date = order.get('createdDate', '')
            order_time = created_date[11:16] if len(created_date) > 16 else 'unknown'

            print(f"- Order {order.get('number', 'N/A')} | Time: {order_time} | Amount: {amount} {currency}")

            # Check if this matches our criteria
            if amount == '44.00' and currency == 'CHF':
                target_orders.append(order)
                print(f"  >>> MATCH FOUND! <<<")

        if target_orders:
            print(f"\n+ Found {len(target_orders)} matching order(s)!")

            for idx, order in enumerate(target_orders):
                print(f"\n--- MATCHING ORDER #{idx + 1} ---")
                print(f"Order ID: {order.get('id')}")
                print(f"Order Number: {order.get('number')}")
                print(f"Created: {order.get('createdDate')}")
                print(f"Updated: {order.get('updatedDate')}")
                print(f"Status: {order.get('status')}")
                print(f"Payment Status: {order.get('paymentStatus')}")
                print(f"Fulfillment Status: {order.get('fulfillmentStatus')}")

                # Customer info
                buyer_info = order.get('buyerInfo', {})
                contact_details = order.get('billingInfo', {}).get('contactDetails', {})
                print(f"Customer: {contact_details.get('firstName', '')} {contact_details.get('lastName', '')}")
                print(f"Email: {buyer_info.get('email', 'N/A')}")

                # Items
                line_items = order.get('lineItems', [])
                print(f"Items ({len(line_items)}):")
                for item in line_items:
                    product_name = item.get('productName', {}).get('original', item.get('name', 'Unknown'))
                    quantity = item.get('quantity', 0)
                    price = item.get('price', {}).get('amount', '0')
                    print(f"  - {product_name} x{quantity} = {price} CHF")

                # Total
                price_summary = order.get('priceSummary', {})
                total = price_summary.get('total', {})
                print(f"Total: {total.get('amount', '0')} {order.get('currency', 'CHF')}")

                return order
        else:
            print("- No matching orders found with 44.00 CHF")

            # Show all today's orders for reference
            print(f"\nAll orders from today ({len(orders)}):")
            for order in orders:
                price_summary = order.get('priceSummary', {})
                total = price_summary.get('total', {})
                amount = total.get('amount', '0')
                currency = order.get('currency', 'N/A')
                created_date = order.get('createdDate', '')
                order_time = created_date[11:16] if len(created_date) > 16 else 'unknown'

                print(f"  - #{order.get('number')} | {order_time} | {amount} {currency} | {order.get('status')}")

            return None

    except Exception as e:
        print(f"- Error: {e}")
        return None

    finally:
        client.close()

def check_database_for_order():
    """Check if the order is in our database"""
    print("\n" + "=" * 80)
    print("CHECKING DATABASE")
    print("=" * 80)

    try:
        from wix_printer_service.database import Database

        db = Database()

        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Look for orders from today with 44.00
                cursor.execute("""
                    SELECT wix_order_id, total_amount, currency, order_date, status, created_at
                    FROM orders
                    WHERE DATE(order_date) = CURRENT_DATE
                    AND total_amount = 44.00
                    AND currency = 'CHF'
                    ORDER BY order_date DESC
                """)

                db_orders = cursor.fetchall()

                if db_orders:
                    print(f"+ Found {len(db_orders)} matching order(s) in database:")
                    for order in db_orders:
                        print(f"  - Wix ID: {order[0]}")
                        print(f"    Amount: {order[1]} {order[2]}")
                        print(f"    Order Date: {order[3]}")
                        print(f"    Status: {order[4]}")
                        print(f"    Created: {order[5]}")

                        # Check for print jobs
                        cursor.execute("""
                            SELECT job_type, status, attempts, created_at
                            FROM print_jobs
                            WHERE order_id = %s
                            ORDER BY created_at
                        """, (order[0],))

                        jobs = cursor.fetchall()
                        print(f"    Print Jobs ({len(jobs)}):")
                        for job in jobs:
                            print(f"      - {job[0]}: {job[1]} (attempts: {job[2]}) at {job[3]}")
                else:
                    print("- No matching orders found in database")

                    # Show what we have from today
                    cursor.execute("""
                        SELECT wix_order_id, total_amount, currency, order_date, status
                        FROM orders
                        WHERE DATE(order_date) = CURRENT_DATE
                        ORDER BY order_date DESC
                    """)

                    all_today = cursor.fetchall()
                    print(f"\nAll orders from today in database ({len(all_today)}):")
                    for order in all_today:
                        print(f"  - {order[0][:8]}... | {order[1]} {order[2]} | {order[3]} | {order[4]}")

    except Exception as e:
        print(f"- Database error: {e}")

def main():
    print("Finding Specific Order - 44.00 CHF from 19:53")
    print("=" * 80)

    # Search in Wix API
    order = find_order_by_criteria()

    # Check database
    check_database_for_order()

    if order:
        print(f"\n+ SUCCESS: Found the 44.00 CHF order!")
        print(f"  Order ID: {order.get('id')}")
        print(f"  Order Number: {order.get('number')}")
        print(f"  Created: {order.get('createdDate')}")
    else:
        print(f"\n- Order not found or criteria didn't match")

if __name__ == "__main__":
    main()