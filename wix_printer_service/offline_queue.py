"""
Offline Queue Manager for handling orders and print jobs during offline scenarios.
Provides persistent storage and priority-based processing for offline operations.
"""
import logging
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .models import Order, PrintJob
from .database import Database, DatabaseError

logger = logging.getLogger(__name__)

class QueuePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class OfflineQueueStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class OfflineQueueItem:
    id: int
    item_type: str
    item_id: str
    priority: int
    status: str
    created_at: datetime
    updated_at: datetime
    retry_count: int
    max_retries: int
    expires_at: Optional[datetime]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]]

class OfflineQueueManager:
    """Manager for handling offline queues for PostgreSQL."""
    
    def __init__(self, database: Database):
        self.database = database
        self._initialize_offline_tables()
        self.default_expiry_hours = 24
        self.max_queue_size = 10000
        logger.info("Offline Queue Manager initialized for PostgreSQL.")

    def _initialize_offline_tables(self):
        """Initialize offline queue tables in the database using PostgreSQL syntax."""
        try:
            with self.database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS offline_queue (
                            id SERIAL PRIMARY KEY,
                            item_type TEXT NOT NULL,
                            item_id TEXT NOT NULL,
                            priority INTEGER NOT NULL DEFAULT 2,
                            status TEXT NOT NULL DEFAULT 'queued',
                            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            retry_count INTEGER DEFAULT 0,
                            max_retries INTEGER DEFAULT 3,
                            expires_at TIMESTAMPTZ,
                            error_message TEXT,
                            metadata JSONB
                        );
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_offline_queue_status_priority ON offline_queue(status, priority DESC, created_at ASC);")
            logger.info("Offline queue tables initialized successfully.")
        except DatabaseError as e:
            logger.error(f"Error initializing offline queue tables: {e}")
            raise

    def queue_item(self, item_type: str, item_id: str, priority: QueuePriority, metadata: Optional[Dict] = None) -> bool:
        """A generic method to queue an item."""
        if self._get_queue_size() >= self.max_queue_size:
            logger.warning("Offline queue is full, cannot queue new item.")
            return False

        expires_at = datetime.utcnow() + timedelta(hours=self.default_expiry_hours)
        query = """
            INSERT INTO offline_queue 
            (item_type, item_id, priority, status, created_at, updated_at, expires_at, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        try:
            with self.database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (
                        item_type, item_id, priority.value, OfflineQueueStatus.QUEUED.value,
                        datetime.utcnow(), datetime.utcnow(), expires_at,
                        json.dumps(metadata) if metadata else None
                    ))
            logger.info(f"{item_type.capitalize()} {item_id} queued for offline processing with priority {priority.name}.")
            return True
        except DatabaseError as e:
            logger.error(f"Error queuing {item_type} {item_id}: {e}")
            return False

    def queue_order(self, order: Order, priority: QueuePriority = QueuePriority.NORMAL) -> bool:
        metadata = {"order_total": order.total_amount, "customer_id": order.customer.id if order.customer else None}
        return self.queue_item("order", order.id, priority, metadata)

    def queue_print_job(self, print_job: PrintJob, priority: QueuePriority = QueuePriority.NORMAL) -> bool:
        metadata = {"job_type": print_job.job_type, "order_id": print_job.order_id}
        return self.queue_item("print_job", print_job.id, priority, metadata)

    def get_next_items(self, limit: int = 10) -> List[OfflineQueueItem]:
        """Get next items from the queue for processing."""
        query = """
            SELECT * FROM offline_queue 
            WHERE status = %s AND (expires_at IS NULL OR expires_at > %s)
            ORDER BY priority DESC, created_at ASC LIMIT %s;
        """
        try:
            with self.database.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute(query, (OfflineQueueStatus.QUEUED.value, datetime.utcnow(), limit))
                    rows = cursor.fetchall()
                    return [self._row_to_queue_item(row) for row in rows]
        except DatabaseError as e:
            logger.error(f"Error getting next queue items: {e}")
            return []

    def _row_to_queue_item(self, row) -> OfflineQueueItem:
        """Converts a DB row to an OfflineQueueItem dataclass."""
        return OfflineQueueItem(**row)

    def _update_item(self, query: str, params: tuple) -> bool:
        try:
            with self.database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.rowcount > 0
        except DatabaseError as e:
            logger.error(f"Error updating queue item: {e}")
            return False

    def update_item_status(self, item_id: int, status: OfflineQueueStatus, error_message: Optional[str] = None) -> bool:
        query = "UPDATE offline_queue SET status = %s, updated_at = %s, error_message = %s WHERE id = %s;"
        return self._update_item(query, (status.value, datetime.utcnow(), error_message, item_id))

    def increment_retry_count(self, item_id: int) -> bool:
        query = "UPDATE offline_queue SET retry_count = retry_count + 1, updated_at = %s WHERE id = %s;"
        return self._update_item(query, (datetime.utcnow(), item_id))

    def remove_item(self, item_id: int) -> bool:
        return self._update_item("DELETE FROM offline_queue WHERE id = %s;", (item_id,))

    def _get_queue_size(self) -> int:
        """Get current queue size."""
        try:
            with self.database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM offline_queue")
                    return cursor.fetchone()[0]
        except DatabaseError as e:
            logger.error(f"Error getting queue size: {e}")
            return 0