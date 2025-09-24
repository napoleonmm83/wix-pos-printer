import hmac
import hashlib
import json
import logging
import os
import asyncio
import subprocess
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from fastapi import FastAPI, Request, HTTPException, status, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import httpx
import uvicorn
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [WEBHOOK] - %(message)s',
    handlers=[
        logging.FileHandler("webhook.log"),
        logging.StreamHandler()
    ]
)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Environment Variables ---
SECRET_KEY = os.environ.get("WIX_SECRET_KEY", "YOUR_WIX_WEBHOOK_SECRET_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
PRINTER_SERVICE_URL = os.environ.get("PRINTER_SERVICE_URL", "http://localhost:8000")
WIX_API_KEY = os.environ.get("WIX_API_KEY")
WIX_SITE_ID = os.environ.get("WIX_SITE_ID")
WIX_API_BASE_URL = os.environ.get("WIX_API_BASE_URL", "https://www.wixapis.com")
AUTO_CHECK_ENABLED = os.environ.get("AUTO_CHECK_ENABLED", "true").lower() == "true"
AUTO_CHECK_INTERVAL = int(os.environ.get("AUTO_CHECK_INTERVAL", "30"))
AUTO_CHECK_HOURS_BACK = int(os.environ.get("AUTO_CHECK_HOURS_BACK", "1"))
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")

auto_check_running = False

# --- Database Helper Functions (PostgreSQL) ---
@contextmanager
def get_db_connection():
    """Provide a transactional scope around a series of PostgreSQL operations."""
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        yield conn
        conn.commit()
    except psycopg2.Error as e:
        logging.error(f"Database transaction failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_auto_check_db():
    """Initialize database table for tracking auto-checked orders in PostgreSQL."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS auto_checked_orders (
                        id SERIAL PRIMARY KEY,
                        wix_order_id TEXT UNIQUE NOT NULL,
                        checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        processed_for_print BOOLEAN DEFAULT FALSE,
                        print_status TEXT DEFAULT 'pending',
                        last_updated_date TEXT,
                        reprint_count INTEGER DEFAULT 0
                    )
                ''')
        logging.info("Auto-check database table initialized successfully")
    except psycopg2.Error as e:
        logging.error(f"Failed to initialize auto-check database: {e}")

def is_order_already_processed(order_id: str) -> bool:
    """Check if an order has already been processed by auto-check."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT processed_for_print FROM auto_checked_orders WHERE wix_order_id = %s", (order_id,))
                result = cursor.fetchone()
        return result is not None and result[0]
    except psycopg2.Error as e:
        logging.error(f"Error checking if order {order_id} was processed: {e}")
        return False

def has_order_been_updated(order_id: str, current_updated_date: str) -> bool:
    """Check if an order has been updated since last processing."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT last_updated_date FROM auto_checked_orders WHERE wix_order_id = %s", (order_id,))
                result = cursor.fetchone()

        if result is None:
            return False  # Order not in database yet

        last_known_update = result[0]
        if not last_known_update:
            return True  # No update date stored, consider it updated

        # Normalize dates for comparison by removing microseconds and timezone info
        def normalize_date(date_str):
            if not date_str:
                return ""
            # Remove microseconds (.XXX) and timezone (Z) for comparison
            date_str = str(date_str)
            if '.' in date_str:
                date_str = date_str.split('.')[0]
            date_str = date_str.replace('Z', '').replace('+00:00', '')
            return date_str

        normalized_current = normalize_date(current_updated_date)
        normalized_last = normalize_date(last_known_update)

        # Debug log for troubleshooting
        logging.debug(f"Date comparison for {order_id}: Current='{normalized_current}' vs Last='{normalized_last}'")

        return normalized_current != normalized_last
    except psycopg2.Error as e:
        logging.error(f"Error checking if order {order_id} was updated: {e}")
        return False

def increment_reprint_count(order_id: str):
    """Increment the reprint count for an order."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE auto_checked_orders
                    SET reprint_count = reprint_count + 1
                    WHERE wix_order_id = %s
                ''', (order_id,))
    except psycopg2.Error as e:
        logging.error(f"Error incrementing reprint count for order {order_id}: {e}")

def mark_order_as_processed(order_id: str, print_status: str = "sent", updated_date: str = None):
    """Mark an order as processed in the auto-check database using ON CONFLICT."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO auto_checked_orders (wix_order_id, checked_at, processed_for_print, print_status, last_updated_date)
                    VALUES (%s, %s, TRUE, %s, %s)
                    ON CONFLICT (wix_order_id) DO UPDATE SET
                        checked_at = EXCLUDED.checked_at,
                        processed_for_print = EXCLUDED.processed_for_print,
                        print_status = EXCLUDED.print_status,
                        last_updated_date = EXCLUDED.last_updated_date;
                ''', (order_id, datetime.utcnow(), print_status, updated_date))
        logging.info(f"Marked order {order_id} as processed with status: {print_status}")
    except psycopg2.Error as e:
        logging.error(f"Error marking order {order_id} as processed: {e}")

