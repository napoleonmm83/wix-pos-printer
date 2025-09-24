#!/usr/bin/env python3
"""
Print Job Tracking Utility
Tracks and displays all print jobs, their status, and detailed logging information.
"""

import os
import sys
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from tabulate import tabulate
import argparse
import time
import json

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


def display_print_jobs(conn, status_filter=None, hours_back=24, show_content=False):
    """Display print jobs with their current status."""
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        # Build query with optional filters
        query = """
            SELECT
                pj.id,
                pj.order_id,
                pj.job_type,
                pj.status,
                pj.printer_name,
                pj.attempts,
                pj.max_attempts,
                pj.created_at,
                pj.updated_at,
                pj.printed_at,
                pj.error_message,
                o.wix_order_id,
                o.total_amount,
                o.currency,
                LENGTH(pj.content) as content_size
            FROM print_jobs pj
            LEFT JOIN orders o ON pj.order_id = o.id
            WHERE pj.created_at > %s
        """

        params = [datetime.now() - timedelta(hours=hours_back)]

        if status_filter:
            query += " AND pj.status = %s"
            params.append(status_filter)

        query += " ORDER BY pj.created_at DESC"

        cursor.execute(query, params)
        jobs = cursor.fetchall()

        if not jobs:
            print(f"No print jobs found in the last {hours_back} hours")
            return

        # Prepare data for table display
        table_data = []
        for job in jobs:
            # Calculate time in status
            time_diff = datetime.now() - job['updated_at'].replace(tzinfo=None)
            time_in_status = f"{int(time_diff.total_seconds() / 60)}m"

            # Format status with color codes for terminal
            status = job['status']
            if status == 'completed':
                status_display = f"\033[92m✓ {status}\033[0m"  # Green
            elif status == 'failed':
                status_display = f"\033[91m✗ {status}\033[0m"  # Red
            elif status == 'printing':
                status_display = f"\033[93m⟳ {status}\033[0m"  # Yellow
            else:  # pending
                status_display = f"\033[94m⋯ {status}\033[0m"  # Blue

            table_data.append([
                job['id'],
                job['wix_order_id'][:12] + "..." if job['wix_order_id'] else "N/A",
                job['job_type'],
                status_display,
                f"{job['attempts']}/{job['max_attempts']}",
                time_in_status,
                job['created_at'].strftime("%H:%M:%S"),
                f"{job['content_size']} chars",
                job['error_message'][:30] + "..." if job['error_message'] else ""
            ])

        headers = ["Job ID", "Order", "Type", "Status", "Attempts", "Time", "Created", "Size", "Error"]
        print(f"\n📋 Print Jobs (Last {hours_back} hours):")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

        # Show statistics
        show_statistics(cursor, hours_back)

        if show_content and jobs:
            print("\n📄 Latest Job Content Preview:")
            latest_job = jobs[0]
            cursor.execute("SELECT content FROM print_jobs WHERE id = %s", (latest_job['id'],))
            content = cursor.fetchone()[0]
            print(f"Job {latest_job['id']} ({latest_job['job_type']}):")
            print("-" * 50)
            print(content[:500] + ("..." if len(content) > 500 else ""))
            print("-" * 50)


def show_statistics(cursor, hours_back):
    """Display print job statistics."""
    # Overall statistics
    cursor.execute("""
        SELECT
            status,
            COUNT(*) as count,
            AVG(attempts) as avg_attempts
        FROM print_jobs
        WHERE created_at > %s
        GROUP BY status
    """, (datetime.now() - timedelta(hours=hours_back),))

    stats = cursor.fetchall()

    print("\n📊 Statistics:")
    total = 0
    for stat in stats:
        total += stat['count']
        print(f"  {stat['status'].capitalize()}: {stat['count']} jobs (avg {stat['avg_attempts']:.1f} attempts)")

    if total > 0:
        # Success rate
        completed = next((s['count'] for s in stats if s['status'] == 'completed'), 0)
        success_rate = (completed / total) * 100
        print(f"\n  Success Rate: {success_rate:.1f}%")

        # Job type distribution
        cursor.execute("""
            SELECT job_type, COUNT(*) as count
            FROM print_jobs
            WHERE created_at > %s
            GROUP BY job_type
        """, (datetime.now() - timedelta(hours=hours_back),))

        types = cursor.fetchall()
        print("\n  Job Types:")
        for type_stat in types:
            print(f"    {type_stat['job_type']}: {type_stat['count']}")


