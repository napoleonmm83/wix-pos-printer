import hmac
import hashlib
import base64
import json
import logging
import os
from fastapi import FastAPI, Request, HTTPException, status, Form
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

# --- Security --- 
# IMPORTANT: Replace this with your actual secret key from the Wix dashboard
# You can also use an environment variable for better security
SECRET_KEY = os.environ.get("WIX_SECRET_KEY", "YOUR_WIX_WEBHOOK_SECRET_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/wix_printer.db")
PRINTER_SERVICE_URL = os.environ.get("PRINTER_SERVICE_URL", "http://localhost:8000")

# Helper to connect to the main service's database
def get_db_connection():
    # The database path is relative to the main service directory, not this app's directory.
    # We need to construct the correct path. Assuming this app runs from the same root.
    db_path = DATABASE_URL.split('///')[-1]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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

