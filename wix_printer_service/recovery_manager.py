"""
Recovery Manager for automatic system recovery and queue processing.
Handles intelligent recovery workflows when connectivity is restored.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from .connectivity_monitor import ConnectivityEvent, ConnectivityEventType, ConnectivityStatus
from .offline_queue import OfflineQueueManager, OfflineQueueStatus, QueuePriority
from .models import PrintJob, PrintJobStatus

logger = logging.getLogger(__name__)


class RecoveryPhase(Enum):
    """Recovery operation phases."""
    IDLE = "idle"
    VALIDATION = "validation"
    PROCESSING = "processing"
    COMPLETION = "completion"
    FAILED = "failed"


class RecoveryType(Enum):
    """Types of recovery operations."""
    PRINTER_RECOVERY = "printer_recovery"
    INTERNET_RECOVERY = "internet_recovery"
    COMBINED_RECOVERY = "combined_recovery"
    MANUAL_RECOVERY = "manual_recovery"


@dataclass
class RecoverySession:
    """Represents a recovery session."""
    id: str
    recovery_type: RecoveryType
    phase: RecoveryPhase
    started_at: datetime
    updated_at: datetime
    items_total: int = 0
    items_processed: int = 0
    items_failed: int = 0
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class RecoveryManager:
    """
    Manager for automatic recovery operations when connectivity is restored.
    Handles intelligent recovery workflows and duplicate prevention.
    """
    
    def __init__(self, offline_queue: OfflineQueueManager, print_manager=None):
        """
        Initialize the recovery manager.
        
        Args:
            offline_queue: Offline queue manager instance
            print_manager: Optional print manager for job processing
        """
        self.offline_queue = offline_queue
        self.print_manager = print_manager
        self._running = False
        self._recovery_thread = None
        self._stop_event = threading.Event()
        
        # Current recovery session
        self._current_session: Optional[RecoverySession] = None
        self._session_lock = threading.Lock()
        
        # Configuration
        self.batch_size = 5  # Jobs per batch
        self.batch_delay = 2.0  # Seconds between batches
        self.max_retry_attempts = 3
        self.validation_timeout = 30  # Seconds for validation phase
        
        # Recovery callbacks
        self._recovery_callbacks: List[Callable[[RecoverySession], None]] = []
        
        logger.info("Recovery Manager initialized")
    
    def start(self):
        """Start the recovery manager."""
        if self._running:
            logger.warning("Recovery Manager is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        logger.info("Recovery Manager started")
    
    def stop(self):
        """Stop the recovery manager."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        # Wait for current recovery to complete
        if self._recovery_thread and self._recovery_thread.is_alive():
            logger.info("Waiting for current recovery to complete...")
            self._recovery_thread.join(timeout=30)
        
        logger.info("Recovery Manager stopped")
    
    def add_recovery_callback(self, callback: Callable[[RecoverySession], None]):
        """
        Add a callback function for recovery session updates.
        
        Args:
            callback: Function to call when recovery sessions are updated
        """
        self._recovery_callbacks.append(callback)
        logger.debug(f"Added recovery callback: {callback.__name__}")
    
    def handle_connectivity_event(self, event: ConnectivityEvent):
        """
        Handle connectivity events and trigger recovery if needed.
        
        Args:
            event: Connectivity event from the monitor
        """
        if not self._running:
            return
        
        try:
            # Determine if recovery is needed
            should_recover = self._should_trigger_recovery(event)
            
            if should_recover:
                recovery_type = self._determine_recovery_type(event)
                logger.info(f"Triggering {recovery_type.value} due to connectivity event: {event.event_type.value}")
                
                # Start recovery in background thread
                self._start_recovery_async(recovery_type, event)
            
        except Exception as e:
            logger.error(f"Error handling connectivity event: {e}")
    
    def _should_trigger_recovery(self, event: ConnectivityEvent) -> bool:
        """
        Determine if a recovery should be triggered based on the event.
        
        Args:
            event: Connectivity event
            
        Returns:
            True if recovery should be triggered
        """
        # Only trigger on "online" events
        if event.event_type not in [
            ConnectivityEventType.PRINTER_ONLINE,
            ConnectivityEventType.INTERNET_ONLINE,
            ConnectivityEventType.CONNECTIVITY_RESTORED
        ]:
            return False
        
        # Don't trigger if already recovering
        with self._session_lock:
            if self._current_session and self._current_session.phase in [
                RecoveryPhase.VALIDATION, RecoveryPhase.PROCESSING
            ]:
                logger.debug("Recovery already in progress, skipping trigger")
                return False
        
        # Check if there are items to recover
        queue_stats = self.offline_queue.get_queue_statistics()
        queued_items = queue_stats.get("status_counts", {}).get("queued", 0)
        
        if queued_items == 0:
            logger.debug("No queued items to recover")
            return False
        
        return True
    
    def _determine_recovery_type(self, event: ConnectivityEvent) -> RecoveryType:
        """
        Determine the type of recovery based on the event.
        
        Args:
            event: Connectivity event
            
        Returns:
            Recovery type
        """
        if event.event_type == ConnectivityEventType.PRINTER_ONLINE:
            return RecoveryType.PRINTER_RECOVERY
        elif event.event_type == ConnectivityEventType.INTERNET_ONLINE:
            return RecoveryType.INTERNET_RECOVERY
        elif event.event_type == ConnectivityEventType.CONNECTIVITY_RESTORED:
            return RecoveryType.COMBINED_RECOVERY
        else:
            return RecoveryType.MANUAL_RECOVERY
    
    def _start_recovery_async(self, recovery_type: RecoveryType, trigger_event: ConnectivityEvent):
        """
        Start recovery operation in a background thread.
        
        Args:
            recovery_type: Type of recovery to perform
            trigger_event: Event that triggered the recovery
        """
        if self._recovery_thread and self._recovery_thread.is_alive():
            logger.warning("Recovery thread already running, cannot start new recovery")
            return
        
        self._recovery_thread = threading.Thread(
            target=self._execute_recovery,
            args=(recovery_type, trigger_event),
            daemon=True
        )
        self._recovery_thread.start()
    
    def _execute_recovery(self, recovery_type: RecoveryType, trigger_event: ConnectivityEvent):
        """
        Execute the recovery operation.
        
        Args:
            recovery_type: Type of recovery to perform
            trigger_event: Event that triggered the recovery
        """
        session_id = f"{recovery_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Create recovery session
            session = RecoverySession(
                id=session_id,
                recovery_type=recovery_type,
                phase=RecoveryPhase.VALIDATION,
                started_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={
                    "trigger_event": trigger_event.event_type.value,
                    "trigger_component": trigger_event.component
                }
            )
            
            with self._session_lock:
                self._current_session = session
            
            self._fire_recovery_callback(session)
            
            # Phase 1: Validation
            logger.info(f"Starting recovery session {session_id} - Phase 1: Validation")
            if not self._validate_recovery_conditions(session):
                self._complete_recovery_with_error(session, "Validation failed")
                return
            
            # Phase 2: Processing
            logger.info(f"Recovery session {session_id} - Phase 2: Processing")
            self._update_session_phase(session, RecoveryPhase.PROCESSING)
            
            if not self._process_recovery_queue(session):
                self._complete_recovery_with_error(session, "Processing failed")
                return
            
            # Phase 3: Completion
            logger.info(f"Recovery session {session_id} - Phase 3: Completion")
            self._update_session_phase(session, RecoveryPhase.COMPLETION)
            self._complete_recovery_successfully(session)
            
        except Exception as e:
            logger.error(f"Error in recovery execution: {e}")
            if session:
                self._complete_recovery_with_error(session, str(e))
    
    def _validate_recovery_conditions(self, session: RecoverySession) -> bool:
        """
        Validate conditions for recovery.
        
        Args:
            session: Recovery session
            
        Returns:
            True if validation passes
        """
        try:
            # Get items to recover
            items = self.offline_queue.get_next_items(item_type="print_job", limit=1000)
            session.items_total = len(items)
            
            if session.items_total == 0:
                logger.info("No items to recover")
                return True
            
            # Validate print manager availability for printer recovery
            if session.recovery_type in [RecoveryType.PRINTER_RECOVERY, RecoveryType.COMBINED_RECOVERY]:
                if not self.print_manager:
                    logger.error("Print manager not available for printer recovery")
                    return False
                
                # Check if printer is actually available
                if hasattr(self.print_manager, '_ensure_printer_ready'):
                    if not self.print_manager._ensure_printer_ready():
                        logger.error("Printer not ready for recovery")
                        return False
            
            logger.info(f"Validation passed: {session.items_total} items ready for recovery")
            self._update_session(session)
            return True
            
        except Exception as e:
            logger.error(f"Error in recovery validation: {e}")
            return False
    
    def _process_recovery_queue(self, session: RecoverySession) -> bool:
        """
        Process the recovery queue in batches.
        
        Args:
            session: Recovery session
            
        Returns:
            True if processing succeeds
        """
        try:
            processed_count = 0
            failed_count = 0
            
            while processed_count < session.items_total and not self._stop_event.is_set():
                # Get next batch
                remaining = session.items_total - processed_count
                batch_size = min(self.batch_size, remaining)
                
                items = self.offline_queue.get_next_items(item_type="print_job", limit=batch_size)
                
                if not items:
                    logger.info("No more items to process")
                    break
                
                # Process batch
                batch_failed = self._process_recovery_batch(items, session)
                
                processed_count += len(items)
                failed_count += batch_failed
                
                # Update session progress
                session.items_processed = processed_count
                session.items_failed = failed_count
                session.updated_at = datetime.now()
                self._fire_recovery_callback(session)
                
                logger.info(f"Recovery progress: {processed_count}/{session.items_total} processed, {failed_count} failed")
                
                # Rate limiting between batches
                if processed_count < session.items_total:
                    time.sleep(self.batch_delay)
            
            # Final update
            session.items_processed = processed_count
            session.items_failed = failed_count
            self._update_session(session)
            
            success_rate = (processed_count - failed_count) / processed_count if processed_count > 0 else 1.0
            logger.info(f"Recovery processing completed: {processed_count} processed, {failed_count} failed, {success_rate:.2%} success rate")
            
            return success_rate > 0.5  # Consider successful if >50% success rate
            
        except Exception as e:
            logger.error(f"Error in recovery processing: {e}")
            return False
    
    def _process_recovery_batch(self, items: List, session: RecoverySession) -> int:
        """
        Process a batch of recovery items.
        
        Args:
            items: List of offline queue items
            session: Recovery session
            
        Returns:
            Number of failed items in the batch
        """
        failed_count = 0
        
        for item in items:
            try:
                # Update item status to processing
                self.offline_queue.update_item_status(item.id, OfflineQueueStatus.PROCESSING)
                
                # Process the item based on type
                if item.item_type == "print_job":
                    success = self._process_print_job_recovery(item, session)
                else:
                    logger.warning(f"Unknown item type for recovery: {item.item_type}")
                    success = False
                
                if success:
                    # Remove from offline queue
                    self.offline_queue.remove_item(item.id)
                    logger.debug(f"Successfully recovered item {item.item_id}")
                else:
                    # Mark as failed or retry
                    if item.retry_count >= item.max_retries:
                        self.offline_queue.update_item_status(
                            item.id, 
                            OfflineQueueStatus.FAILED, 
                            "Max retries exceeded during recovery"
                        )
                        failed_count += 1
                        logger.warning(f"Item {item.item_id} failed recovery after {item.retry_count} retries")
                    else:
                        # Increment retry count and reset to queued
                        self.offline_queue.increment_retry_count(item.id)
                        self.offline_queue.update_item_status(item.id, OfflineQueueStatus.QUEUED)
                        logger.debug(f"Item {item.item_id} will be retried (attempt {item.retry_count + 1})")
                
            except Exception as e:
                logger.error(f"Error processing recovery item {item.id}: {e}")
                failed_count += 1
                
                # Mark item as failed
                self.offline_queue.update_item_status(
                    item.id, 
                    OfflineQueueStatus.FAILED, 
                    f"Recovery processing error: {str(e)}"
                )
        
        return failed_count
    
    def _process_print_job_recovery(self, queue_item, session: RecoverySession) -> bool:
        """
        Process recovery of a print job.
        
        Args:
            queue_item: Offline queue item
            session: Recovery session
            
        Returns:
            True if processing succeeds
        """
        try:
            if not self.print_manager:
                logger.error("Print manager not available for print job recovery")
                return False
            
            # Get the actual print job from database
            with self.offline_queue.database.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM print_jobs WHERE id = ?", (queue_item.item_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"Print job {queue_item.item_id} not found in database")
                    return False
                
                print_job = self.offline_queue.database._row_to_print_job(row)
                
                # Check for duplicate prevention
                if print_job.status == PrintJobStatus.COMPLETED:
                    logger.info(f"Print job {print_job.id} already completed, skipping")
                    return True
                
                # Process the print job
                if hasattr(self.print_manager, '_print_job_content'):
                    success = self.print_manager._print_job_content(print_job)
                    
                    if success:
                        # Update print job status
                        print_job.status = PrintJobStatus.COMPLETED
                        print_job.printed_at = datetime.now()
                        print_job.error_message = None
                        self.offline_queue.database.save_print_job(print_job)
                        
                        logger.info(f"Successfully recovered print job {print_job.id}")
                        return True
                    else:
                        logger.warning(f"Failed to process print job {print_job.id}")
                        return False
                else:
                    logger.error("Print manager does not support _print_job_content method")
                    return False
                
        except Exception as e:
            logger.error(f"Error in print job recovery: {e}")
            return False
    
    def _update_session_phase(self, session: RecoverySession, phase: RecoveryPhase):
        """Update session phase and fire callbacks."""
        session.phase = phase
        session.updated_at = datetime.now()
        self._fire_recovery_callback(session)
    
    def _update_session(self, session: RecoverySession):
        """Update session timestamp and fire callbacks."""
        session.updated_at = datetime.now()
        self._fire_recovery_callback(session)
    
    def _complete_recovery_successfully(self, session: RecoverySession):
        """Complete recovery session successfully."""
        session.phase = RecoveryPhase.COMPLETION
        session.completed_at = datetime.now()
        session.updated_at = datetime.now()
        
        with self._session_lock:
            self._current_session = None
        
        self._fire_recovery_callback(session)
        
        # Log recovery completion
        self.offline_queue.log_connectivity_event(
            event_type="recovery_completed",
            component="recovery_manager",
            status="completed",
            details={
                "session_id": session.id,
                "recovery_type": session.recovery_type.value,
                "items_total": session.items_total,
                "items_processed": session.items_processed,
                "items_failed": session.items_failed,
                "duration_seconds": (session.completed_at - session.started_at).total_seconds()
            }
        )
        
        logger.info(f"Recovery session {session.id} completed successfully")
    
    def _complete_recovery_with_error(self, session: RecoverySession, error_message: str):
        """Complete recovery session with error."""
        session.phase = RecoveryPhase.FAILED
        session.error_message = error_message
        session.completed_at = datetime.now()
        session.updated_at = datetime.now()
        
        with self._session_lock:
            self._current_session = None
        
        self._fire_recovery_callback(session)
        
        # Log recovery failure
        self.offline_queue.log_connectivity_event(
            event_type="recovery_failed",
            component="recovery_manager",
            status="failed",
            details={
                "session_id": session.id,
                "recovery_type": session.recovery_type.value,
                "error_message": error_message,
                "items_processed": session.items_processed,
                "items_failed": session.items_failed
            }
        )
        
        logger.error(f"Recovery session {session.id} failed: {error_message}")
    
    def _fire_recovery_callback(self, session: RecoverySession):
        """Fire recovery callbacks."""
        for callback in self._recovery_callbacks:
            try:
                callback(session)
            except Exception as e:
                logger.error(f"Error in recovery callback: {e}")
    
    def get_current_session(self) -> Optional[RecoverySession]:
        """Get current recovery session."""
        with self._session_lock:
            return self._current_session
    
    def trigger_manual_recovery(self, recovery_type: RecoveryType = RecoveryType.MANUAL_RECOVERY) -> bool:
        """
        Manually trigger a recovery operation.
        
        Args:
            recovery_type: Type of recovery to perform
            
        Returns:
            True if recovery was triggered successfully
        """
        if not self._running:
            logger.error("Recovery manager is not running")
            return False
        
        # Check if already recovering
        with self._session_lock:
            if self._current_session and self._current_session.phase in [
                RecoveryPhase.VALIDATION, RecoveryPhase.PROCESSING
            ]:
                logger.warning("Recovery already in progress")
                return False
        
        # Create dummy trigger event
        from .connectivity_monitor import ConnectivityEvent, ConnectivityEventType, ConnectivityStatus
        trigger_event = ConnectivityEvent(
            event_type=ConnectivityEventType.CONNECTIVITY_RESTORED,
            timestamp=datetime.now(),
            component="manual",
            status=ConnectivityStatus.ONLINE
        )
        
        logger.info(f"Manually triggering {recovery_type.value}")
        self._start_recovery_async(recovery_type, trigger_event)
        return True
