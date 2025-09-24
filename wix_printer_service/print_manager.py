"""
Print Manager service for processing print jobs.
Handles automatic processing of pending print jobs and status updates.
"""
import asyncio
import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import threading
import time

from .database import Database
from .printer_client import PrinterClient, PrinterStatus, PrinterError
from .models import PrintJob, PrintJobStatus
from .receipt_formatter import ReceiptType
from .offline_queue import OfflineQueueManager, OfflineQueueStatus
from .recovery_manager import RecoveryManager
from .notification_service import NotificationService, NotificationConfig
from .retry_manager import RetryManager, FailureType
from .health_monitor import HealthMonitor
from .circuit_breaker import get_circuit_breaker, printer_circuit_breaker

logger = logging.getLogger(__name__)


class PrintManager:
    """
    Service for managing print jobs and printer operations.
    Handles automatic processing of pending jobs and status management.
    """
    
    def __init__(self, database: Database, printer_client: PrinterClient, connectivity_monitor=None):
        """
        Initialize the print manager.
        
        Args:
            database: Database instance for job persistence
            printer_client: Printer client for hardware communication
            connectivity_monitor: Optional connectivity monitor for offline detection
        """
        self.database = database
        self.printer_client = printer_client
        self.connectivity_monitor = connectivity_monitor
        self.offline_queue = OfflineQueueManager(database)
        self.recovery_manager = RecoveryManager(self.offline_queue, self)
        self.notification_service = self._initialize_notification_service()
        
        # Self-Healing Components
        self.retry_manager = RetryManager(database)
        self.health_monitor = HealthMonitor(database, self.notification_service)
        self.printer_circuit_breaker = printer_circuit_breaker("main_printer")
        
        self._running = False
        self._worker_thread = None
        self._stop_event = threading.Event()
        
        # Configuration
        self.poll_interval = 5  # seconds between job checks
        self.max_retry_attempts = 3
        self.retry_delay = 30  # seconds between retries
        self.offline_mode = False
        
        # Setup integrations
        if self.connectivity_monitor:
            self.connectivity_monitor.add_event_callback(self.recovery_manager.handle_connectivity_event)
            if self.notification_service:
                self.connectivity_monitor.add_event_callback(self.notification_service.handle_connectivity_event)
        
        # Setup recovery manager callbacks
        if self.notification_service:
            self.recovery_manager.add_recovery_callback(self._handle_recovery_notification)
        
        # Setup health monitor callbacks
        self.health_monitor.add_event_callback(self._handle_health_event)
        
        logger.info("Print Manager initialized with Self-Healing capabilities")
    
    def start(self):
        """Start the print manager background processing."""
        if self._running:
            logger.warning("Print Manager is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info(f"!!! PRINT MANAGER WORKER THREAD LAUNCHED (Thread ID: {self._worker_thread.ident}) !!!")
        
        # Start recovery manager
        self.recovery_manager.start()
        
        # Start self-healing components
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            
            # Start notification service
            if self.notification_service:
                loop.create_task(self.notification_service.start())
            
            # Start retry manager
            loop.create_task(self.retry_manager.start())
            
            # Start health monitor
            loop.create_task(self.health_monitor.start())
            
        except RuntimeError:
            # No event loop running, will be started later
            logger.warning("No async event loop running, self-healing components will start later")
        
        logger.info("Print Manager started with Self-Healing capabilities")
    
    def stop(self):
        """Stop the print manager background processing."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        
        # Stop recovery manager
        self.recovery_manager.stop()
        
        # Stop self-healing components
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            
            # Stop notification service
            if self.notification_service:
                loop.create_task(self.notification_service.stop())
            
            # Stop retry manager
            loop.create_task(self.retry_manager.stop())
            
            # Stop health monitor
            loop.create_task(self.health_monitor.stop())
            
        except RuntimeError:
            pass
        
        logger.info("Print Manager stopped")
    
    def _worker_loop(self):
        """Main worker loop for processing print jobs."""
        # Give the main application a moment to fully start up
        time.sleep(5)
        
        while self._running and not self._stop_event.is_set():
            try:
                self._process_pending_jobs()
            except Exception as e:
                logger.error(f"Error in print manager worker loop: {e}")
            
            # Wait for next iteration or stop signal
            self._stop_event.wait(timeout=self.poll_interval)
        
        logger.info("Print Manager worker loop stopped")
    
    def _process_pending_jobs(self):
        """Process all pending print jobs."""
        try:
            # Check if printer is online
            printer_online = self._ensure_printer_ready()
            
            if printer_online:
                # Process regular pending jobs
                pending_jobs = self.database.get_pending_print_jobs()
                
                if pending_jobs:
                    logger.info(f"Processing {len(pending_jobs)} pending print jobs")
                    
                    for job in pending_jobs:
                        if self._stop_event.is_set():
                            break
                        self._process_single_job(job)
                
                # Process offline queue when printer comes back online
                self._process_offline_queue()
            else:
                # Printer is offline, move pending jobs to offline queue
                self._handle_printer_offline()
                
        except Exception as e:
            logger.error(f"Error processing pending jobs: {e}")
    
    def _process_offline_queue(self):
        """Process items from the offline queue when printer is available."""
        try:
            # Get all items from the offline queue
            all_items = self.offline_queue.get_next_items(limit=10)
            
            # Filter for print jobs
            queue_items = [item for item in all_items if item.item_type == "print_job"]

            if not queue_items:
                return

            logger.info(f"Processing {len(queue_items)} print jobs from offline queue")

            for queue_item in queue_items:
                if self._stop_event.is_set():
                    break
                
                # Update queue item status to processing
                self.offline_queue.update_item_status(queue_item.id, OfflineQueueStatus.PROCESSING)
                
                try:
                    # Get the actual print job from database
                    with self.database.get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT * FROM print_jobs WHERE id = %s", (queue_item.item_id,)
                            )
                            row = cursor.fetchone()
                        
                        if row:
                            print_job = self.database._row_to_print_job(row)
                            
                            # Process the print job
                            success = self._print_job_content(print_job)
                            
                            if success:
                                # Mark print job as completed
                                print_job.status = PrintJobStatus.COMPLETED
                                print_job.printed_at = datetime.now()
                                print_job.error_message = None
                                self.database.save_print_job(print_job)
                                
                                # Remove from offline queue
                                self.offline_queue.remove_item(queue_item.id)
                                logger.info(f"Completed offline print job {print_job.id}")
                            else:
                                # Handle failure
                                self._handle_offline_job_failure(queue_item, print_job)
                        else:
                            # Print job not found, remove from queue
                            self.offline_queue.remove_item(queue_item.id)
                            logger.warning(f"Print job {queue_item.item_id} not found, removed from queue")
                            
                except Exception as e:
                    logger.error(f"Error processing offline queue item {queue_item.id}: {e}")
                    self._handle_offline_job_failure(queue_item, None, str(e))
                    
        except Exception as e:
            logger.error(f"Error processing offline queue: {e}")
    
    def _handle_printer_offline(self):
        """Handle printer offline scenario by moving jobs to offline queue."""
        try:
            # Get pending print jobs
            pending_jobs = self.database.get_pending_print_jobs()
            
            if not pending_jobs:
                return
            
            logger.info(f"Moving {len(pending_jobs)} pending jobs to offline queue")
            
            for job in pending_jobs:
                # Queue the print job for offline processing
                if self.offline_queue.queue_print_job(job):
                    logger.debug(f"Moved print job {job.id} to offline queue")
                else:
                    logger.error(f"Failed to move print job {job.id} to offline queue")
                    
        except Exception as e:
            logger.error(f"Error handling printer offline: {e}")
    
    def _handle_offline_job_failure(self, queue_item, print_job=None, error_message=None):
        """
        Handle failure of an offline queue job.
        
        Args:
            queue_item: The offline queue item
            print_job: Optional print job instance
            error_message: Optional error message
        """
        try:
            # Increment retry count
            self.offline_queue.increment_retry_count(queue_item.id)
            
            if queue_item.retry_count >= queue_item.max_retries:
                # Max retries reached, mark as failed
                self.offline_queue.update_item_status(
                    queue_item.id, 
                    OfflineQueueStatus.FAILED, 
                    error_message or "Max retries exceeded"
                )
                
                if print_job:
                    print_job.status = PrintJobStatus.FAILED
                    print_job.error_message = error_message or "Max retries exceeded"
                    self.database.save_print_job(print_job)
                
                logger.error(f"Offline print job {queue_item.item_id} failed after {queue_item.retry_count} attempts")
            else:
                # Reset to queued for retry
                self.offline_queue.update_item_status(
                    queue_item.id, 
                    OfflineQueueStatus.QUEUED, 
                    error_message
                )
                logger.warning(f"Offline print job {queue_item.item_id} failed, will retry (attempt {queue_item.retry_count + 1}/{queue_item.max_retries})")
                
        except Exception as e:
            logger.error(f"Error handling offline job failure: {e}")
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """
        Get current recovery status information.
        
        Returns:
            Dictionary with recovery status details
        """
        try:
            current_session = self.recovery_manager.get_current_session()
            recovery_stats = self.offline_queue.get_recovery_statistics()
            
            status = {
                "recovery_manager_running": self.recovery_manager._running,
                "current_session": None,
                "queue_statistics": recovery_stats,
                "last_recovery": None
            }
            
            if current_session:
                status["current_session"] = {
                    "id": current_session.id,
                    "type": current_session.recovery_type.value,
                    "phase": current_session.phase.value,
                    "started_at": current_session.started_at.isoformat(),
                    "items_total": current_session.items_total,
                    "items_processed": current_session.items_processed,
                    "items_failed": current_session.items_failed,
                    "progress_percentage": (current_session.items_processed / current_session.items_total * 100) if current_session.items_total > 0 else 0
                }
            
            # Get last recovery from connectivity events
            recent_events = self.offline_queue.get_connectivity_events(limit=10, component="recovery_manager")
            recovery_events = [e for e in recent_events if e["event_type"] in ["recovery_completed", "recovery_failed"]]
            
            if recovery_events:
                last_event = recovery_events[0]
                status["last_recovery"] = {
                    "timestamp": last_event["timestamp"],
                    "status": "completed" if last_event["event_type"] == "recovery_completed" else "failed",
                    "details": last_event["details"]
                }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting recovery status: {e}")
            return {"error": str(e)}
    
    def trigger_manual_recovery(self, recovery_type: str = "manual") -> Dict[str, Any]:
        """
        Trigger a manual recovery operation.
        
        Args:
            recovery_type: Type of recovery to trigger
            
        Returns:
            Dictionary with operation result
        """
        try:
            from .recovery_manager import RecoveryType
            
            # Map string to enum
            type_mapping = {
                "manual": RecoveryType.MANUAL_RECOVERY,
                "printer": RecoveryType.PRINTER_RECOVERY,
                "internet": RecoveryType.INTERNET_RECOVERY,
                "combined": RecoveryType.COMBINED_RECOVERY
            }
            
            recovery_enum = type_mapping.get(recovery_type.lower(), RecoveryType.MANUAL_RECOVERY)
            
            success = self.recovery_manager.trigger_manual_recovery(recovery_enum)
            
            if success:
                return {
                    "status": "success",
                    "message": f"Manual {recovery_type} recovery triggered successfully",
                    "recovery_type": recovery_enum.value
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to trigger manual recovery",
                    "recovery_type": recovery_enum.value
                }
                
        except Exception as e:
            logger.error(f"Error triggering manual recovery: {e}")
            return {
                "status": "error",
                "message": f"Error triggering manual recovery: {str(e)}"
            }
    
    def _initialize_notification_service(self) -> Optional[NotificationService]:
        """Initialize the notification service with configuration."""
        try:
            import os
            
            # Check if notifications are enabled
            if not os.getenv("NOTIFICATION_ENABLED", "false").lower() == "true":
                logger.info("Notification service is disabled")
                return None
            
            # Create notification configuration from environment
            config = NotificationConfig(
                smtp_server=os.getenv("SMTP_SERVER", ""),
                smtp_port=int(os.getenv("SMTP_PORT", "587")),
                smtp_username=os.getenv("SMTP_USERNAME", ""),
                smtp_password=os.getenv("SMTP_PASSWORD", ""),
                smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
                from_email=os.getenv("NOTIFICATION_FROM_EMAIL", ""),
                to_emails=os.getenv("NOTIFICATION_TO_EMAILS", "").split(",") if os.getenv("NOTIFICATION_TO_EMAILS") else [],
                enabled=True
            )
            
            # Validate configuration
            if not config.smtp_server or not config.smtp_username or not config.to_emails:
                logger.warning("Notification service configuration incomplete, disabling notifications")
                return None
            
            # Create notification service
            notification_service = NotificationService(config, self.database)
            logger.info("Notification service initialized successfully")
            return notification_service
            
        except Exception as e:
            logger.error(f"Failed to initialize notification service: {e}")
            return None
    
    def _handle_recovery_notification(self, recovery_session):
        """Handle recovery session updates for notifications."""
        if not self.notification_service:
            return
        
        try:
            import asyncio
            from .recovery_manager import RecoveryPhase
            
            # Send notification for completed or failed recovery
            if recovery_session.phase == RecoveryPhase.COMPLETION:
                session_data = {
                    "session_id": recovery_session.id,
                    "items_processed": recovery_session.items_processed,
                    "items_failed": recovery_session.items_failed,
                    "duration": (recovery_session.completed_at - recovery_session.started_at).total_seconds() if recovery_session.completed_at else 0
                }
                
                # Create task for async notification
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(
                        self.notification_service.send_recovery_notification(
                            recovery_session.recovery_type.value,
                            True,  # Success
                            session_data
                        )
                    )
                except RuntimeError:
                    # No event loop, skip notification
                    pass
            
            elif recovery_session.phase == RecoveryPhase.FAILED:
                session_data = {
                    "session_id": recovery_session.id,
                    "items_processed": recovery_session.items_processed,
                    "items_failed": recovery_session.items_failed,
                    "error_message": recovery_session.error_message or "Unknown error"
                }
                
                # Create task for async notification
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(
                        self.notification_service.send_recovery_notification(
                            recovery_session.recovery_type.value,
                            False,  # Failed
                            session_data
                        )
                    )
                except RuntimeError:
                    # No event loop, skip notification
                    pass
        
        except Exception as e:
            logger.error(f"Error handling recovery notification: {e}")
    
    async def send_system_error_notification(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """
        Send a system error notification.
        
        Args:
            error_type: Type of system error
            error_message: Error message details
            context: Additional context information
        """
        if self.notification_service:
            await self.notification_service.send_system_error_notification(error_type, error_message, context)
    
    def get_notification_status(self) -> Dict[str, Any]:
        """
        Get notification service status.
        
        Returns:
            Dictionary with notification service status
        """
        if not self.notification_service:
            return {
                "enabled": False,
                "status": "disabled",
                "message": "Notification service not configured"
            }
        
        return self.notification_service.get_statistics()
    
    def _handle_health_event(self, health_event):
        """Handle health monitor events."""
        try:
            from .health_monitor import HealthStatus
            
            logger.info(f"Health event: {health_event.resource_type.value} changed from {health_event.old_status.value} to {health_event.new_status.value}")
            
            # Take action based on health event
            if health_event.new_status == HealthStatus.CRITICAL:
                # Critical health issue - consider service restart
                logger.warning(f"Critical health issue detected: {health_event.resource_type.value} at {health_event.metric_value:.1f}%")
                
                # Log self-healing event
                self._log_self_healing_event(
                    event_type="health_critical",
                    resource_type=health_event.resource_type.value,
                    details={
                        "metric_value": health_event.metric_value,
                        "old_status": health_event.old_status.value,
                        "new_status": health_event.new_status.value,
                        "action_taken": health_event.action_taken
                    }
                )
                
            elif health_event.new_status == HealthStatus.EMERGENCY:
                # Emergency health issue - immediate action required
                logger.error(f"Emergency health issue detected: {health_event.resource_type.value} at {health_event.metric_value:.1f}%")
                
                # Log self-healing event
                self._log_self_healing_event(
                    event_type="health_emergency",
                    resource_type=health_event.resource_type.value,
                    details={
                        "metric_value": health_event.metric_value,
                        "old_status": health_event.old_status.value,
                        "new_status": health_event.new_status.value,
                        "action_taken": health_event.action_taken
                    }
                )
                
                # Consider emergency actions like service restart
                # This would be implemented in Task 3 (Controlled Service Restart)
                
            elif health_event.old_status in [HealthStatus.CRITICAL, HealthStatus.EMERGENCY] and health_event.new_status == HealthStatus.HEALTHY:
                # Health recovered
                logger.info(f"Health recovered: {health_event.resource_type.value} back to healthy")
                
                # Log recovery event
                self._log_self_healing_event(
                    event_type="health_recovered",
                    resource_type=health_event.resource_type.value,
                    details={
                        "metric_value": health_event.metric_value,
                        "old_status": health_event.old_status.value,
                        "new_status": health_event.new_status.value
                    }
                )
        
        except Exception as e:
            logger.error(f"Error handling health event: {e}")
    
    def _log_self_healing_event(self, event_type: str, resource_type: str, details: dict):
        """Log self-healing events to database."""
        if not self.database:
            return
        
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO self_healing_events 
                    (event_type, resource_type, timestamp, details)
                    VALUES (?, ?, ?, ?)
                """, (
                    event_type,
                    resource_type,
                    datetime.now().isoformat(),
                    json.dumps(details) if details else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log self-healing event: {e}")
    
    async def print_job_with_retry(self, job: PrintJob) -> bool:
        """
        Print a job with intelligent retry and circuit breaker protection.
        
        Args:
            job: Print job to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use circuit breaker and retry manager for resilient printing
            result = await self.retry_manager.retry_operation(
                self._print_job_with_circuit_breaker,
                job,
                task_id=f"print_job_{job.id}",
                failure_type=FailureType.PRINTER_ERROR,
                metadata={"job_id": job.id, "order_id": job.order_id}
            )
            
            # Log successful self-healing print
            self._log_self_healing_event(
                event_type="print_job_success",
                resource_type="printer",
                details={
                    "job_id": job.id,
                    "order_id": job.order_id,
                    "retry_attempts": getattr(result, 'attempt_count', 0)
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to print job {job.id} after retries: {e}")
            
            # Log failed self-healing attempt
            self._log_self_healing_event(
                event_type="print_job_failed",
                resource_type="printer",
                details={
                    "job_id": job.id,
                    "order_id": job.order_id,
                    "error": str(e)
                }
            )
            
            return False
    
    def _print_job_with_circuit_breaker(self, job: PrintJob) -> bool:
        """Print job through circuit breaker protection."""
        return self.printer_circuit_breaker.call(self._print_job_direct, job)
    
    def _print_job_direct(self, job: PrintJob) -> bool:
        """Direct print job implementation."""
        # This would be the actual printing logic
        # For now, simulate the printing process
        if not self.printer_client.is_connected:
            raise ConnectionError("Printer not connected")
        
        # Simulate printing
        success = self.printer_client.print_receipt(job.receipt_data)
        if not success:
            raise Exception("Print job failed")
        
        return True
    
    def get_self_healing_status(self) -> Dict[str, Any]:
        """
        Get comprehensive self-healing system status.
        
        Returns:
            Dictionary with self-healing status information
        """
        try:
            return {
                "retry_manager": self.retry_manager.get_statistics(),
                "health_monitor": self.health_monitor.get_statistics(),
                "circuit_breakers": {
                    "printer": self.printer_circuit_breaker.get_statistics()
                },
                "notification_service": self.get_notification_status(),
                "recovery_manager": self.get_recovery_status(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting self-healing status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def trigger_self_healing_check(self) -> Dict[str, Any]:
        """
        Trigger immediate self-healing health check.
        
        Returns:
            Dictionary with check results
        """
        try:
            results = {}
            
            # Force health check
            health_results = await self.health_monitor.force_health_check()
            results["health_check"] = health_results
            
            # Get circuit breaker status
            results["circuit_breaker_status"] = self.printer_circuit_breaker.get_statistics()
            
            # Get retry manager status
            results["retry_manager_status"] = self.retry_manager.get_statistics()
            
            # Log self-healing check
            self._log_self_healing_event(
                event_type="manual_health_check",
                resource_type="system",
                details=results
            )
            
            return {
                "status": "success",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error during self-healing check: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_self_healing_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get self-healing event history.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of self-healing events
        """
        if not self.database:
            return []
        
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT event_type, resource_type, timestamp, details
                    FROM self_healing_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                events = []
                for row in cursor.fetchall():
                    events.append({
                        "event_type": row[0],
                        "resource_type": row[1],
                        "timestamp": row[2],
                        "details": json.loads(row[3]) if row[3] else {}
                    })
                
                return events
                
        except Exception as e:
            logger.error(f"Error getting self-healing history: {e}")
            return []
    
    def _ensure_printer_ready(self) -> bool:
        """
        Ensure printer is connected and ready.
        
        Returns:
            bool: True if printer is ready, False otherwise
        """
        try:
            # Connect if not already connected
            if not self.printer_client.is_connected:
                logger.info("Printer not connected. Attempting to connect...")
                if not self.printer_client.connect():
                    logger.error("Failed to connect to printer. Check USB connection and permissions.")
                    return False
                logger.info("Printer connected successfully.")
            
            # Check printer status
            status = self.printer_client.get_status()
            if status not in [PrinterStatus.ONLINE]:
                logger.warning(f"Printer not ready, status: {status.value}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking printer readiness: {e}")
            return False
    
    def _process_single_job(self, job: PrintJob):
        """
        Process a single print job.
        
        Args:
            job: PrintJob to process
        """
        try:
            # Self-healing: Ensure printer is ready before processing this specific job
            if not self._ensure_printer_ready():
                logger.warning(f"Printer not ready for job {job.id}, deferring.")
                # The job remains 'pending' and will be picked up in the next cycle.
                # We don't mark it as failed immediately, giving the connection a chance to recover.
                return

            logger.info(f"Processing print job {job.id} (type: {job.job_type})")
            
            # Update job status to printing
            job.status = PrintJobStatus.PRINTING
            job.updated_at = datetime.now()
            job.attempts += 1
            
            # Save status update
            self.database.save_print_job(job)
            
            # Attempt to print
            success = self._print_job_content(job)
            
            if success:
                # Mark as completed
                job.status = PrintJobStatus.COMPLETED
                job.printed_at = datetime.now()
                job.error_message = None
                logger.info(f"Print job {job.id} completed successfully")
            else:
                # Handle failure
                self._handle_job_failure(job)
            
            # Update job in database
            job.updated_at = datetime.now()
            self.database.save_print_job(job)
            
        except Exception as e:
            logger.error(f"Error processing print job {job.id}: {e}")
            self._handle_job_failure(job, str(e))
    
    def _print_job_content(self, job: PrintJob) -> bool:
        """
        Print the content of a job with layout validation.
        
        Args:
            job: PrintJob to print
            
        Returns:
            bool: True if printing successful, False otherwise
        """
        try:
            # Validate job content before printing
            if not self._validate_job_content(job):
                logger.error(f"Job content validation failed for job {job.id}")
                return False
            
            # Determine print method based on job type
            if job.job_type in ['kitchen', 'customer', 'driver']:
                # Use receipt printing for formatted receipts
                return self.printer_client.print_receipt(job.content)
            else:
                # Use text printing for other job types
                return self.printer_client.print_text(job.content)
                
        except Exception as e:
            logger.error(f"Error printing job content: {e}")
            return False
    
    def _validate_job_content(self, job: PrintJob) -> bool:
        """
        Validate print job content before printing.
        
        Args:
            job: PrintJob to validate
            
        Returns:
            bool: True if content is valid, False otherwise
        """
        try:
            # Check if content exists and is not empty
            if not job.content or not job.content.strip():
                logger.error(f"Job {job.id} has empty content")
                return False
            
            # Check for valid job type
            valid_job_types = [rt.value for rt in ReceiptType] + ['receipt', 'other']
            if job.job_type not in valid_job_types:
                logger.warning(f"Job {job.id} has unknown job type: {job.job_type}")
            
            # Basic content length check (avoid extremely large content)
            if len(job.content) > 10000:  # 10KB limit
                logger.warning(f"Job {job.id} has unusually large content ({len(job.content)} chars)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating job content: {e}")
            return False
    
    def _handle_job_failure(self, job: PrintJob, error_message: str = None):
        """
        Handle a failed print job.
        
        Args:
            job: Failed PrintJob
            error_message: Optional error message
        """
        job.error_message = error_message or "Print operation failed"
        
        if job.attempts >= job.max_attempts:
            # Max attempts reached, mark as failed
            job.status = PrintJobStatus.FAILED
            logger.error(f"Print job {job.id} failed after {job.attempts} attempts")
        else:
            # Reset to pending for retry
            job.status = PrintJobStatus.PENDING
            logger.warning(f"Print job {job.id} failed, will retry (attempt {job.attempts}/{job.max_attempts})")
    
    def process_job_immediately(self, job_id: str) -> bool:
        """
        Process a specific job immediately (manual trigger).
        
        Args:
            job_id: ID of the job to process
            
        Returns:
            bool: True if processing successful, False otherwise
        """
        try:
            # Get job from database
            with self.database.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM print_jobs WHERE id = ?", (job_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    logger.error(f"Print job {job_id} not found")
                    return False
                
                job = self.database._row_to_print_job(row)
            
            # Ensure printer is ready
            if not self._ensure_printer_ready():
                logger.error("Printer not ready for immediate job processing")
                return False
            
            # Process the job
            self._process_single_job(job)
            
            return job.status == PrintJobStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Error processing job {job_id} immediately: {e}")
            return False
    
    def get_job_statistics(self) -> dict:
        """
        Get statistics about print jobs.
        
        Returns:
            dict: Job statistics
        """
        try:
            with self.database.get_connection() as conn:
                # Count jobs by status
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM print_jobs 
                    GROUP BY status
                """)
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Get recent job counts (last 24 hours)
                yesterday = datetime.now() - timedelta(days=1)
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM print_jobs 
                    WHERE created_at > ?
                """, (yesterday.isoformat(),))
                recent_jobs = cursor.fetchone()[0]
                
                # Get failed jobs in last 24 hours
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM print_jobs 
                    WHERE status = 'failed' AND updated_at > ?
                """, (yesterday.isoformat(),))
                recent_failures = cursor.fetchone()[0]
                
                return {
                    'total_jobs': sum(status_counts.values()),
                    'pending_jobs': status_counts.get('pending', 0),
                    'completed_jobs': status_counts.get('completed', 0),
                    'failed_jobs': status_counts.get('failed', 0),
                    'recent_jobs_24h': recent_jobs,
                    'recent_failures_24h': recent_failures,
                    'printer_status': self.printer_client.get_status().value,
                    'printer_connected': self.printer_client.is_connected,
                    'manager_running': self._running
                }
                
        except Exception as e:
            logger.error(f"Error getting job statistics: {e}")
            return {
                'error': str(e),
                'printer_status': 'unknown',
                'printer_connected': False,
                'manager_running': self._running
            }
    
    def retry_failed_jobs(self) -> int:
        """
        Retry all failed jobs by resetting them to pending status.
        
        Returns:
            int: Number of jobs reset for retry
        """
        try:
            with self.database.get_connection() as conn:
                # Reset failed jobs to pending
                cursor = conn.execute("""
                    UPDATE print_jobs 
                    SET status = 'pending', 
                        attempts = 0, 
                        error_message = NULL,
                        updated_at = ?
                    WHERE status = 'failed'
                """, (datetime.now().isoformat(),))
                
                count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Reset {count} failed jobs for retry")
                return count
                
        except Exception as e:
            logger.error(f"Error retrying failed jobs: {e}")
            return 0
