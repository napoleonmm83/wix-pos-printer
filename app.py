import hmac
import hashlib
import base64
import json
import logging
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, status, Form, Query, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import sqlite3
import httpx
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Configure logging to show timestamp, level, and message
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

# --- Application Startup Event ---
@app.on_event("startup")
async def startup_event():
    """Initialize the application and start auto-check if enabled."""
    logging.info("Starting Wix Order Webhook Service...")

    # Start auto-check task if enabled
    await start_auto_check_task()

    logging.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of the application."""
    global auto_check_running

    logging.info("Shutting down Wix Order Webhook Service...")

    # Stop auto-check task
    if auto_check_running:
        auto_check_running = False
        logging.info("Auto-check task stopped")

    logging.info("Application shutdown complete")

# --- Security --- 
# IMPORTANT: Replace this with your actual secret key from the Wix dashboard
# You can also use an environment variable for better security
SECRET_KEY = os.environ.get("WIX_SECRET_KEY", "YOUR_WIX_WEBHOOK_SECRET_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/wix_printer.db")
PRINTER_SERVICE_URL = os.environ.get("PRINTER_SERVICE_URL", "http://localhost:8000")

# Wix API Configuration
WIX_API_KEY = os.environ.get("WIX_API_KEY")
WIX_SITE_ID = os.environ.get("WIX_SITE_ID")
WIX_API_BASE_URL = os.environ.get("WIX_API_BASE_URL", "https://www.wixapis.com")

# Auto-check Configuration
AUTO_CHECK_ENABLED = os.environ.get("AUTO_CHECK_ENABLED", "true").lower() == "true"
AUTO_CHECK_INTERVAL = int(os.environ.get("AUTO_CHECK_INTERVAL", "30"))  # seconds
AUTO_CHECK_HOURS_BACK = int(os.environ.get("AUTO_CHECK_HOURS_BACK", "1"))  # hours to check back

# Global variable to control auto-check task
auto_check_running = False

# Helper to connect to the main service's database
def get_db_connection():
    # The database path is relative to the main service directory, not this app's directory.
    # We need to construct the correct path. Assuming this app runs from the same root.
    db_path = DATABASE_URL.split('///')[-1]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --- Database Helper Functions ---
def init_auto_check_db():
    """Initialize database table for tracking auto-checked orders."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create table for tracking auto-checked orders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_checked_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wix_order_id TEXT UNIQUE NOT NULL,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_for_print BOOLEAN DEFAULT FALSE,
                print_status TEXT DEFAULT 'pending'
            )
        ''')

        conn.commit()
        conn.close()
        logging.info("Auto-check database table initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize auto-check database: {e}")


def is_order_already_processed(order_id: str) -> bool:
    """Check if an order has already been processed by auto-check."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT processed_for_print FROM auto_checked_orders WHERE wix_order_id = ?", (order_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None and result[0]
    except Exception as e:
        logging.error(f"Error checking if order {order_id} was processed: {e}")
        return False


def mark_order_as_processed(order_id: str, print_status: str = "sent"):
    """Mark an order as processed in the auto-check database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO auto_checked_orders
            (wix_order_id, checked_at, processed_for_print, print_status)
            VALUES (?, ?, TRUE, ?)
        ''', (order_id, datetime.utcnow(), print_status))
        conn.commit()
        conn.close()
        logging.info(f"Marked order {order_id} as processed with status: {print_status}")
    except Exception as e:
        logging.error(f"Error marking order {order_id} as processed: {e}")


# --- Wix API Helper Functions ---
async def fetch_wix_orders(from_date: Optional[str] = None, to_date: Optional[str] = None, limit: int = 50):
    """
    Fetch orders from Wix Orders API within a specified date range.

    Args:
        from_date: Start date in ISO format (e.g., "2024-01-01T00:00:00Z")
        to_date: End date in ISO format (e.g., "2024-01-31T23:59:59Z")
        limit: Maximum number of orders to retrieve (default: 50, max: 100)

    Returns:
        List of orders from Wix API
    """
    if not WIX_API_KEY or not WIX_SITE_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wix API credentials not configured"
        )

    headers = {
        "Authorization": f"Bearer {WIX_API_KEY}",
        "Content-Type": "application/json",
        "wix-site-id": WIX_SITE_ID
    }

    # Build query parameters using correct Wix API format
    params = {
        "cursorPaging": {"limit": min(limit, 100)},  # Wix API max limit is 100
        "sort": [{"fieldName": "createdDate", "order": "DESC"}]
    }

    # Build filter object
    filter_obj = {}
    if from_date:
        filter_obj["createdDate"] = {"$gte": from_date}
    if to_date:
        if "createdDate" in filter_obj:
            filter_obj["createdDate"]["$lte"] = to_date
        else:
            filter_obj["createdDate"] = {"$lte": to_date}

    if filter_obj:
        params["filter"] = filter_obj

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{WIX_API_BASE_URL}/ecom/v1/orders/query"
            logging.info(f"Fetching orders from Wix API: {url}")
            logging.info(f"Query parameters: {params}")

            response = await client.post(url, headers=headers, json=params)
            response.raise_for_status()

            data = response.json()
            orders = data.get("orders", [])

            logging.info(f"Successfully fetched {len(orders)} orders from Wix API")
            return orders

    except httpx.RequestError as e:
        logging.error(f"Network error when fetching Wix orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Wix API"
        )
    except httpx.HTTPStatusError as e:
        logging.error(f"Wix API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Wix API error: {e.response.status_code}"
        )
    except Exception as e:
        logging.error(f"Unexpected error fetching Wix orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching orders"
        )