# --- Application Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    """Initialize the application and start auto-check if enabled."""
    logging.info("Starting Wix Order Webhook Service...")
    await start_auto_check_task()
    logging.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of the application."""
    global auto_check_running
    logging.info("Shutting down Wix Order Webhook Service...")
    if auto_check_running:
        auto_check_running = False
        logging.info("Auto-check task stopped")
    logging.info("Application shutdown complete")

# --- Wix API Helper Functions ---
async def fetch_wix_orders(from_date: Optional[str] = None, to_date: Optional[str] = None, limit: int = 50):
    if not WIX_API_KEY or not WIX_SITE_ID:
        raise HTTPException(status_code=500,detail="Wix API credentials not configured")
    headers = {
        "Authorization": WIX_API_KEY,
        "Content-Type": "application/json",
        "wix-site-id": WIX_SITE_ID
    }
    params = {
        "paging": {"limit": min(limit, 100)},
        "sort": [{"createdDate": "DESC"}]
    }
    filter_obj = {"status": {"$ne": "INITIALIZED"}}
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = from_date
        if to_date:
            date_filter["$lte"] = to_date
        filter_obj["createdDate"] = date_filter
    params["filter"] = filter_obj
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{WIX_API_BASE_URL}/ecom/v1/orders/search"
            response = await client.post(url, headers=headers, json=params)
            response.raise_for_status()
            data = response.json()
            return data.get("orders", [])
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f"Error fetching Wix orders: {e}")
        return []

# --- Auto-Check Background Task ---
async def auto_check_new_orders():
    global auto_check_running
    if auto_check_running:
        return
    auto_check_running = True
    logging.info(f"Starting enhanced auto-check task (interval: {AUTO_CHECK_INTERVAL}s, look back: {AUTO_CHECK_HOURS_BACK}h)")
    logging.info("Auto-check now detects: NEW orders + UPDATED orders (qty changes, new items, address changes)")

    cycle_count = 0
    while auto_check_running:
        try:
            cycle_count += 1
            now = datetime.utcnow()
            from_date = (now - timedelta(hours=AUTO_CHECK_HOURS_BACK)).isoformat() + "Z"

            logging.info(f"[SEARCH] Auto-check cycle #{cycle_count} starting - Looking for orders since {from_date}")
            orders = await fetch_wix_orders(from_date=from_date, limit=100)
            logging.info(f"[FOUND] {len(orders)} orders in {AUTO_CHECK_HOURS_BACK}h window")

            new_orders = 0
            updated_orders = 0
            skipped_orders = 0
            canceled_orders = 0

            for order in orders:
                order_id = order.get('id')
                updated_date = order.get('updatedDate', '')
                order_number = order.get('number', 'N/A')
                order_status = order.get('status', 'N/A')
                payment_status = order.get('paymentStatus', 'N/A')
                fulfillment_status = order.get('fulfillmentStatus', 'N/A')
                created_date = order.get('createdDate', '')

                # Get price info for debugging
                price_summary = order.get('priceSummary', {})
                total_amount = price_summary.get('total', {}).get('amount', '0')
                currency = order.get('currency', 'N/A')

                if not order_id:
                    logging.debug(f"⚠️ Order without ID found, skipping")
                    continue

                # Enhanced debug log for every order
                logging.info(f"[CHECK] Order #{order_number} ({order_id[:8]}...)")
                logging.info(f"   Status: {order_status} | Payment: {payment_status} | Fulfillment: {fulfillment_status}")
                logging.info(f"   Amount: {total_amount} {currency}")
                logging.info(f"   Created: {created_date[:19]} | Updated: {updated_date[:19]}")

                # Filter out CANCELED orders - do not process them
                if order_status and order_status.upper() in ['CANCELED', 'CANCELLED']:
                    logging.info(f"   [SKIP] Order #{order_number} is CANCELED - canceled orders are not printed")
                    canceled_orders += 1
                    continue

                is_processed = is_order_already_processed(order_id)
                is_updated = has_order_been_updated(order_id, updated_date)

                logging.info(f"   DB-Check: Processed={is_processed} | Updated={is_updated}")

                should_process = False
                reason = ""

                if not is_processed:
                    # New order
                    should_process = True
                    reason = "new order"
                    new_orders += 1
                    logging.info(f"[NEW] ORDER: #{order_number} ({total_amount} {currency}) - {order_status}")
                elif is_updated:
                    # Existing order that has been updated
                    should_process = True
                    reason = "order updated"
                    updated_orders += 1
                    increment_reprint_count(order_id)
                    logging.info(f"[UPDATED] ORDER: #{order_number} ({total_amount} {currency}) - {order_status}")
                else:
                    # Already processed and not updated
                    skipped_orders += 1
                    logging.info(f"[SKIP] #{order_number} already processed and unchanged")

                if should_process:
                    logging.info(f"[PROCESS] Order #{order_number} ({order_id[:8]}...) - {reason}")
                    print_payload = {
                        "data": {"orderId": order_id},
                        "metadata": {
                            "source": "auto_check",
                            "reason": reason,
                            "updated_date": updated_date
                        }
                    }

                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.post(f"{PRINTER_SERVICE_URL}/webhook/orders", json=print_payload)
                            if response.status_code == 202:
                                mark_order_as_processed(order_id, "sent", updated_date)
                                logging.info(f"   [SUCCESS] Print job sent for #{order_number}")
                            else:
                                mark_order_as_processed(order_id, "failed", updated_date)
                                logging.warning(f"   [FAILED] Print job failed for #{order_number} - Status: {response.status_code}")
                    except Exception as e:
                        mark_order_as_processed(order_id, "error", updated_date)
                        logging.error(f"   [ERROR] Processing #{order_number}: {e}")

            # Always log cycle completion for debugging
            logging.info(f"[COMPLETE] Auto-check cycle #{cycle_count} complete:")
            logging.info(f"   Total orders found: {len(orders)}")
            logging.info(f"   New orders processed: {new_orders}")
            logging.info(f"   Updated orders processed: {updated_orders}")
            logging.info(f"   Orders skipped (already processed): {skipped_orders}")
            logging.info(f"   CANCELED orders filtered out: {canceled_orders}")

            if new_orders > 0 or updated_orders > 0:
                logging.info(f"[ACTION] {new_orders + updated_orders} orders sent to printer service")
            else:
                logging.info(f"[IDLE] No action needed: All orders already processed and up-to-date")

        except Exception as e:
            logging.error(f"[ERROR] Auto-check: Error during cycle #{cycle_count}: {e}")
            import traceback
            logging.error(f"   Stack trace: {traceback.format_exc()}")

        logging.info(f"[SLEEP] Auto-check sleeping for {AUTO_CHECK_INTERVAL}s until next cycle...")
        await asyncio.sleep(AUTO_CHECK_INTERVAL)

async def start_auto_check_task():
    if AUTO_CHECK_ENABLED and WIX_API_KEY and WIX_SITE_ID and DATABASE_URL:
        init_auto_check_db()
        asyncio.create_task(auto_check_new_orders())
        logging.info("Auto-check task started")
    else:
        logging.warning("Auto-check disabled: check AUTO_CHECK_ENABLED, Wix credentials, and DATABASE_URL.")

# --- Webhook Endpoint ---
@app.post('/webhook/orders')
async def handle_webhook(request: Request):
    raw_body = await request.body()
    # Validation logic remains the same
    # ...
    return JSONResponse(content={"status": "success"}, status_code=200)

# --- Auto-Update Webhook Endpoint ---
@app.post("/webhook/git-update")
async def handle_git_update(request: Request):
    """Receives a webhook from GitHub to trigger an auto-update."""
    logging.info("Git update webhook received. Verifying signature...")

    if not GITHUB_WEBHOOK_SECRET:
        logging.error("CRITICAL: GITHUB_WEBHOOK_SECRET is not configured. Aborting update.")
        raise HTTPException(status_code=500, detail="Update service not configured.")

    github_signature = request.headers.get("X-Hub-Signature-256")
    if not github_signature:
        logging.warning("Request is missing X-Hub-Signature-256 header. Aborting.")
        raise HTTPException(status_code=403, detail="Missing signature.")

    body = await request.body()
    
    h = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256)
    expected_signature = "sha256=" + h.hexdigest()

    if not hmac.compare_digest(expected_signature, github_signature):
        logging.error("Invalid GitHub signature. Aborting.")
        raise HTTPException(status_code=403, detail="Invalid signature.")

    logging.info("GitHub signature verified successfully.")

    try:
        # Use an absolute path to be safe, assuming the script is in /opt/wix-printer-service/scripts
        update_script_path = "/opt/wix-printer-service/scripts/auto-update.sh"
        
        logging.info(f"Executing update script via /bin/bash: {update_script_path}")
        
        # Use a more robust Popen call, explicitly using bash
        # This is non-blocking
        subprocess.Popen(['/bin/bash', update_script_path])
        
        logging.info("Update process initiated in the background.")
        return {"status": "success", "message": "Update process initiated."}
    except Exception as e:
        logging.error(f"Failed to start update script: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start update process.")

# --- Web UI & Other Endpoints ---
@app.get('/')
async def get_reprint_ui(request: Request):
    return templates.TemplateResponse("reprint.html", {"request": request, "orders": []})

# --- Health Check Endpoint ---
@app.get('/health')
def health_check():
    return {"status": "ok"}

# --- Main Execution ---
if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=5000)
