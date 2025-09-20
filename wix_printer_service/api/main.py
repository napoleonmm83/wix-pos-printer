"""
FastAPI application for the Wix Printer Service.
Provides REST API endpoints for monitoring and webhook handling.
"""
import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any

from ..database import Database
from ..order_service import OrderService
from ..wix_client import WixClient
from ..printer_client import PrinterClient
from ..print_manager import PrintManager
from ..connectivity_monitor import ConnectivityMonitor, ConnectivityEvent
from ..offline_queue import OfflineQueueManager

logger = logging.getLogger(__name__)

# Global instances
database = None
order_service = None
wix_client = None
printer_client = None
print_manager = None
connectivity_monitor = None
offline_queue = None

app = FastAPI(
    title="Wix Printer Service",
    description="Automated printing service for Wix orders on Raspberry Pi",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


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
            # Add event callback for logging
            connectivity_monitor.add_event_callback(_handle_connectivity_event)
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


def _handle_connectivity_event(event: ConnectivityEvent):
    """Handle connectivity events for logging and queue management."""
    try:
        # Log the connectivity event
        if offline_queue:
            offline_queue.log_connectivity_event(
                event_type=event.event_type.value,
                component=event.component,
                status=event.status.value,
                duration_offline=str(event.duration_offline) if event.duration_offline else None,
                details=event.details
            )
        
        logger.info(f"Connectivity event: {event.event_type.value} - {event.component} is {event.status.value}")
        
    except Exception as e:
        logger.error(f"Error handling connectivity event: {e}")


@app.get("/health", tags=["Monitoring"], response_model=dict)
def health_check():
    """
    Health check endpoint to confirm the service is running and accessible.
    
    Returns:
        dict: Status information with "ok" status
    """
    logger.info("Health check requested")
    return {"status": "ok"}


@app.post("/webhook/orders", tags=["Webhooks"])
async def webhook_orders(
    request: Request,
    order_service: OrderService = Depends(get_order_service),
    connectivity_monitor: ConnectivityMonitor = Depends(get_connectivity_monitor)
):
    """
    Webhook endpoint for receiving Wix order notifications.
    Handles both online and offline scenarios gracefully.
    
    Args:
        request: FastAPI request object containing webhook data
        order_service: Order service for processing orders
        connectivity_monitor: Connectivity monitor for offline detection
        
    Returns:
        dict: Processing result
    """
    try:
        # Validate webhook signature (basic implementation)
        signature = request.headers.get("X-Wix-Webhook-Signature")
        if not signature:
            logger.warning("Webhook received without signature")
            # In production, you might want to reject unsigned webhooks
            # raise HTTPException(status_code=401, detail="Missing webhook signature")
        
        # Parse JSON payload
        try:
            webhook_data = await request.json()
        except Exception as e:
            logger.error(f"Invalid JSON payload in webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        logger.info(f"Received webhook: {webhook_data.get('eventType', 'unknown')}")
        
        # Check if we're in offline mode
        if connectivity_monitor and not connectivity_monitor.is_internet_online():
            logger.info("Processing webhook in offline mode")
            order = order_service.process_offline_order(webhook_data)
        else:
            # Process normally
            order = order_service.process_webhook_order(webhook_data)
        
        if order:
            offline_status = " (offline mode)" if order_service.is_offline_mode() else ""
            return {
                "status": "success",
                "message": f"Order {order.id} processed successfully{offline_status}",
                "order_id": order.id,
                "offline_mode": order_service.is_offline_mode()
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to process order")
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/orders/{order_id}", tags=["Orders"])
def get_order(
    order_id: str,
    order_service: OrderService = Depends(get_order_service)
):
    """
    Retrieve an order by ID.
    
    Args:
        order_id: Order ID to retrieve
        order_service: Order service for data access
        
    Returns:
        dict: Order data or error message
    """
    try:
        order = order_service.get_order_by_id(order_id)
        
        if order:
            return {
                "status": "success",
                "order": order.to_dict()
            }
        else:
            raise HTTPException(status_code=404, detail="Order not found")
            
    except Exception as e:
        logger.error(f"Error retrieving order {order_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/status", tags=["Monitoring"])
def api_status(
    db: Database = Depends(get_database),
    wix_client: WixClient = Depends(get_wix_client),
    printer_client: PrinterClient = Depends(get_printer_client),
    print_manager: PrintManager = Depends(get_print_manager),
    connectivity_monitor: ConnectivityMonitor = Depends(get_connectivity_monitor)
):
    """
    Get detailed API status including database, Wix API, and printer connectivity.
    
    Returns:
        dict: Detailed status information
    """
    status = {
        "service": "running",
        "database": "unknown",
        "wix_api": "unknown",
        "printer": "unknown",
        "print_manager": "unknown",
        "connectivity": "unknown",
        "offline_mode": False
    }
    
    # Test database connection
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        status["database"] = "disconnected"
    
    # Test Wix API connection
    if wix_client:
        try:
            if wix_client.test_connection():
                status["wix_api"] = "connected"
            else:
                status["wix_api"] = "disconnected"
        except Exception as e:
            logger.error(f"Wix API connection test failed: {e}")
            status["wix_api"] = "error"
    else:
        status["wix_api"] = "not_configured"
    
    # Test printer connection
    if printer_client:
        try:
            printer_status = printer_client.get_status()
            status["printer"] = printer_status.value
            status["printer_info"] = printer_client.get_printer_info()
        except Exception as e:
            logger.error(f"Printer status check failed: {e}")
            status["printer"] = "error"
    else:
        status["printer"] = "not_configured"
    
    # Get print manager status
    if print_manager:
        try:
            status["print_manager"] = "running" if print_manager._running else "stopped"
            status["print_statistics"] = print_manager.get_job_statistics()
        except Exception as e:
            logger.error(f"Print manager status check failed: {e}")
            status["print_manager"] = "error"
    else:
        status["print_manager"] = "not_configured"
    
    # Get connectivity status
    if connectivity_monitor:
        try:
            connectivity_status = connectivity_monitor.get_status()
            status["connectivity"] = connectivity_status
            status["offline_mode"] = not connectivity_monitor.is_fully_online()
        except Exception as e:
            logger.error(f"Connectivity status check failed: {e}")
            status["connectivity"] = "error"
    else:
        status["connectivity"] = "not_configured"
    
    return status


@app.post("/print/job/{job_id}", tags=["Printing"])
def trigger_print_job(
    job_id: str,
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Manually trigger a specific print job.
    
    Args:
        job_id: ID of the print job to process
        print_manager: Print manager instance
        
    Returns:
        dict: Result of the print operation
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        success = print_manager.process_job_immediately(job_id)
        
        if success:
            return {
                "status": "success",
                "message": f"Print job {job_id} processed successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to process print job {job_id}")
            
    except Exception as e:
        logger.error(f"Error triggering print job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/print/statistics", tags=["Printing"])
def get_print_statistics(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get print job statistics.
    
    Returns:
        dict: Print job statistics
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return print_manager.get_job_statistics()
    except Exception as e:
        logger.error(f"Error getting print statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/print/retry-failed", tags=["Printing"])
def retry_failed_jobs(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Retry all failed print jobs.
    
    Returns:
        dict: Number of jobs reset for retry
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        count = print_manager.retry_failed_jobs()
        return {
            "status": "success",
            "message": f"Reset {count} failed jobs for retry"
        }
    except Exception as e:
        logger.error(f"Error retrying failed jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/connectivity/status", tags=["Connectivity"])
def get_connectivity_status(
    connectivity_monitor: ConnectivityMonitor = Depends(get_connectivity_monitor)
):
    """
    Get detailed connectivity status.
    
    Returns:
        dict: Connectivity status information
    """
    if not connectivity_monitor:
        raise HTTPException(status_code=503, detail="Connectivity monitor not available")
    
    try:
        return connectivity_monitor.get_status()
    except Exception as e:
        logger.error(f"Error getting connectivity status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/connectivity/check", tags=["Connectivity"])
def force_connectivity_check(
    connectivity_monitor: ConnectivityMonitor = Depends(get_connectivity_monitor)
):
    """
    Force an immediate connectivity check.
    
    Returns:
        dict: Updated connectivity status
    """
    if not connectivity_monitor:
        raise HTTPException(status_code=503, detail="Connectivity monitor not available")
    
    try:
        connectivity_monitor.force_check()
        return {
            "status": "success",
            "message": "Connectivity check completed",
            "connectivity": connectivity_monitor.get_status()
        }
    except Exception as e:
        logger.error(f"Error forcing connectivity check: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/offline/queue/status", tags=["Offline Queue"])
def get_offline_queue_status(
    offline_queue: OfflineQueueManager = Depends(get_offline_queue)
):
    """
    Get offline queue status and statistics.
    
    Returns:
        dict: Offline queue statistics
    """
    if not offline_queue:
        raise HTTPException(status_code=503, detail="Offline queue not available")
    
    try:
        return offline_queue.get_queue_statistics()
    except Exception as e:
        logger.error(f"Error getting offline queue status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/offline/queue/cleanup", tags=["Offline Queue"])
def cleanup_offline_queue(
    offline_queue: OfflineQueueManager = Depends(get_offline_queue)
):
    """
    Clean up expired items from the offline queue.
    
    Returns:
        dict: Cleanup results
    """
    if not offline_queue:
        raise HTTPException(status_code=503, detail="Offline queue not available")
    
    try:
        removed_count = offline_queue.cleanup_expired_items()
        return {
            "status": "success",
            "message": f"Cleaned up {removed_count} expired items",
            "removed_count": removed_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up offline queue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/connectivity/events", tags=["Connectivity"])
def get_connectivity_events(
    limit: int = 50,
    component: Optional[str] = None,
    offline_queue: OfflineQueueManager = Depends(get_offline_queue)
):
    """
    Get recent connectivity events.
    
    Args:
        limit: Maximum number of events to return
        component: Optional filter by component (printer, internet)
        offline_queue: Offline queue manager instance
        
    Returns:
        dict: List of connectivity events
    """
    if not offline_queue:
        raise HTTPException(status_code=503, detail="Offline queue not available")
    
    try:
        events = offline_queue.get_connectivity_events(limit=limit, component=component)
        return {
            "events": events,
            "count": len(events),
            "limit": limit,
            "component_filter": component
        }
    except Exception as e:
        logger.error(f"Error getting connectivity events: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/recovery/status", tags=["Recovery"])
def get_recovery_status(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get current recovery status and statistics.
    
    Returns:
        dict: Recovery status information
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return print_manager.get_recovery_status()
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/recovery/trigger", tags=["Recovery"])
def trigger_manual_recovery(
    recovery_type: str = "manual",
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Manually trigger a recovery operation.
    
    Args:
        recovery_type: Type of recovery (manual, printer, internet, combined)
        print_manager: Print manager instance
        
    Returns:
        dict: Recovery trigger result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        result = print_manager.trigger_manual_recovery(recovery_type)
        
        if result.get("status") == "success":
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("message", "Recovery trigger failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering manual recovery: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/recovery/history", tags=["Recovery"])
def get_recovery_history(
    limit: int = 20,
    offline_queue: OfflineQueueManager = Depends(get_offline_queue)
):
    """
    Get recovery operation history.
    
    Args:
        limit: Maximum number of recovery events to return
        offline_queue: Offline queue manager instance
        
    Returns:
        dict: Recovery history
    """
    if not offline_queue:
        raise HTTPException(status_code=503, detail="Offline queue not available")
    
    try:
        events = offline_queue.get_connectivity_events(limit=limit, component="recovery_manager")
        recovery_events = [e for e in events if e["event_type"] in ["recovery_completed", "recovery_failed", "recovery_started"]]
        
        return {
            "recovery_history": recovery_events,
            "count": len(recovery_events),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting recovery history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/recovery/pause", tags=["Recovery"])
def pause_recovery(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Pause current recovery operation.
    
    Returns:
        dict: Operation result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        current_session = print_manager.recovery_manager.get_current_session()
        
        if not current_session:
            raise HTTPException(status_code=400, detail="No active recovery session to pause")
        
        # For now, we'll just stop the recovery manager
        # In a more advanced implementation, we could add pause/resume functionality
        return {
            "status": "info",
            "message": "Recovery pause not implemented - use stop recovery instead",
            "current_session": current_session.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing recovery: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/recovery/statistics", tags=["Recovery"])
def get_recovery_statistics(
    offline_queue: OfflineQueueManager = Depends(get_offline_queue)
):
    """
    Get detailed recovery statistics and analytics.
    
    Returns:
        dict: Recovery statistics
    """
    if not offline_queue:
        raise HTTPException(status_code=503, detail="Offline queue not available")
    
    try:
        recovery_stats = offline_queue.get_recovery_statistics()
        queue_stats = offline_queue.get_queue_statistics()
        
        return {
            "recovery_statistics": recovery_stats,
            "queue_statistics": queue_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recovery statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/notifications/status", tags=["Notifications"])
def get_notification_status(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get notification service status and statistics.
    
    Returns:
        dict: Notification service status
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return print_manager.get_notification_status()
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/notifications/test", tags=["Notifications"])
async def test_notification_service(
    notification_type: str = "system_error",
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Test the notification service by sending a test email.
    
    Args:
        notification_type: Type of test notification to send
        print_manager: Print manager instance
        
    Returns:
        dict: Test result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    if not print_manager.notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")
    
    try:
        # Test SMTP connection first
        connection_test = await print_manager.notification_service.test_email_connection()
        
        if not connection_test["success"]:
            return {
                "status": "error",
                "message": "SMTP connection test failed",
                "details": connection_test
            }
        
        # Send test notification
        from ..notification_service import NotificationType
        
        test_context = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "restaurant_name": "Test Restaurant",
            "error_type": "Test Error",
            "error_message": "This is a test notification from the Wix Printer Service",
            "service_status": "TESTING",
            "printer_status": "online",
            "internet_status": "online",
            "queue_size": 0
        }
        
        if notification_type == "system_error":
            await print_manager.notification_service.send_notification(
                NotificationType.SYSTEM_ERROR, test_context
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown notification type: {notification_type}")
        
        return {
            "status": "success",
            "message": "Test notification sent successfully",
            "notification_type": notification_type,
            "smtp_test": connection_test
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing notification service: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/notifications/send", tags=["Notifications"])
async def send_manual_notification(
    notification_type: str,
    message: str,
    severity: str = "info",
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Send a manual notification.
    
    Args:
        notification_type: Type of notification
        message: Custom message
        severity: Notification severity (info, warning, high, critical)
        print_manager: Print manager instance
        
    Returns:
        dict: Send result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    if not print_manager.notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")
    
    try:
        # Send system error notification with custom message
        await print_manager.send_system_error_notification(
            error_type=f"Manual Notification ({severity.upper()})",
            error_message=message,
            context={
                "manual_notification": True,
                "severity": severity,
                "sent_by": "API"
            }
        )
        
        return {
            "status": "success",
            "message": "Manual notification sent successfully",
            "notification_type": notification_type,
            "severity": severity
        }
        
    except Exception as e:
        logger.error(f"Error sending manual notification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/notifications/history", tags=["Notifications"])
def get_notification_history(
    limit: int = 50,
    notification_type: Optional[str] = None,
    offline_queue: OfflineQueueManager = Depends(get_offline_queue)
):
    """
    Get notification history from database.
    
    Args:
        limit: Maximum number of notifications to return
        notification_type: Optional filter by notification type
        offline_queue: Offline queue manager instance
        
    Returns:
        dict: Notification history
    """
    if not offline_queue:
        raise HTTPException(status_code=503, detail="Offline queue not available")
    
    try:
        with offline_queue.database.get_connection() as conn:
            query = """
                SELECT notification_type, context, success, sent_at, created_at
                FROM notification_history
            """
            params = []
            
            if notification_type:
                query += " WHERE notification_type = ?"
                params.append(notification_type)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            notifications = []
            for row in rows:
                notifications.append({
                    "notification_type": row[0],
                    "context": json.loads(row[1]) if row[1] else {},
                    "success": bool(row[2]),
                    "sent_at": row[3],
                    "created_at": row[4]
                })
            
            return {
                "notifications": notifications,
                "count": len(notifications),
                "limit": limit,
                "notification_type_filter": notification_type
            }
    
    except Exception as e:
        logger.error(f"Error getting notification history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/notifications/config/test", tags=["Notifications"])
async def test_notification_config(
    smtp_server: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    smtp_use_tls: bool = True,
    test_email: str = ""
):
    """
    Test notification configuration without saving.
    
    Args:
        smtp_server: SMTP server hostname
        smtp_port: SMTP server port
        smtp_username: SMTP username
        smtp_password: SMTP password
        smtp_use_tls: Use TLS encryption
        test_email: Email address to send test to
        
    Returns:
        dict: Configuration test result
    """
    try:
        from ..notification_service import NotificationService, NotificationConfig
        
        # Create test configuration
        config = NotificationConfig(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_tls=smtp_use_tls,
            from_email=smtp_username,
            to_emails=[test_email] if test_email else [smtp_username],
            enabled=True
        )
        
        # Create temporary notification service
        test_service = NotificationService(config)
        
        # Test connection
        connection_result = await test_service.test_email_connection()
        
        if connection_result["success"] and test_email:
            # Send test email
            await test_service.start()
            
            test_context = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "restaurant_name": "Configuration Test",
                "error_type": "Configuration Test",
                "error_message": "This is a test email to verify your notification configuration.",
                "service_status": "TESTING",
                "printer_status": "unknown",
                "internet_status": "unknown",
                "queue_size": 0
            }
            
            from ..notification_service import NotificationType
            await test_service.send_notification(NotificationType.SYSTEM_ERROR, test_context)
            await test_service.stop()
            
            return {
                "status": "success",
                "message": "Configuration test successful and test email sent",
                "connection_test": connection_result,
                "test_email_sent": True,
                "test_email_recipient": test_email
            }
        
        return {
            "status": "success" if connection_result["success"] else "error",
            "message": "Configuration test completed",
            "connection_test": connection_result,
            "test_email_sent": False
        }
        
    except Exception as e:
        logger.error(f"Error testing notification configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration test failed: {str(e)}")


# Self-Healing API Endpoints
@app.get("/self-healing/status", tags=["Self-Healing"])
def get_self_healing_status(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get comprehensive self-healing system status.
    
    Returns:
        dict: Self-healing system status including retry manager, health monitor, and circuit breakers
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return print_manager.get_self_healing_status()
    except Exception as e:
        logger.error(f"Error getting self-healing status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/self-healing/trigger-check", tags=["Self-Healing"])
async def trigger_self_healing_check(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Trigger immediate self-healing health check.
    
    Returns:
        dict: Health check results
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return await print_manager.trigger_self_healing_check()
    except Exception as e:
        logger.error(f"Error triggering self-healing check: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/self-healing/history", tags=["Self-Healing"])
def get_self_healing_history(
    limit: int = 50,
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get self-healing event history.
    
    Args:
        limit: Maximum number of events to return
        print_manager: Print manager instance
        
    Returns:
        dict: Self-healing event history
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        events = print_manager.get_self_healing_history(limit)
        return {
            "events": events,
            "count": len(events),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting self-healing history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health/metrics", tags=["Self-Healing"])
def get_health_metrics(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get current health metrics for all monitored resources.
    
    Returns:
        dict: Current health metrics
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return print_manager.health_monitor.get_current_health()
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health/metrics/history", tags=["Self-Healing"])
def get_health_metrics_history(
    resource_type: Optional[str] = None,
    limit: int = 100,
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get health metrics history.
    
    Args:
        resource_type: Optional filter by resource type (memory, cpu, disk, threads)
        limit: Maximum number of metrics to return
        print_manager: Print manager instance
        
    Returns:
        dict: Health metrics history
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        from ..health_monitor import ResourceType
        
        resource_filter = None
        if resource_type:
            try:
                resource_filter = ResourceType(resource_type.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid resource type: {resource_type}")
        
        history = print_manager.health_monitor.get_health_history(resource_filter, limit)
        return {
            "history": history,
            "count": len(history),
            "resource_type_filter": resource_type,
            "limit": limit
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health metrics history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/circuit-breakers/status", tags=["Self-Healing"])
def get_circuit_breakers_status(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get status of all circuit breakers.
    
    Returns:
        dict: Circuit breaker status information
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        from ..circuit_breaker import _circuit_breaker_manager
        
        return {
            "circuit_breakers": _circuit_breaker_manager.get_statistics(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/circuit-breakers/{circuit_name}/reset", tags=["Self-Healing"])
def reset_circuit_breaker(
    circuit_name: str,
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Reset a specific circuit breaker to closed state.
    
    Args:
        circuit_name: Name of the circuit breaker to reset
        print_manager: Print manager instance
        
    Returns:
        dict: Reset operation result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        from ..circuit_breaker import _circuit_breaker_manager
        
        all_circuits = _circuit_breaker_manager.get_all_circuit_breakers()
        
        if circuit_name not in all_circuits:
            raise HTTPException(status_code=404, detail=f"Circuit breaker '{circuit_name}' not found")
        
        circuit = all_circuits[circuit_name]
        old_state = circuit.state.value
        circuit.reset()
        
        return {
            "status": "success",
            "message": f"Circuit breaker '{circuit_name}' reset successfully",
            "old_state": old_state,
            "new_state": circuit.state.value,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breaker {circuit_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/retry-manager/status", tags=["Self-Healing"])
def get_retry_manager_status(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get retry manager status and statistics.
    
    Returns:
        dict: Retry manager status
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        return print_manager.retry_manager.get_statistics()
    except Exception as e:
        logger.error(f"Error getting retry manager status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/retry-manager/dead-letter-queue", tags=["Self-Healing"])
def get_dead_letter_queue(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get dead letter queue contents.
    
    Returns:
        dict: Dead letter queue items
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        dead_tasks = print_manager.retry_manager.dead_letter_queue.get_tasks()
        
        return {
            "dead_letter_tasks": [
                {
                    "id": task.id,
                    "failure_type": task.failure_type.value,
                    "attempt_count": task.attempt_count,
                    "created_at": task.created_at.isoformat(),
                    "last_error": str(task.last_error) if task.last_error else None,
                    "metadata": task.metadata
                }
                for task in dead_tasks
            ],
            "count": len(dead_tasks),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting dead letter queue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/retry-manager/requeue/{task_id}", tags=["Self-Healing"])
def requeue_dead_letter_task(
    task_id: str,
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Requeue a task from the dead letter queue.
    
    Args:
        task_id: ID of the task to requeue
        print_manager: Print manager instance
        
    Returns:
        dict: Requeue operation result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        task = print_manager.retry_manager.dead_letter_queue.requeue_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in dead letter queue")
        
        # Queue the task for retry
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(print_manager.retry_manager.queue_retry(task))
        except RuntimeError:
            # No event loop running
            pass
        
        return {
            "status": "success",
            "message": f"Task '{task_id}' requeued successfully",
            "task": {
                "id": task.id,
                "failure_type": task.failure_type.value,
                "metadata": task.metadata
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requeuing task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/health/thresholds/update", tags=["Self-Healing"])
def update_health_thresholds(
    resource_type: str,
    warning_threshold: float,
    critical_threshold: float,
    emergency_threshold: float,
    check_interval: float = 30.0,
    enabled: bool = True,
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Update health monitoring thresholds for a resource type.
    
    Args:
        resource_type: Type of resource (memory, cpu, disk, threads)
        warning_threshold: Warning threshold percentage (0-100)
        critical_threshold: Critical threshold percentage (0-100)
        emergency_threshold: Emergency threshold percentage (0-100)
        check_interval: Check interval in seconds
        enabled: Whether monitoring is enabled for this resource
        print_manager: Print manager instance
        
    Returns:
        dict: Update operation result
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        from ..health_monitor import ResourceType, HealthThreshold
        
        # Validate resource type
        try:
            resource_enum = ResourceType(resource_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid resource type: {resource_type}")
        
        # Create new threshold configuration
        try:
            new_threshold = HealthThreshold(
                resource_type=resource_enum,
                warning_threshold=warning_threshold,
                critical_threshold=critical_threshold,
                emergency_threshold=emergency_threshold,
                check_interval=check_interval,
                enabled=enabled
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid threshold configuration: {str(e)}")
        
        # Update the threshold
        print_manager.health_monitor.update_threshold(resource_enum, new_threshold)
        
        return {
            "status": "success",
            "message": f"Health thresholds updated for {resource_type}",
            "resource_type": resource_type,
            "thresholds": {
                "warning": warning_threshold,
                "critical": critical_threshold,
                "emergency": emergency_threshold,
                "check_interval": check_interval,
                "enabled": enabled
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating health thresholds: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/self-healing/config", tags=["Self-Healing"])
def get_self_healing_config(
    print_manager: PrintManager = Depends(get_print_manager)
):
    """
    Get current self-healing system configuration.
    
    Returns:
        dict: Self-healing configuration
    """
    if not print_manager:
        raise HTTPException(status_code=503, detail="Print manager not available")
    
    try:
        health_stats = print_manager.health_monitor.get_statistics()
        retry_stats = print_manager.retry_manager.get_statistics()
        
        return {
            "health_monitor": {
                "thresholds": health_stats.get("thresholds", {}),
                "cleanup_handlers": health_stats.get("cleanup_handlers", {})
            },
            "retry_manager": {
                "default_configs": retry_stats.get("default_configs", {})
            },
            "circuit_breakers": {
                "printer": print_manager.printer_circuit_breaker.get_statistics().get("config", {})
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting self-healing config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Wix Printer Service API started")
    
    # Initialize database
    try:
        get_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # Initialize Wix client (optional)
    try:
        get_wix_client()
        logger.info("Wix client initialized successfully")
    except Exception as e:
        logger.warning(f"Wix client initialization failed: {e}")
    
    # Initialize printer client (optional)
    try:
        get_printer_client()
        logger.info("Printer client initialized successfully")
    except Exception as e:
        logger.warning(f"Printer client initialization failed: {e}")
    
    # Initialize and start connectivity monitor
    try:
        monitor = get_connectivity_monitor()
        if monitor:
            monitor.start()
            logger.info("Connectivity monitor started successfully")
    except Exception as e:
        logger.warning(f"Connectivity monitor initialization failed: {e}")
    
    # Initialize and start print manager
    try:
        manager = get_print_manager()
        if manager:
            manager.start()
            logger.info("Print manager started successfully")
    except Exception as e:
        logger.warning(f"Print manager initialization failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global database, wix_client, printer_client, print_manager, connectivity_monitor
    
    # Stop connectivity monitor
    if connectivity_monitor:
        connectivity_monitor.stop()
        logger.info("Connectivity monitor stopped")
    
    # Stop print manager
    if print_manager:
        print_manager.stop()
        logger.info("Print manager stopped")
    
    # Disconnect printer
    if printer_client:
        printer_client.disconnect()
        logger.info("Printer client disconnected")
    
    if database:
        database.close()
        logger.info("Database connection closed")
    
    if wix_client:
        wix_client.close()
        logger.info("Wix client session closed")
    
    logger.info("Wix Printer Service API shutting down")