def monitor_print_jobs(conn, interval=5):
    """Monitor print jobs in real-time."""
    print(f"🔍 Monitoring print jobs (updating every {interval} seconds, press Ctrl+C to stop)...")

    last_jobs = {}

    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"🖨️  PRINT JOB MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 80)

            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Get recent jobs
                cursor.execute("""
                    SELECT
                        pj.*,
                        o.wix_order_id
                    FROM print_jobs pj
                    LEFT JOIN orders o ON pj.order_id = o.id
                    WHERE pj.created_at > %s
                    ORDER BY pj.updated_at DESC
                    LIMIT 20
                """, (datetime.now() - timedelta(hours=1),))

                jobs = cursor.fetchall()

                # Detect changes
                current_jobs = {job['id']: job['status'] for job in jobs}

                # Display jobs with change indicators
                table_data = []
                for job in jobs:
                    # Check if status changed
                    status_changed = False
                    if job['id'] in last_jobs and last_jobs[job['id']] != job['status']:
                        status_changed = True

                    status = job['status']
                    if status_changed:
                        status = f"⚡ {status}"  # Lightning bolt for changed status

                    # Color code status
                    if job['status'] == 'completed':
                        status_display = f"\033[92m{status}\033[0m"
                    elif job['status'] == 'failed':
                        status_display = f"\033[91m{status}\033[0m"
                    elif job['status'] == 'printing':
                        status_display = f"\033[93m{status}\033[0m"
                    else:
                        status_display = f"\033[94m{status}\033[0m"

                    # Time since update
                    time_diff = datetime.now() - job['updated_at'].replace(tzinfo=None)
                    if time_diff.total_seconds() < 60:
                        time_str = f"{int(time_diff.total_seconds())}s ago"
                    else:
                        time_str = f"{int(time_diff.total_seconds() / 60)}m ago"

                    table_data.append([
                        job['id'],
                        job['job_type'],
                        status_display,
                        f"{job['attempts']}/{job['max_attempts']}",
                        time_str,
                        job['printer_name'] or "default"
                    ])

                headers = ["ID", "Type", "Status", "Attempts", "Updated", "Printer"]
                print(tabulate(table_data, headers=headers, tablefmt="simple"))

                # Show queue status
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM print_jobs
                    WHERE created_at > %s
                    GROUP BY status
                """, (datetime.now() - timedelta(hours=1),))

                queue_stats = cursor.fetchall()
                print(f"\n📊 Queue Status (Last Hour):")
                for stat in queue_stats:
                    emoji = {"pending": "⏳", "printing": "🖨️", "completed": "✅", "failed": "❌"}.get(stat['status'], "❓")
                    print(f"  {emoji} {stat['status'].capitalize()}: {stat['count']}")

                # Check for stuck jobs
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM print_jobs
                    WHERE status = 'printing'
                    AND updated_at < %s
                """, (datetime.now() - timedelta(minutes=5),))

                stuck_count = cursor.fetchone()['count']
                if stuck_count > 0:
                    print(f"\n⚠️  WARNING: {stuck_count} job(s) stuck in 'printing' status for >5 minutes!")

                # Update last jobs for change detection
                last_jobs = current_jobs

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


