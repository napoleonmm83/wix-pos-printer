import hmac
import hashlib
import base64
import json
import logging
import os
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
import uvicorn

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

# --- Security --- 
# IMPORTANT: Replace this with your actual secret key from the Wix dashboard
# You can also use an environment variable for better security
SECRET_KEY = os.environ.get("WIX_SECRET_KEY", "YOUR_WIX_WEBHOOK_SECRET_KEY")

def generate_signature(secret, body):
    """Generates the expected HMAC-SHA256 signature for a given request body."""
    hmac_digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return base64.b64encode(hmac_digest).decode('utf-8')

# --- Webhook Endpoint ---
@app.post('/webhook/orders')
async def handle_webhook(request: Request):
    """Receives, validates, and processes webhook events from Wix."""
    logging.info("Webhook endpoint hit. Starting validation...")
    
    # 1. Get Signature and Body
    signature = request.headers.get('x-wix-signature')
    raw_body = await request.body()

    # Log incoming data for debugging
    logging.info(f"Received Headers: {request.headers}")
    logging.info(f"Received Body: {raw_body.decode('utf-8')}")

    # 2. Validate Signature
    if not signature:
        logging.warning("Request is missing 'x-wix-signature' header.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")

    expected_signature = generate_signature(SECRET_KEY, raw_body)

    if not hmac.compare_digest(signature, expected_signature):
        logging.error(f"Invalid signature. Expected: '{expected_signature}', Got: '{signature}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    logging.info("Signature validation successful!")

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

