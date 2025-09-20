"""
Offline Queue Manager for handling orders and print jobs during offline scenarios.
Provides persistent storage and priority-based processing for offline operations.
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .models import Order, PrintJob, PrintJobStatus
from .database import Database

logger = logging.getLogger(__name__)


class QueuePriority(Enum):
    """Queue priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class OfflineQueueStatus(Enum):
    """Offline queue status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class OfflineQueueItem:
    """Represents an item in the offline queue."""
    id: str
    item_type: str  # 'order' or 'print_job'
    item_id: str
    priority: QueuePriority
    status: OfflineQueueStatus
    created_at: datetime
    updated_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OfflineQueueManager:
    """
    Manager for handling offline queues and priority-based processing.
    Provides persistent storage and intelligent queue management.
    """
    
    def __init__(self, database: Database):
        """
        Initialize the offline queue manager.
        
        Args:
            database: Database instance for persistence
        """
        self.database = database
        self._initialize_offline_tables()
        
        # Configuration
        self.default_expiry_hours = 24  # Hours before items expire
        self.max_queue_size = 10000  # Maximum items in queue
        
        logger.info("Offline Queue Manager initialized")
    
    def _initialize_offline_tables(self):
        """Initialize offline queue tables in the database."""
        try:
            with self.database.get_connection() as conn:
                # Create offline_queue table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS offline_queue (
                        id TEXT PRIMARY KEY,
                        item_type TEXT NOT NULL,
                        item_id TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        expires_at TEXT,
                        error_message TEXT,
                        metadata TEXT
                    )
                """)
                
                # Create connectivity_events table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS connectivity_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        component TEXT NOT NULL,
                        status TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        duration_offline TEXT,
                        details TEXT
                    )
                """)
                
                # Create indices for efficient querying
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_offline_queue_status_priority 
                    ON offline_queue(status, priority DESC, created_at ASC)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_offline_queue_type_status 
                    ON offline_queue(item_type, status)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_connectivity_events_timestamp 
                    ON connectivity_events(timestamp DESC)
                """)
                
                conn.commit()
                logger.info("Offline queue tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing offline queue tables: {e}")
            raise
    
    def queue_order(self, order: Order, priority: QueuePriority = QueuePriority.NORMAL) -> bool:
        """
        Queue an order for offline processing.
        
        Args:
            order: Order to queue
            priority: Priority level for the order
            
        Returns:
            True if queued successfully, False otherwise
        """
        try:
            # Check queue size limit
            if self._get_queue_size() >= self.max_queue_size:
                logger.warning("Offline queue is full, cannot queue new order")
                return False
            
            # Create queue item
            queue_item = OfflineQueueItem(
                id=f"order_{order.id}_{datetime.now().timestamp()}",
                item_type="order",
                item_id=order.id,
                priority=priority,
                status=OfflineQueueStatus.QUEUED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=self.default_expiry_hours),
                metadata={"order_total": order.total_amount, "customer_id": order.customer.id if order.customer else None}
            )
            
            # Save to database
            if self._save_queue_item(queue_item):
                logger.info(f"Order {order.id} queued for offline processing with priority {priority.name}")
                return True
            else:
                logger.error(f"Failed to queue order {order.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error queuing order {order.id}: {e}")
            return False
    
    def queue_print_job(self, print_job: PrintJob, priority: QueuePriority = QueuePriority.NORMAL) -> bool:
        """
        Queue a print job for offline processing.
        
        Args:
            print_job: Print job to queue
            priority: Priority level for the print job
            
        Returns:
            True if queued successfully, False otherwise
        """
        try:
            # Check queue size limit
            if self._get_queue_size() >= self.max_queue_size:
                logger.warning("Offline queue is full, cannot queue new print job")
                return False
            
            # Create queue item
            queue_item = OfflineQueueItem(
                id=f"print_job_{print_job.id}_{datetime.now().timestamp()}",
                item_type="print_job",
                item_id=print_job.id,
                priority=priority,
                status=OfflineQueueStatus.QUEUED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=self.default_expiry_hours),
                metadata={"job_type": print_job.job_type, "order_id": print_job.order_id}
            )
            
            # Save to database
            if self._save_queue_item(queue_item):
                logger.info(f"Print job {print_job.id} queued for offline processing with priority {priority.name}")
                return True
            else:
                logger.error(f"Failed to queue print job {print_job.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error queuing print job {print_job.id}: {e}")
            return False
    
    def get_next_items(self, item_type: Optional[str] = None, limit: int = 10) -> List[OfflineQueueItem]:
        """
        Get next items from the queue for processing.
        
        Args:
            item_type: Optional filter by item type ('order' or 'print_job')
            limit: Maximum number of items to return
            
        Returns:
            List of queue items ordered by priority and creation time
        """
        try:
            with self.database.get_connection() as conn:
                # Build query
                query = """
                    SELECT * FROM offline_queue 
                    WHERE status = ? AND (expires_at IS NULL OR expires_at > ?)
                """
                params = [OfflineQueueStatus.QUEUED.value, datetime.now().isoformat()]
                
                if item_type:
                    query += " AND item_type = ?"
                    params.append(item_type)
                
                query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_queue_item(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting next queue items: {e}")
            return []
    
    def update_item_status(self, item_id: str, status: OfflineQueueStatus, error_message: Optional[str] = None) -> bool:
        """
        Update the status of a queue item.
        
        Args:
            item_id: Queue item ID
            status: New status
            error_message: Optional error message
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    UPDATE offline_queue 
                    SET status = ?, updated_at = ?, error_message = ?
                    WHERE id = ?
                """, (status.value, datetime.now().isoformat(), error_message, item_id))
                
                conn.commit()
                
                if conn.total_changes > 0:
                    logger.debug(f"Updated queue item {item_id} status to {status.value}")
                    return True
                else:
                    logger.warning(f"No queue item found with ID {item_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating queue item status: {e}")
            return False
    
    def increment_retry_count(self, item_id: str) -> bool:
        """
        Increment the retry count for a queue item.
        
        Args:
            item_id: Queue item ID
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    UPDATE offline_queue 
                    SET retry_count = retry_count + 1, updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), item_id))
                
                conn.commit()
                return conn.total_changes > 0
                
        except Exception as e:
            logger.error(f"Error incrementing retry count: {e}")
            return False
    
    def remove_item(self, item_id: str) -> bool:
        """
        Remove an item from the queue.
        
        Args:
            item_id: Queue item ID
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            with self.database.get_connection() as conn:
                conn.execute("DELETE FROM offline_queue WHERE id = ?", (item_id,))
                conn.commit()
                
                if conn.total_changes > 0:
                    logger.debug(f"Removed queue item {item_id}")
                    return True
                else:
                    logger.warning(f"No queue item found with ID {item_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing queue item: {e}")
            return False
    
    def cleanup_expired_items(self) -> int:
        """
        Remove expired items from the queue.
        
        Returns:
            Number of items removed
        """
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM offline_queue 
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                """, (datetime.now().isoformat(),))
                
                conn.commit()
                removed_count = cursor.rowcount
                
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} expired queue items")
                
                return removed_count
                
        except Exception as e:
            logger.error(f"Error cleaning up expired items: {e}")
            return 0
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the offline queue.
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            with self.database.get_connection() as conn:
                # Count by status
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM offline_queue 
                    GROUP BY status
                """)
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Count by type
                cursor = conn.execute("""
                    SELECT item_type, COUNT(*) as count 
                    FROM offline_queue 
                    GROUP BY item_type
                """)
                type_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Count by priority
                cursor = conn.execute("""
                    SELECT priority, COUNT(*) as count 
                    FROM offline_queue 
                    GROUP BY priority
                """)
                priority_counts = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Get oldest item
                cursor = conn.execute("""
                    SELECT MIN(created_at) FROM offline_queue WHERE status = ?
                """, (OfflineQueueStatus.QUEUED.value,))
                oldest_item = cursor.fetchone()[0]
                
                return {
                    "total_items": sum(status_counts.values()),
                    "status_counts": status_counts,
                    "type_counts": type_counts,
                    "priority_counts": priority_counts,
                    "oldest_queued_item": oldest_item,
                    "max_queue_size": self.max_queue_size
                }
                
        except Exception as e:
            logger.error(f"Error getting queue statistics: {e}")
            return {"error": str(e)}
    
    def log_connectivity_event(self, event_type: str, component: str, status: str, 
                             duration_offline: Optional[str] = None, details: Optional[Dict] = None) -> bool:
        """
        Log a connectivity event.
        
        Args:
            event_type: Type of connectivity event
            component: Component that changed (printer, internet)
            status: New status
            duration_offline: Optional duration offline
            details: Optional additional details
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            import json
            
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO connectivity_events 
                    (event_type, component, status, timestamp, duration_offline, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event_type,
                    component,
                    status,
                    datetime.now().isoformat(),
                    duration_offline,
                    json.dumps(details) if details else None
                ))
                
                conn.commit()
                logger.debug(f"Logged connectivity event: {event_type} for {component}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging connectivity event: {e}")
            return False
    
    def get_connectivity_events(self, limit: int = 100, component: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent connectivity events.
        
        Args:
            limit: Maximum number of events to return
            component: Optional filter by component
            
        Returns:
            List of connectivity events
        """
        try:
            import json
            
            with self.database.get_connection() as conn:
                query = "SELECT * FROM connectivity_events"
                params = []
                
                if component:
                    query += " WHERE component = ?"
                    params.append(component)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    event = {
                        "id": row[0],
                        "event_type": row[1],
                        "component": row[2],
                        "status": row[3],
                        "timestamp": row[4],
                        "duration_offline": row[5],
                        "details": json.loads(row[6]) if row[6] else None
                    }
                    events.append(event)
                
                return events
                
        except Exception as e:
            logger.error(f"Error getting connectivity events: {e}")
            return []
    
    def _save_queue_item(self, item: OfflineQueueItem) -> bool:
        """Save a queue item to the database."""
        try:
            import json
            
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO offline_queue 
                    (id, item_type, item_id, priority, status, created_at, updated_at, 
                     retry_count, max_retries, expires_at, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id,
                    item.item_type,
                    item.item_id,
                    item.priority.value,
                    item.status.value,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                    item.retry_count,
                    item.max_retries,
                    item.expires_at.isoformat() if item.expires_at else None,
                    item.error_message,
                    json.dumps(item.metadata) if item.metadata else None
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving queue item: {e}")
            return False
    
    def _row_to_queue_item(self, row) -> OfflineQueueItem:
        """Convert database row to OfflineQueueItem."""
        import json
        
        return OfflineQueueItem(
            id=row[0],
            item_type=row[1],
            item_id=row[2],
            priority=QueuePriority(row[3]),
            status=OfflineQueueStatus(row[4]),
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            retry_count=row[7],
            max_retries=row[8],
            expires_at=datetime.fromisoformat(row[9]) if row[9] else None,
            error_message=row[10],
            metadata=json.loads(row[11]) if row[11] else None
        )
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for recovery operations.
        
        Returns:
            Dictionary with recovery-specific statistics
        """
        try:
            with self.database.get_connection() as conn:
                # Count items by priority for recovery planning
                cursor = conn.execute("""
                    SELECT priority, COUNT(*) as count 
                    FROM offline_queue 
                    WHERE status = ? 
                    GROUP BY priority 
                    ORDER BY priority DESC
                """, (OfflineQueueStatus.QUEUED.value,))
                priority_distribution = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Get oldest queued items for recovery urgency
                cursor = conn.execute("""
                    SELECT MIN(created_at), MAX(created_at), AVG(retry_count)
                    FROM offline_queue 
                    WHERE status = ?
                """, (OfflineQueueStatus.QUEUED.value,))
                row = cursor.fetchone()
                oldest_item = row[0]
                newest_item = row[1]
                avg_retry_count = row[2] or 0
                
                # Count items approaching expiration
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM offline_queue 
                    WHERE status = ? AND expires_at IS NOT NULL 
                    AND expires_at < datetime('now', '+1 hour')
                """, (OfflineQueueStatus.QUEUED.value,))
                expiring_soon = cursor.fetchone()[0]
                
                return {
                    "priority_distribution": priority_distribution,
                    "oldest_queued_item": oldest_item,
                    "newest_queued_item": newest_item,
                    "average_retry_count": round(avg_retry_count, 2),
                    "expiring_soon": expiring_soon,
                    "recovery_urgency": self._calculate_recovery_urgency(oldest_item, expiring_soon)
                }
                
        except Exception as e:
            logger.error(f"Error getting recovery statistics: {e}")
            return {"error": str(e)}
    
    def _calculate_recovery_urgency(self, oldest_item: Optional[str], expiring_soon: int) -> str:
        """Calculate recovery urgency level."""
        if not oldest_item:
            return "none"
        
        try:
            from datetime import datetime
            oldest_time = datetime.fromisoformat(oldest_item)
            age_hours = (datetime.now() - oldest_time).total_seconds() / 3600
            
            if expiring_soon > 0 or age_hours > 12:
                return "critical"
            elif age_hours > 6:
                return "high"
            elif age_hours > 2:
                return "medium"
            else:
                return "low"
        except:
            return "unknown"
    
    def get_batch_for_recovery(self, batch_size: int = 10, priority_filter: Optional[QueuePriority] = None) -> List[OfflineQueueItem]:
        """
        Get a batch of items optimized for recovery processing.
        
        Args:
            batch_size: Maximum number of items to return
            priority_filter: Optional priority filter
            
        Returns:
            List of queue items optimized for recovery
        """
        try:
            with self.database.get_connection() as conn:
                query = """
                    SELECT * FROM offline_queue 
                    WHERE status = ? AND (expires_at IS NULL OR expires_at > ?)
                """
                params = [OfflineQueueStatus.QUEUED.value, datetime.now().isoformat()]
                
                if priority_filter:
                    query += " AND priority = ?"
                    params.append(priority_filter.value)
                
                # Order by priority (desc), then by created_at (asc) for FIFO within priority
                query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
                params.append(batch_size)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [self._row_to_queue_item(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting recovery batch: {e}")
            return []
    
    def mark_batch_processing(self, item_ids: List[str]) -> bool:
        """
        Mark a batch of items as processing atomically.
        
        Args:
            item_ids: List of item IDs to mark as processing
            
        Returns:
            True if all items were marked successfully
        """
        try:
            with self.database.get_connection() as conn:
                # Use transaction for atomic batch update
                conn.execute("BEGIN TRANSACTION")
                
                for item_id in item_ids:
                    conn.execute("""
                        UPDATE offline_queue 
                        SET status = ?, updated_at = ?
                        WHERE id = ? AND status = ?
                    """, (
                        OfflineQueueStatus.PROCESSING.value,
                        datetime.now().isoformat(),
                        item_id,
                        OfflineQueueStatus.QUEUED.value
                    ))
                
                conn.execute("COMMIT")
                
                # Check if all items were updated
                updated_count = sum(1 for _ in item_ids if conn.total_changes > 0)
                success = updated_count == len(item_ids)
                
                if success:
                    logger.debug(f"Marked {len(item_ids)} items as processing")
                else:
                    logger.warning(f"Only {updated_count}/{len(item_ids)} items marked as processing")
                
                return success
                
        except Exception as e:
            logger.error(f"Error marking batch as processing: {e}")
            try:
                conn.execute("ROLLBACK")
            except:
                pass
            return False
    
    def _get_queue_size(self) -> int:
        """Get current queue size."""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM offline_queue")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return 0