def check_printer_service():
    """Check if the printer service is running and accessible."""
    import requests

    print("\n🔌 Checking Printer Service Status...")

    # Check local service
    try:
        response = requests.get("http://localhost:8000/status", timeout=2)
        if response.status_code == 200:
            status = response.json()
            print(f"  ✅ Printer service is running")
            print(f"     - Printer connected: {status.get('printer_connected', False)}")
            print(f"     - Manager running: {status.get('manager_running', False)}")
            print(f"     - Pending jobs: {status.get('pending_jobs', 0)}")
        else:
            print(f"  ⚠️  Printer service responded with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Printer service not accessible: {e}")

    # Check if print manager thread is running
    try:
        conn = get_database_connection()
        with conn.cursor() as cursor:
            # Check for recent job processing
            cursor.execute("""
                SELECT MAX(updated_at) as last_update
                FROM print_jobs
                WHERE status IN ('completed', 'failed')
            """)
            last_update = cursor.fetchone()[0]

            if last_update:
                time_diff = datetime.now() - last_update.replace(tzinfo=None)
                if time_diff.total_seconds() < 300:  # 5 minutes
                    print(f"  ✅ Print processing active (last job {int(time_diff.total_seconds())}s ago)")
                else:
                    print(f"  ⚠️  No jobs processed in {int(time_diff.total_seconds() / 60)} minutes")
        conn.close()
    except Exception as e:
        print(f"  ❌ Error checking job processing: {e}")


def trace_job(conn, job_id):
    """Trace the complete lifecycle of a specific print job."""
    print(f"\n🔍 Tracing Print Job #{job_id}")
    print("=" * 60)

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        # Get job details
        cursor.execute("""
            SELECT pj.*, o.wix_order_id
            FROM print_jobs pj
            LEFT JOIN orders o ON pj.order_id = o.id
            WHERE pj.id = %s
        """, (job_id,))

        job = cursor.fetchone()
        if not job:
            print(f"❌ Print job #{job_id} not found")
            return

        print(f"📋 Job Details:")
        print(f"  Order: {job['wix_order_id']}")
        print(f"  Type: {job['job_type']}")
        print(f"  Status: {job['status']}")
        print(f"  Printer: {job['printer_name'] or 'default'}")
        print(f"  Attempts: {job['attempts']}/{job['max_attempts']}")

        print(f"\n⏱️  Timeline:")
        print(f"  Created: {job['created_at']}")
        print(f"  Updated: {job['updated_at']}")
        if job['printed_at']:
            print(f"  Printed: {job['printed_at']}")
            duration = (job['printed_at'] - job['created_at']).total_seconds()
            print(f"  Duration: {int(duration)}s")

        if job['error_message']:
            print(f"\n❌ Error:")
            print(f"  {job['error_message']}")

        print(f"\n📄 Content Preview:")
        cursor.execute("SELECT content FROM print_jobs WHERE id = %s", (job_id,))
        content = cursor.fetchone()[0]
        print("-" * 60)
        print(content[:1000] + ("..." if len(content) > 1000 else ""))
        print("-" * 60)

        # Check for related jobs
        cursor.execute("""
            SELECT id, job_type, status
            FROM print_jobs
            WHERE order_id = %s AND id != %s
        """, (job['order_id'], job_id))

        related = cursor.fetchall()
        if related:
            print(f"\n🔗 Related Jobs for Same Order:")
            for r in related:
                print(f"  #{r['id']} - {r['job_type']} ({r['status']})")


def main():
    parser = argparse.ArgumentParser(description='Track and monitor print jobs')
    parser.add_argument('--status', help='Filter by status (pending/printing/completed/failed)')
    parser.add_argument('--hours', type=int, default=24, help='Show jobs from last N hours')
    parser.add_argument('--monitor', action='store_true', help='Monitor jobs in real-time')
    parser.add_argument('--interval', type=int, default=5, help='Monitor update interval in seconds')
    parser.add_argument('--content', action='store_true', help='Show content preview')
    parser.add_argument('--check', action='store_true', help='Check printer service status')
    parser.add_argument('--trace', type=int, help='Trace specific job by ID')

    args = parser.parse_args()

    if args.check:
        check_printer_service()

    conn = get_database_connection()

    try:
        if args.trace:
            trace_job(conn, args.trace)
        elif args.monitor:
            monitor_print_jobs(conn, args.interval)
        else:
            display_print_jobs(conn, args.status, args.hours, args.content)

            if not args.check:
                check_printer_service()

    finally:
        conn.close()


if __name__ == "__main__":
    main()