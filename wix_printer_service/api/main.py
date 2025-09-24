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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Models for Request Bodies ---
class WixWebhookPayload(BaseModel):
    orderId: str = Field(..., description="The unique identifier for the Wix order.")

class WebhookData(BaseModel):
    data: WixWebhookPayload
    metadata: Optional[Dict[str, Any]] = None

# --- Singleton Dependency Management ---
# Use a dictionary to hold singleton instances of our services
global_instances: Dict[str, Any] = {}

def get_database() -> Database:
    """Dependency injection for Database."""
    if "database" not in global_instances:
        # Creating an instance of Database automatically initializes the schema.
        global_instances["database"] = Database()
    return global_instances["database"]

def get_printer_client() -> PrinterClient:
    """Dependency injection for PrinterClient."""
    if "printer_client" not in global_instances:
        logger.info("Creating and connecting PrinterClient singleton.")
        client = PrinterClient()
        if not client.connect():
            logger.error("Failed to connect to printer on startup.")
            # Depending on requirements, you might want to raise an exception
            # or handle this state gracefully. For now, we'll allow it to start
            # and let the PrintManager's retry logic handle it.
        global_instances["printer_client"] = client
    return global_instances["printer_client"]

def get_print_manager(
    db: Database = Depends(get_database),
    printer_client: PrinterClient = Depends(get_printer_client)
) -> PrintManager:
    """Dependency injection for PrintManager."""
    if "print_manager" not in global_instances:
        logger.info("Creating PrintManager singleton.")
        manager = PrintManager(database=db, printer_client=printer_client)
        global_instances["print_manager"] = manager
    return global_instances["print_manager"]

def get_order_service(
    db: Database = Depends(get_database),
    print_manager: PrintManager = Depends(get_print_manager)
) -> OrderService:
    """Dependency injection for OrderService."""
    if "order_service" not in global_instances:
        logger.info("Creating OrderService singleton.")
        # The OrderService now needs the PrintManager to create jobs
        global_instances["order_service"] = OrderService(db, print_manager)
    return global_instances["order_service"]

def get_wix_client() -> Optional[WixClient]:
    """Dependency injection for WixClient."""
    if "wix_client" not in global_instances:
        try:
            logger.info("Creating WixClient singleton.")
            global_instances["wix_client"] = WixClient()
        except Exception as e:
            logger.warning(f"Could not initialize Wix client: {e}")
            global_instances["wix_client"] = None
    return global_instances["wix_client"]


# --- FastAPI App Creation ---
def create_app():
    app = FastAPI(
        title="Wix Printer Service",
        description="Automated printing service for Wix orders on Raspberry Pi",
        version="1.2.0", # Incremented version
        docs_url="/docs",
        redoc_url="/redoc"
    )

    @app.on_event("startup")
    async def startup_event():
        """Initializes and starts background services."""
        logger.info("Application startup...")
        # Manually resolve dependencies to start them
        db = get_database()
        printer = get_printer_client()
        manager = get_print_manager(db, printer)
        
        # Start the print manager's background worker
        logger.info("Starting Print Manager background worker...")
        manager.start()
        logger.info("Startup complete.")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Stops background services gracefully."""
        logger.info("Application shutdown...")
        if "print_manager" in global_instances:
            logger.info("Stopping Print Manager...")
            global_instances["print_manager"].stop()
        if "printer_client" in global_instances:
            logger.info("Disconnecting PrinterClient...")
            global_instances["printer_client"].disconnect()
        logger.info("Shutdown complete.")

    @app.get("/health", tags=["Monitoring"], response_model=dict)
    def health_check(
        printer_client: PrinterClient = Depends(get_printer_client),
        print_manager: PrintManager = Depends(get_print_manager)
    ):
        """Health check endpoint to confirm the service is running."""
        printer_info = printer_client.get_printer_info()
        job_stats = print_manager.get_job_statistics()
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "printer": printer_info,
            "jobs": job_stats
        }

    @app.post("/jobs/wix", status_code=202, tags=["Jobs"])
    def queue_wix_order_job(
        payload: WebhookData,
        order_service: OrderService = Depends(get_order_service),
        wix_client: Optional[WixClient] = Depends(get_wix_client)
    ):
        """Receives an order ID, fetches details, and creates print jobs."""
        wix_order_id = payload.data.orderId
        logger.info(f"Received job request for Wix Order ID: {wix_order_id}")

        if not wix_client:
            raise HTTPException(status_code=503, detail="Wix client is not available.")

        try:
            # Fetch the full order data from Wix API
            order_data = wix_client.get_order(wix_order_id)
            if not order_data:
                raise HTTPException(status_code=404, detail=f"Order {wix_order_id} not found on Wix.")

            # Ingest the order using the order service.
            # This will now also create the print jobs via the PrintManager.
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