# --- Auto-Check Background Task ---
async def auto_check_new_orders():
    """Background task that automatically checks for new orders every X seconds."""
    global auto_check_running

    if auto_check_running:
        logging.warning("Auto-check task is already running")
        return

    auto_check_running = True
    logging.info(f"Starting auto-check task (interval: {AUTO_CHECK_INTERVAL}s, looking back: {AUTO_CHECK_HOURS_BACK}h)")

    try:
        while auto_check_running:
            try:
                # Calculate time range for checking
                now = datetime.utcnow()
                from_date = (now - timedelta(hours=AUTO_CHECK_HOURS_BACK)).isoformat() + "Z"
                to_date = now.isoformat() + "Z"

                logging.info(f"Auto-check: Fetching orders from {from_date} to {to_date}")

                # Fetch orders from Wix API
                orders = await fetch_wix_orders(from_date=from_date, to_date=to_date, limit=50)

                new_orders_count = 0
                processed_orders = []

                for order in orders:
                    order_id = order.get('id')
                    if not order_id:
                        continue

                    # Check if this order was already processed by auto-check
                    if is_order_already_processed(order_id):
                        continue

                    new_orders_count += 1
                    logging.info(f"Auto-check: Found new order {order_id}")

                    try:
                        # Create payload for printer service
                        print_payload = {
                            "data": {"orderId": order_id},
                            "metadata": {
                                "source": "auto_check",
                                "fetchedAt": datetime.utcnow().isoformat(),
                                "interval": AUTO_CHECK_INTERVAL
                            }
                        }

                        # Send to printer service
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.post(f"{PRINTER_SERVICE_URL}/jobs/wix", json=print_payload)

                            if response.status_code == 202:
                                mark_order_as_processed(order_id, "sent")
                                processed_orders.append(order_id)
                                logging.info(f"Auto-check: Successfully sent order {order_id} to printer")
                            else:
                                mark_order_as_processed(order_id, "failed")
                                logging.warning(f"Auto-check: Failed to send order {order_id} to printer: {response.status_code}")

                    except Exception as e:
                        mark_order_as_processed(order_id, "error")
                        logging.error(f"Auto-check: Error processing order {order_id}: {e}")

                if new_orders_count > 0:
                    logging.info(f"Auto-check: Processed {len(processed_orders)}/{new_orders_count} new orders")
                else:
                    logging.debug("Auto-check: No new orders found")

            except Exception as e:
                logging.error(f"Auto-check: Error during order checking cycle: {e}")

            # Wait for next check
            await asyncio.sleep(AUTO_CHECK_INTERVAL)

    except asyncio.CancelledError:
        logging.info("Auto-check task was cancelled")
    finally:
        auto_check_running = False
        logging.info("Auto-check task stopped")


async def start_auto_check_task():
    """Start the auto-check background task if enabled."""
    if AUTO_CHECK_ENABLED and WIX_API_KEY and WIX_SITE_ID:
        # Initialize database
        init_auto_check_db()

        # Start background task
        asyncio.create_task(auto_check_new_orders())
        logging.info("Auto-check task started")
    else:
        if not AUTO_CHECK_ENABLED:
            logging.info("Auto-check is disabled via configuration")
        else:
            logging.warning("Auto-check disabled: Wix API credentials not configured")


