"""
FastAPI application for the Wix Printer Service.
Provides REST API endpoints for monitoring and webhook handling.
"""
import os
import asyncio
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..database import Database
from ..order_service import OrderService
from ..wix_client import WixClient
from ..printer_client import PrinterClient
from ..print_manager import PrintManager
from ..connectivity_monitor import ConnectivityMonitor, ConnectivityEvent
from ..offline_queue import OfflineQueueManager
from ..webhook_validator import get_webhook_validator

# --- Background Tasks ---
POLLING_INTERVAL = 30  # seconds

async def poll_for_new_orders():
    """Periodically polls the Wix API for new orders."""
    logger.info(f"Starting background polling task every {POLLING_INTERVAL} seconds.")
    wix_client = get_wix_client()
    order_service = get_order_service()
    print_manager = get_print_manager()

    if not all([wix_client, order_service, print_manager]):
        logger.error("Polling task cannot start: one or more services are not configured.")
        return

    while True:
        try:
            logger.info("Polling task running...")
            recent_orders = wix_client.get_recent_orders(minutes_ago=5)
            
            if recent_orders:
                new_orders_found = 0
                for order_data in recent_orders:
                    wix_order_id = order_data.get('id')
                    if wix_order_id and not order_service.order_exists(wix_order_id):
                        logger.info(f"Polling found new order: {wix_order_id}")
                        new_orders_found += 1
                        # Ingest the order and create print jobs
                        order = order_service.ingest_order_from_api(order_data)
                        if order:
                            print_manager.create_print_jobs_for_order(order.id)
                
                if new_orders_found == 0:
                    logger.info("Polling complete. No new orders found.")

        except Exception as e:
            logger.error(f"Error during polling task: {e}")
        
        # Wait for the next interval
        await asyncio.sleep(POLLING_INTERVAL)

logger = logging.getLogger(__name__)

# Global instances
database = None
order_service = None
wix_client = None
printer_client = None
print_manager = None
connectivity_monitor = None
offline_queue = None


def get_database() -> Database:
    """Dependency to get database instance."""
    global database
    if database is None:
        database = Database()
    return database


def get_order_service() -> OrderService:
    """Dependency to get order service instance."""
    global order_service, database
    if order_service is None:
        if database is None:
            database = Database()
        order_service = OrderService(database)
    return order_service


def get_wix_client() -> WixClient:
    """Dependency to get Wix client instance."""
    global wix_client
    if wix_client is None:
        try:
            wix_client = WixClient()
        except Exception as e:
            logger.warning(f"Could not initialize Wix client: {e}")
            wix_client = None
    return wix_client


def get_printer_client() -> PrinterClient:
    """Dependency to get printer client instance."""
    global printer_client
    if printer_client is None:
        try:
            printer_client = PrinterClient()
        except Exception as e:
            logger.warning(f"Could not initialize printer client: {e}")
            printer_client = None
    return printer_client


def get_connectivity_monitor() -> ConnectivityMonitor:
    """Dependency to get connectivity monitor instance."""
    global connectivity_monitor, printer_client
    if connectivity_monitor is None:
        try:
            if printer_client is None:
                printer_client = PrinterClient()
            connectivity_monitor = ConnectivityMonitor(printer_client)
        except Exception as e:
            logger.warning(f"Could not initialize connectivity monitor: {e}")
            connectivity_monitor = None
    return connectivity_monitor


def get_offline_queue() -> OfflineQueueManager:
    """Dependency to get offline queue manager instance."""
    global offline_queue, database
    if offline_queue is None:
        try:
            if database is None:
                database = Database()
            offline_queue = OfflineQueueManager(database)
        except Exception as e:
            logger.warning(f"Could not initialize offline queue: {e}")
            offline_queue = None
    return offline_queue


def get_print_manager() -> PrintManager:
    """Dependency to get print manager instance."""
    global print_manager, database, printer_client, connectivity_monitor
    if print_manager is None:
        try:
            if database is None:
                database = Database()
            if printer_client is None:
                printer_client = PrinterClient()
            if connectivity_monitor is None:
                connectivity_monitor = ConnectivityMonitor(printer_client)
            print_manager = PrintManager(database, printer_client, connectivity_monitor)
        except Exception as e:
            logger.warning(f"Could not initialize print manager: {e}")
            print_manager = None
    return print_manager


from pydantic import BaseModel, Field\n\n# ... (existing imports)\n\n# Pydantic models for the request body\nclass WixWebhookPayload(BaseModel):\n    orderId: str = Field(..., description=\"The unique identifier for the Wix order.\")\n\nclass WebhookData(BaseModel):\n    data: WixWebhookPayload\n    metadata: Optional[Dict[str, Any]] = None\n\n# ... (existing code)\n\ndef create_app():\n    app = FastAPI(\n        title=\"Wix Printer Service\",\n        description=\"Automated printing service for Wix orders on Raspberry Pi\",\n        version=\"1.0.0\",\n        docs_url=\"/docs\",\n        redoc_url=\"/redoc\"\n    )\n\n    @app.get(\"/health\", tags=[\"Monitoring\"], response_model=dict)\n    def health_check():\n        \"\"\"\n        Health check endpoint to confirm the service is running and accessible.\n        \n        Returns:\n            dict: Status information with \"ok\" status\n        \"\"\"\n        logger.info(\"Health check requested\")\n        return {\"status\": \"ok\"}\n\n    @app.post(\"/jobs/wix\", status_code=202, tags=[\"Jobs\"])\n    def queue_wix_order_job(\n        payload: WebhookData,\n        order_service: OrderService = Depends(get_order_service),\n        wix_client: WixClient = Depends(get_wix_client)\n    ):\n        wix_order_id = payload.data.orderId\n        logger.info(f\"Received job request for Wix Order ID: {wix_order_id}\")\n\n        if not wix_client:\n            raise HTTPException(status_code=503, detail=\"Wix client is not available.\")\n\n        try:\n            # Fetch the full order data from Wix API\n            order_data = wix_client.get_order(wix_order_id)\n            if not order_data:\n                raise HTTPException(status_code=404, detail=f\"Order {wix_order_id} not found on Wix.\")\n\n            # Ingest the order using the order service\n            result = order_service.ingest_order_from_api(order_data)\n            \n            if result.get(\"error\"):\n                logger.error(f\"Failed to ingest order {wix_order_id}: {result.get(\'error\')}\")\n                raise HTTPException(status_code=422, detail=result.get(\'error\))\n\n            logger.info(f\"Successfully processed job for order {wix_order_id}. Result: {result}\")\n            return {\n                \"message\": \"Job accepted and processed\",\n                \"order_id\": result.get(\"order_id\"),\n                \"wix_order_id\": wix_order_id,\n                \"jobs_created\": result.get(\"created_jobs\", 0),\n                \"was_existing\": result.get(\"existing\", False)\n            }\n        except HTTPException:\n            raise # Re-raise HTTP exceptions directly\n        except Exception as e:\n            logger.error(f\"An unexpected error occurred while processing job for order {wix_order_id}: {e}\", exc_info=True)\n            raise HTTPException(status_code=500, detail=\"An internal error occurred.\")\n\n    return app

app = create_app()
