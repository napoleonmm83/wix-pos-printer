"""
FastAPI application for the Wix Printer Service.
Provides REST API endpoints for monitoring and webhook handling.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..database import Database
from ..order_service import OrderService
from ..wix_client import WixClient
from ..printer_client import PrinterClient
from ..print_manager import PrintManager
from ..connectivity_monitor import ConnectivityMonitor
from ..offline_queue import OfflineQueueManager

logger = logging.getLogger(__name__)

# --- Pydantic Models for Request Bodies ---
class WixWebhookPayload(BaseModel):
    orderId: str = Field(..., description="The unique identifier for the Wix order.")

class WebhookData(BaseModel):
    data: WixWebhookPayload
    metadata: Optional[Dict[str, Any]] = None

# --- Dependency Injection Functions ---
global_instances = {}

def get_database() -> Database:
    if "database" not in global_instances:
        global_instances["database"] = Database()
    return global_instances["database"]

def get_order_service(db: Database = Depends(get_database)) -> OrderService:
    if "order_service" not in global_instances:
        global_instances["order_service"] = OrderService(db)
    return global_instances["order_service"]

def get_wix_client() -> Optional[WixClient]:
    if "wix_client" not in global_instances:
        try:
            global_instances["wix_client"] = WixClient()
        except Exception as e:
            logger.warning(f"Could not initialize Wix client: {e}")
            global_instances["wix_client"] = None
    return global_instances["wix_client"]

def get_print_manager(db: Database = Depends(get_database)) -> Optional[PrintManager]:
    # This function might need more dependencies if fully implemented
    if "print_manager" not in global_instances:
        # A placeholder for a real printer client is needed
        class MockPrinterClient:
            def is_connected(self): return False
        global_instances["print_manager"] = PrintManager(db, MockPrinterClient())
    return global_instances["print_manager"]


# --- FastAPI App Creation ---
def create_app():
    app = FastAPI(
        title="Wix Printer Service",
        description="Automated printing service for Wix orders on Raspberry Pi",
        version="1.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    @app.get("/health", tags=["Monitoring"], response_model=dict)
    def health_check():
        """Health check endpoint to confirm the service is running."""
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    @app.post("/webhook/orders", status_code=202, tags=["Webhooks"])
    def handle_wix_order_webhook(
        payload: WebhookData,
        order_service: OrderService = Depends(get_order_service),
        wix_client: Optional[WixClient] = Depends(get_wix_client)
    ):
        """Receives a webhook from Wix with an order ID, fetches details, and creates print jobs."""
        wix_order_id = payload.data.orderId
        logger.info(f"Received job request for Wix Order ID: {wix_order_id}")

        if not wix_client:
            raise HTTPException(status_code=503, detail="Wix client is not available.")

        try:
            # Fetch the full order data from Wix API
            order_data = wix_client.get_order(wix_order_id)
            if not order_data:
                raise HTTPException(status_code=404, detail=f"Order {wix_order_id} not found on Wix.")

            # Ingest the order using the order service
            result = order_service.ingest_order_from_api(order_data)
            
            if result.get("error"):
                logger.error(f"Failed to ingest order {wix_order_id}: {result.get('error')}")
                raise HTTPException(status_code=422, detail=result.get('error'))

            logger.info(f"Successfully processed job for order {wix_order_id}. Result: {result}")
            return {
                "message": "Job accepted and processed",
                "wix_order_id": wix_order_id,
                "jobs_created": result.get("created_jobs", 0),
                "was_existing": result.get("existing", False)
            }
        except HTTPException:
            raise  # Re-raise HTTP exceptions directly
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing job for order {wix_order_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred.")

    return app

app = create_app()