# --- Webhook Endpoint ---
@app.post('/webhook/orders')
async def handle_webhook(request: Request):
    """Receives, validates, and processes webhook events from Wix."""
    logging.info("Webhook endpoint hit. Starting validation...")
    
    # 1. Get Auth Token and Body
    auth_token = request.headers.get('X-Auth-Token')
    raw_body = await request.body()

    # Log incoming data for debugging
    logging.info(f"Received Headers: {request.headers}")
    logging.info(f"Received Body: {raw_body.decode('utf-8')}")

    # 2. Validate Auth Token
    if not auth_token:
        logging.warning("Request is missing 'X-Auth-Token' header.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")

    if not hmac.compare_digest(auth_token, SECRET_KEY):
        logging.error("Invalid auth token received.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token")

    logging.info("Auth token validation successful!")

    # 3. Process the validated payload
    try:
        data = json.loads(raw_body)
        logging.info(f"Processing valid payload: {json.dumps(data, indent=2)}")
        
        # --- YOUR PRINTER LOGIC GOES HERE ---
        # Example: Extract order details
        order_id = data.get('data', {}).get('orderId')
        if order_id:
            logging.info(f"Successfully extracted Order ID: {order_id}. Triggering printer...")
            # print_order(data) # <--- Call your printer function here
        else:
            logging.warning("Payload did not contain an orderId.")
        # ----------------------------------------

    except json.JSONDecodeError:
        logging.error("Failed to decode JSON from request body.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    except Exception as e:
        logging.error(f"An unexpected error occurred during processing: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

    return JSONResponse(content={"status": "success"}, status_code=status.HTTP_200_OK)

# --- Web UI Endpoints ---

@app.get('/')
async def get_reprint_ui(request: Request):
    """Serves the web UI for reprinting orders."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fetch the last 10 orders
        cursor.execute("SELECT wix_order_id, created_at FROM orders ORDER BY created_at DESC LIMIT 10")
        orders = cursor.fetchall()
        conn.close()
        return templates.TemplateResponse("reprint.html", {"request": request, "orders": orders})
    except Exception as e:
        logging.error(f"Could not fetch orders for UI: {e}")
        return templates.TemplateResponse("reprint.html", {"request": request, "orders": [], "error": str(e)})

@app.post('/reprint')
async def handle_reprint_request(order_id: str = Form(...)):
    """Handles the reprint request from the web UI form."""
    logging.info(f"Reprint request received from Web UI for order ID: {order_id}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE wix_order_id = ? LIMIT 1", (order_id,))
        order_data = cursor.fetchone()
        conn.close()

        if not order_data:
            logging.error(f"Order ID {order_id} not found in the database for reprinting.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order ID not found")

        # Reconstruct a payload for the main service
        reconstructed_payload = {
            "data": {"orderId": order_data['wix_order_id']},
            "metadata": {"isReprint": True}
        }

        # Forward the payload to the main printer service
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{PRINTER_SERVICE_URL}/jobs/wix", json=reconstructed_payload)
            response.raise_for_status()

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": "Reprint job accepted", "details": response.json()}
        )

    except httpx.RequestError as e:
        logging.error(f"Could not connect to the main printer service: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Main printer service is unavailable")
    except Exception as e:
        logging.error(f"An error occurred during reprint request for order {order_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# --- Active Order Fetching Endpoints ---

@app.get('/orders/fetch')
async def fetch_orders_by_date_range(
    from_date: Optional[str] = Query(None, description="Start date in ISO format (e.g., 2024-01-01T00:00:00Z)"),
    to_date: Optional[str] = Query(None, description="End date in ISO format (e.g., 2024-01-31T23:59:59Z)"),
    hours_back: Optional[int] = Query(None, description="Hours to look back from now (alternative to from_date/to_date)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of orders to retrieve"),
    process_orders: bool = Query(False, description="Whether to automatically process fetched orders for printing")
):
    """
    Fetch orders from Wix API within a specified date range or time period.

    You can specify either:
    - from_date and to_date for a specific date range
    - hours_back to fetch orders from the last N hours
    - If no date parameters are provided, fetches orders from the last 24 hours
    """
    logging.info(f"Order fetch request: from_date={from_date}, to_date={to_date}, hours_back={hours_back}, limit={limit}")

    # If hours_back is specified, calculate from_date and to_date
    if hours_back is not None:
        now = datetime.utcnow()
        from_date = (now - timedelta(hours=hours_back)).isoformat() + "Z"
        to_date = now.isoformat() + "Z"
        logging.info(f"Using hours_back={hours_back}: from_date={from_date}, to_date={to_date}")

    # Default to last 24 hours if no dates specified
    elif from_date is None and to_date is None:
        now = datetime.utcnow()
        from_date = (now - timedelta(hours=24)).isoformat() + "Z"
        to_date = now.isoformat() + "Z"
        logging.info(f"No dates specified, using last 24 hours: from_date={from_date}, to_date={to_date}")

    try:
        # Fetch orders from Wix API
        orders = await fetch_wix_orders(from_date=from_date, to_date=to_date, limit=limit)

        processed_orders = []

        if process_orders:
            # Process each order for printing
            for order in orders:
                order_id = order.get('id')
                if order_id:
                    try:
                        # Create payload for printer service
                        print_payload = {
                            "data": {"orderId": order_id},
                            "metadata": {"source": "active_fetch", "fetchedAt": datetime.utcnow().isoformat()}
                        }

                        # Send to printer service
                        async with httpx.AsyncClient() as client:
                            response = await client.post(f"{PRINTER_SERVICE_URL}/jobs/wix", json=print_payload)
                            if response.status_code == 202:
                                processed_orders.append(order_id)
                                logging.info(f"Successfully queued order {order_id} for printing")
                            else:
                                logging.warning(f"Failed to queue order {order_id}: {response.status_code}")

                    except Exception as e:
                        logging.error(f"Error processing order {order_id} for printing: {e}")

        response_data = {
            "success": True,
            "fetched_count": len(orders),
            "date_range": {
                "from_date": from_date,
                "to_date": to_date
            },
            "orders": orders
        }

        if process_orders:
            response_data["processed_for_printing"] = {
                "count": len(processed_orders),
                "order_ids": processed_orders
            }

        return JSONResponse(content=response_data)

    except HTTPException:
        # Re-raise HTTP exceptions from fetch_wix_orders
        raise
    except Exception as e:
        logging.error(f"Unexpected error in fetch_orders_by_date_range: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching orders"
        )


@app.get('/orders/recent')
async def fetch_recent_orders(
    hours: int = Query(1, ge=1, le=168, description="Hours to look back (1-168 hours / 7 days)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of orders to retrieve"),
    process_orders: bool = Query(False, description="Whether to automatically process fetched orders for printing")
):
    """
    Convenience endpoint to fetch recent orders from the last N hours.
    """
    return await fetch_orders_by_date_range(
        hours_back=hours,
        limit=limit,
        process_orders=process_orders
    )


# --- Auto-Check Control Endpoints ---

@app.get('/auto-check/status')
async def get_auto_check_status():
    """Get the current status of the auto-check system."""
    global auto_check_running

    # Get recent auto-check statistics
    stats = {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total processed orders
        cursor.execute("SELECT COUNT(*) FROM auto_checked_orders WHERE processed_for_print = TRUE")
        stats['total_processed'] = cursor.fetchone()[0]

        # Orders processed today
        cursor.execute('''
            SELECT COUNT(*) FROM auto_checked_orders
            WHERE processed_for_print = TRUE AND date(checked_at) = date('now')
        ''')
        stats['processed_today'] = cursor.fetchone()[0]

        # Last check time
        cursor.execute('''
            SELECT MAX(checked_at) FROM auto_checked_orders
        ''')
        last_check = cursor.fetchone()[0]
        stats['last_check'] = last_check

        conn.close()
    except Exception as e:
        logging.error(f"Error getting auto-check stats: {e}")
        stats = {"error": "Could not retrieve statistics"}

    return {
        "enabled": AUTO_CHECK_ENABLED,
        "running": auto_check_running,
        "interval_seconds": AUTO_CHECK_INTERVAL,
        "hours_back": AUTO_CHECK_HOURS_BACK,
        "api_configured": bool(WIX_API_KEY and WIX_SITE_ID),
        "statistics": stats
    }


@app.post('/auto-check/start')
async def start_auto_check():
    """Manually start the auto-check system."""
    global auto_check_running

    if auto_check_running:
        return {"status": "already_running", "message": "Auto-check is already running"}

    if not (WIX_API_KEY and WIX_SITE_ID):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wix API credentials not configured"
        )

    await start_auto_check_task()
    return {"status": "started", "message": "Auto-check system started"}


@app.post('/auto-check/stop')
async def stop_auto_check():
    """Manually stop the auto-check system."""
    global auto_check_running

    if not auto_check_running:
        return {"status": "not_running", "message": "Auto-check is not running"}

    auto_check_running = False
    return {"status": "stopping", "message": "Auto-check system is stopping"}


# --- Health Check Endpoint ---
@app.get('/health')
def health_check():
    """A simple health check endpoint for the Cloudflare Tunnel."""
    return {"status": "ok"}

# --- Main Execution ---
if __name__ == '__main__':
    # Runs the FastAPI app using uvicorn on all available network interfaces on port 5000
    # This is what the Cloudflare Tunnel will connect to.
    logging.info("Starting FastAPI application with uvicorn on port 5000...")
    uvicorn.run(app, host='0.0.0.0', port=5000)

