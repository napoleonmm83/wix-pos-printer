#!/usr/bin/env python3
"""
Enhanced Debug Tool for Print Job Issues
Provides comprehensive debugging information for print job failures.
"""

import os
import sys
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import argparse
import json
import requests
import subprocess

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def get_database_connection():
    """Get database connection."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)
    return psycopg2.connect(db_url)


def check_system_status():
    """Check overall system status."""
    print("\n🔍 SYSTEM DIAGNOSTICS")
    print("=" * 70)

    # Check environment variables
    print("\n📋 Environment Variables:")
    required_vars = [
        "DATABASE_URL",
        "WIX_SITE_ID",
        "WIX_API_KEY",
        "PRINTER_SERVICE_URL"
    ]

    for var in required_vars:
        value = os.environ.get(var)
        if value:
            if "KEY" in var or "PASSWORD" in var:
                print(f"  ✅ {var}: ****** (set)")
            else:
                print(f"  ✅ {var}: {value[:50]}...")
        else:
            print(f"  ❌ {var}: NOT SET")

    # Check database connection
    print("\n🗄️  Database Connection:")
    try:
        conn = get_database_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM print_jobs")
            total_jobs = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            print(f"  ✅ Connected successfully")
            print(f"     Total print jobs: {total_jobs}")
            print(f"     Total orders: {total_orders}")
        conn.close()
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")

    # Check printer service
    print("\n🖨️  Printer Service:")
    check_printer_service_detailed()

    # Check for running processes
    print("\n🔄 Running Processes:")
    check_running_processes()


def check_printer_service_detailed():
    """Detailed check of printer service."""
    service_url = os.environ.get("PRINTER_SERVICE_URL", "http://localhost:8000")

    endpoints = [
        ("/status", "Service Status"),
        ("/printer/status", "Printer Status"),
        ("/recovery/status", "Recovery Status"),
        ("/self-healing/status", "Self-Healing Status")
    ]

    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{service_url}{endpoint}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ {name}: OK")

                # Show relevant details
                if endpoint == "/status":
                    print(f"     - Printer connected: {data.get('printer_connected', False)}")
                    print(f"     - Manager running: {data.get('manager_running', False)}")
                    print(f"     - Pending jobs: {data.get('pending_jobs', 0)}")
                elif endpoint == "/printer/status":
                    print(f"     - Status: {data.get('status', 'unknown')}")
                elif endpoint == "/recovery/status":
                    if data.get('current_session'):
                        print(f"     - Active recovery: {data['current_session']['type']}")
            else:
                print(f"  ⚠️  {name}: Status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ {name}: Not accessible")


def check_running_processes():
    """Check if relevant processes are running."""
    processes = [
        "python.*wix_printer_server.py",
        "python.*auto_check_service.py",
        "python.*webhook_server.py"
    ]

    for pattern in processes:
        try:
            if os.name == 'nt':
                # Windows
                result = subprocess.run(
                    ["wmic", "process", "where", f"CommandLine like '%{pattern.replace('.*', '%')}%'", "get", "ProcessId,CommandLine"],
                    capture_output=True,
                    text=True
                )
                if pattern.replace('.*', '') in result.stdout:
                    print(f"  ✅ {pattern.split('.')[-1].replace('py', '')}: Running")
                else:
                    print(f"  ❌ {pattern.split('.')[-1].replace('py', '')}: Not found")
            else:
                # Linux/Mac
                result = subprocess.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True
                )
                if result.returncode == 0:
                    print(f"  ✅ {pattern.split('.')[-1].replace('py', '')}: Running")
                else:
                    print(f"  ❌ {pattern.split('.')[-1].replace('py', '')}: Not found")
        except Exception as e:
            print(f"  ⚠️  Could not check {pattern}: {e}")


def analyze_failed_jobs(conn, hours=24):
    """Analyze patterns in failed print jobs."""
    print(f"\n❌ FAILED JOB ANALYSIS (Last {hours} hours)")
    print("=" * 70)

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        # Get failed jobs
        cursor.execute("""
            SELECT
                pj.*,
                o.wix_order_id,
                o.total_amount
            FROM print_jobs pj
            LEFT JOIN orders o ON pj.order_id = o.id
            WHERE pj.status = 'failed'
            AND pj.created_at > %s
            ORDER BY pj.created_at DESC
        """, (datetime.now() - timedelta(hours=hours),))

        failed_jobs = cursor.fetchall()

        if not failed_jobs:
            print("  ✅ No failed jobs in the specified timeframe")
            return

        print(f"\n  Found {len(failed_jobs)} failed jobs:")

        # Group by error message
        error_patterns = {}
        for job in failed_jobs:
            error = job['error_message'] or "No error message"
            if error not in error_patterns:
                error_patterns[error] = []
            error_patterns[error].append(job)

        print("\n  Error Patterns:")
        for error, jobs in error_patterns.items():
            print(f"\n  '{error[:100]}...':")
            print(f"    Count: {len(jobs)}")
            print(f"    Job Types: {', '.join(set(j['job_type'] for j in jobs))}")
            print(f"    Job IDs: {', '.join(str(j['id']) for j in jobs[:5])}")

        # Check for retry patterns
        print("\n  Retry Analysis:")
        for job in failed_jobs[:10]:  # Show first 10
            print(f"    Job #{job['id']}: {job['attempts']}/{job['max_attempts']} attempts")
            if job['attempts'] >= job['max_attempts']:
                print(f"      ⚠️  Max retries exhausted")


def trace_order_flow(conn, order_id):
    """Trace complete flow of an order through the system."""
    print(f"\n📦 ORDER FLOW TRACE: {order_id}")
    print("=" * 70)

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        # Find order
        cursor.execute("""
            SELECT * FROM orders
            WHERE wix_order_id = %s OR id = %s
        """, (order_id, order_id))

        order = cursor.fetchone()
        if not order:
            print(f"  ❌ Order not found: {order_id}")
            return

        print(f"\n  Order Details:")
        print(f"    ID: {order['id']}")
        print(f"    Wix ID: {order['wix_order_id']}")
        print(f"    Status: {order['status']}")
        print(f"    Amount: {order['total_amount']} {order['currency']}")
        print(f"    Created: {order['created_at']}")

        # Get all print jobs for this order
        cursor.execute("""
            SELECT * FROM print_jobs
            WHERE order_id = %s
            ORDER BY created_at
        """, (order['id'],))

        jobs = cursor.fetchall()

        print(f"\n  Print Jobs ({len(jobs)} total):")
        for job in jobs:
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'printing': '🖨️',
                'pending': '⏳'
            }.get(job['status'], '❓')

            print(f"\n    {status_icon} Job #{job['id']} - {job['job_type']}")
            print(f"      Status: {job['status']}")
            print(f"      Created: {job['created_at']}")
            print(f"      Updated: {job['updated_at']}")

            if job['printed_at']:
                duration = (job['printed_at'] - job['created_at']).total_seconds()
                print(f"      Printed: {job['printed_at']} (took {int(duration)}s)")

            if job['error_message']:
                print(f"      Error: {job['error_message']}")

            # Show timeline
            print(f"      Timeline:")
            print(f"        Created → ", end="")

            if job['status'] == 'pending':
                print("Waiting...")
            elif job['status'] == 'printing':
                print("Printing → ...")
            elif job['status'] == 'completed':
                print(f"Printing → Completed ({job['attempts']} attempts)")
            else:  # failed
                print(f"Printing → Failed ({job['attempts']}/{job['max_attempts']} attempts)")


def check_printer_hardware():
    """Check printer hardware status."""
    print("\n🖨️  PRINTER HARDWARE CHECK")
    print("=" * 70)

    # Try to connect directly to printer
    try:
        from escpos.printer import Usb

        print("  Attempting direct USB connection...")

        # Common USB printer vendor/product IDs
        vendor_product_pairs = [
            (0x04b8, 0x0e15),  # Epson TM-T88V
            (0x04b8, 0x0202),  # Epson TM-T88II
            (0x04b8, 0x0e03),  # Epson TM-T20
            (0x0519, 0x0001),  # Star Micronics
        ]

        printer_found = False
        for vendor_id, product_id in vendor_product_pairs:
            try:
                printer = Usb(vendor_id, product_id)
                print(f"  ✅ Printer found: Vendor {hex(vendor_id)}, Product {hex(product_id)}")
                printer_found = True

                # Try to get printer status
                try:
                    # Send a simple command to check if printer responds
                    printer.text("Test\n")
                    print("  ✅ Printer responds to commands")
                except Exception as e:
                    print(f"  ⚠️  Printer found but not responding: {e}")

                printer.close()
                break
            except:
                continue

        if not printer_found:
            print("  ❌ No USB printer detected")
            print("  Possible issues:")
            print("    - Printer not connected via USB")
            print("    - Printer powered off")
            print("    - USB permissions issue (try running with sudo)")
            print("    - Driver not installed")

    except ImportError:
        print("  ⚠️  python-escpos not installed")
    except Exception as e:
        print(f"  ❌ Hardware check failed: {e}")


def suggest_fixes():
    """Suggest fixes based on common issues."""
    print("\n💡 SUGGESTED FIXES")
    print("=" * 70)

    conn = get_database_connection()
    issues_found = []

    with conn.cursor() as cursor:
        # Check for stuck jobs
        cursor.execute("""
            SELECT COUNT(*) FROM print_jobs
            WHERE status = 'printing'
            AND updated_at < %s
        """, (datetime.now() - timedelta(minutes=5),))

        stuck_count = cursor.fetchone()[0]
        if stuck_count > 0:
            issues_found.append(f"stuck_jobs:{stuck_count}")

        # Check for high failure rate
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM print_jobs WHERE status = 'failed' AND created_at > %s) * 100.0 /
                NULLIF((SELECT COUNT(*) FROM print_jobs WHERE created_at > %s), 0) as failure_rate
        """, (datetime.now() - timedelta(hours=1), datetime.now() - timedelta(hours=1)))

        failure_rate = cursor.fetchone()[0] or 0
        if failure_rate > 20:
            issues_found.append(f"high_failure_rate:{failure_rate:.1f}%")

    conn.close()

    # Generate suggestions
    if "stuck_jobs" in str(issues_found):
        print("\n  🔧 Fix for stuck jobs:")
        print("    1. Restart the printer service:")
        print("       python scripts/reset_printed_orders.py")
        print("       python wix_printer_server.py")
        print("    2. Check USB connection and printer power")

    if "high_failure_rate" in str(issues_found):
        print("\n  🔧 Fix for high failure rate:")
        print("    1. Check printer paper and ink")
        print("    2. Verify USB permissions:")
        print("       sudo usermod -a -G dialout $USER")
        print("    3. Check printer queue:")
        print("       lpstat -t")

    # Check if service is not running
    service_url = os.environ.get("PRINTER_SERVICE_URL", "http://localhost:8000")
    try:
        requests.get(f"{service_url}/status", timeout=1)
    except:
        print("\n  🔧 Printer service not running:")
        print("    Start the service:")
        print("      python wix_printer_server.py")

    if not issues_found and stuck_count == 0:
        print("\n  ✅ No obvious issues detected")
        print("  If problems persist, check:")
        print("    - Printer physical connections")
        print("    - System logs: journalctl -u wix-printer")
        print("    - Application logs in the console output")


def main():
    parser = argparse.ArgumentParser(description='Debug print job issues')
    parser.add_argument('--check-all', action='store_true', help='Run all diagnostic checks')
    parser.add_argument('--failed', action='store_true', help='Analyze failed jobs')
    parser.add_argument('--trace', help='Trace specific order flow')
    parser.add_argument('--hardware', action='store_true', help='Check printer hardware')
    parser.add_argument('--fixes', action='store_true', help='Suggest fixes')
    parser.add_argument('--hours', type=int, default=24, help='Hours to look back')

    args = parser.parse_args()

    if args.check_all or (not any([args.failed, args.trace, args.hardware, args.fixes])):
        check_system_status()
        conn = get_database_connection()
        analyze_failed_jobs(conn, args.hours)
        conn.close()
        check_printer_hardware()
        suggest_fixes()
    else:
        if args.failed:
            conn = get_database_connection()
            analyze_failed_jobs(conn, args.hours)
            conn.close()

        if args.trace:
            conn = get_database_connection()
            trace_order_flow(conn, args.trace)
            conn.close()

        if args.hardware:
            check_printer_hardware()

        if args.fixes:
            suggest_fixes()


if __name__ == "__main__":
    main()