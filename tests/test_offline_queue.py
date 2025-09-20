"""
Unit tests for offline queue manager.
Tests queue management, priority handling, and persistence.
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from wix_printer_service.offline_queue import (
    OfflineQueueManager, QueuePriority, OfflineQueueStatus, OfflineQueueItem
)
from wix_printer_service.models import Order, PrintJob, OrderStatus, PrintJobStatus, CustomerInfo, DeliveryInfo
from wix_printer_service.database import Database


class TestOfflineQueueManager:
    """Test cases for the OfflineQueueManager class."""
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock(spec=Database)
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
        return mock_db
    
    @pytest.fixture
    def offline_queue(self, mock_database):
        """Create an offline queue manager instance."""
        with patch.object(OfflineQueueManager, '_initialize_offline_tables'):
            return OfflineQueueManager(mock_database)
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing."""
        customer = CustomerInfo(
            id="cust_1",
            email="test@example.com",
            first_name="John",
            last_name="Doe"
        )
        
        return Order(
            id="order_123",
            wix_order_id="wix_456",
            status=OrderStatus.PENDING,
            items=[],
            customer=customer,
            delivery=DeliveryInfo(),
            total_amount=25.50,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def sample_print_job(self):
        """Create a sample print job for testing."""
        return PrintJob(
            id="job_123",
            order_id="order_123",
            job_type="kitchen",
            status=PrintJobStatus.PENDING,
            content="Test receipt content"
        )
    
    def test_init(self, mock_database):
        """Test offline queue manager initialization."""
        with patch.object(OfflineQueueManager, '_initialize_offline_tables') as mock_init:
            queue = OfflineQueueManager(mock_database)
            
            assert queue.database == mock_database
            assert queue.default_expiry_hours == 24
            assert queue.max_queue_size == 10000
            mock_init.assert_called_once()
    
    def test_initialize_offline_tables(self, mock_database):
        """Test offline tables initialization."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        queue = OfflineQueueManager(mock_database)
        
        # Should have executed CREATE TABLE statements
        assert mock_conn.execute.call_count >= 5  # Tables and indices
        mock_conn.commit.assert_called()
    
    def test_queue_order_success(self, offline_queue, sample_order, mock_database):
        """Test successfully queuing an order."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Mock queue size check
        mock_conn.execute.return_value.fetchone.return_value = [0]  # Empty queue
        
        with patch.object(offline_queue, '_save_queue_item', return_value=True):
            result = offline_queue.queue_order(sample_order, QueuePriority.HIGH)
            
            assert result is True
    
    def test_queue_order_full_queue(self, offline_queue, sample_order):
        """Test queuing order when queue is full."""
        with patch.object(offline_queue, '_get_queue_size', return_value=10000):
            result = offline_queue.queue_order(sample_order)
            
            assert result is False
    
    def test_queue_order_save_failure(self, offline_queue, sample_order, mock_database):
        """Test queuing order with save failure."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = [0]  # Empty queue
        
        with patch.object(offline_queue, '_save_queue_item', return_value=False):
            result = offline_queue.queue_order(sample_order)
            
            assert result is False
    
    def test_queue_print_job_success(self, offline_queue, sample_print_job, mock_database):
        """Test successfully queuing a print job."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = [0]  # Empty queue
        
        with patch.object(offline_queue, '_save_queue_item', return_value=True):
            result = offline_queue.queue_print_job(sample_print_job, QueuePriority.NORMAL)
            
            assert result is True
    
    def test_get_next_items(self, offline_queue, mock_database):
        """Test getting next items from queue."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Mock database rows
        mock_rows = [
            ("item_1", "print_job", "job_1", 2, "queued", 
             datetime.now().isoformat(), datetime.now().isoformat(),
             0, 3, None, None, None),
            ("item_2", "order", "order_1", 3, "queued",
             datetime.now().isoformat(), datetime.now().isoformat(),
             0, 3, None, None, None)
        ]
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        
        items = offline_queue.get_next_items(limit=5)
        
        assert len(items) == 2
        assert all(isinstance(item, OfflineQueueItem) for item in items)
        assert items[0].item_type == "print_job"
        assert items[1].item_type == "order"
    
    def test_get_next_items_with_filter(self, offline_queue, mock_database):
        """Test getting next items with type filter."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = []
        
        offline_queue.get_next_items(item_type="print_job", limit=10)
        
        # Verify SQL query includes type filter
        call_args = mock_conn.execute.call_args
        assert "item_type = ?" in call_args[0][0]
        assert "print_job" in call_args[0][1]
    
    def test_update_item_status_success(self, offline_queue, mock_database):
        """Test updating item status successfully."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.total_changes = 1
        
        result = offline_queue.update_item_status("item_1", OfflineQueueStatus.COMPLETED)
        
        assert result is True
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()
    
    def test_update_item_status_not_found(self, offline_queue, mock_database):
        """Test updating status of non-existent item."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.total_changes = 0
        
        result = offline_queue.update_item_status("nonexistent", OfflineQueueStatus.COMPLETED)
        
        assert result is False
    
    def test_increment_retry_count(self, offline_queue, mock_database):
        """Test incrementing retry count."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.total_changes = 1
        
        result = offline_queue.increment_retry_count("item_1")
        
        assert result is True
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()
    
    def test_remove_item_success(self, offline_queue, mock_database):
        """Test removing item successfully."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.total_changes = 1
        
        result = offline_queue.remove_item("item_1")
        
        assert result is True
        mock_conn.execute.assert_called_with("DELETE FROM offline_queue WHERE id = ?", ("item_1",))
        mock_conn.commit.assert_called()
    
    def test_remove_item_not_found(self, offline_queue, mock_database):
        """Test removing non-existent item."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.total_changes = 0
        
        result = offline_queue.remove_item("nonexistent")
        
        assert result is False
    
    def test_cleanup_expired_items(self, offline_queue, mock_database):
        """Test cleaning up expired items."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_cursor = Mock()
        mock_cursor.rowcount = 3
        mock_conn.execute.return_value = mock_cursor
        
        removed_count = offline_queue.cleanup_expired_items()
        
        assert removed_count == 3
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()
    
    def test_get_queue_statistics(self, offline_queue, mock_database):
        """Test getting queue statistics."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Mock different query results
        mock_conn.execute.return_value.fetchall.side_effect = [
            [("queued", 5), ("completed", 10)],  # Status counts
            [("order", 3), ("print_job", 12)],   # Type counts
            [(2, 8), (3, 7)]                     # Priority counts
        ]
        mock_conn.execute.return_value.fetchone.return_value = ["2025-01-01T10:00:00"]
        
        stats = offline_queue.get_queue_statistics()
        
        assert stats["total_items"] == 15
        assert stats["status_counts"]["queued"] == 5
        assert stats["type_counts"]["order"] == 3
        assert stats["oldest_queued_item"] == "2025-01-01T10:00:00"
        assert stats["max_queue_size"] == 10000
    
    def test_log_connectivity_event(self, offline_queue, mock_database):
        """Test logging connectivity event."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        details = {"old_status": "online", "new_status": "offline"}
        result = offline_queue.log_connectivity_event(
            "printer_offline", "printer", "offline", "00:05:30", details
        )
        
        assert result is True
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()
        
        # Check that details were JSON serialized
        call_args = mock_conn.execute.call_args[0][1]
        assert json.dumps(details) in call_args
    
    def test_get_connectivity_events(self, offline_queue, mock_database):
        """Test getting connectivity events."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        mock_rows = [
            (1, "printer_offline", "printer", "offline", "2025-01-01T10:00:00", "00:05:30", '{"test": "data"}'),
            (2, "internet_online", "internet", "online", "2025-01-01T10:05:30", None, None)
        ]
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        
        events = offline_queue.get_connectivity_events(limit=10)
        
        assert len(events) == 2
        assert events[0]["event_type"] == "printer_offline"
        assert events[0]["details"] == {"test": "data"}
        assert events[1]["event_type"] == "internet_online"
        assert events[1]["details"] is None
    
    def test_get_connectivity_events_with_filter(self, offline_queue, mock_database):
        """Test getting connectivity events with component filter."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = []
        
        offline_queue.get_connectivity_events(limit=50, component="printer")
        
        # Verify SQL query includes component filter
        call_args = mock_conn.execute.call_args
        assert "WHERE component = ?" in call_args[0][0]
        assert "printer" in call_args[0][1]
    
    def test_save_queue_item(self, offline_queue, mock_database):
        """Test saving queue item to database."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        
        queue_item = OfflineQueueItem(
            id="test_item",
            item_type="order",
            item_id="order_123",
            priority=QueuePriority.HIGH,
            status=OfflineQueueStatus.QUEUED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={"test": "data"}
        )
        
        result = offline_queue._save_queue_item(queue_item)
        
        assert result is True
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()
    
    def test_save_queue_item_exception(self, offline_queue, mock_database):
        """Test saving queue item with database exception."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("Database error")
        
        queue_item = OfflineQueueItem(
            id="test_item",
            item_type="order",
            item_id="order_123",
            priority=QueuePriority.HIGH,
            status=OfflineQueueStatus.QUEUED,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = offline_queue._save_queue_item(queue_item)
        
        assert result is False
    
    def test_row_to_queue_item(self, offline_queue):
        """Test converting database row to queue item."""
        now = datetime.now()
        expires = now + timedelta(hours=24)
        
        row = (
            "item_1", "print_job", "job_1", 2, "queued",
            now.isoformat(), now.isoformat(),
            1, 3, expires.isoformat(), "Error message",
            '{"test": "data"}'
        )
        
        item = offline_queue._row_to_queue_item(row)
        
        assert isinstance(item, OfflineQueueItem)
        assert item.id == "item_1"
        assert item.item_type == "print_job"
        assert item.item_id == "job_1"
        assert item.priority == QueuePriority.NORMAL
        assert item.status == OfflineQueueStatus.QUEUED
        assert item.retry_count == 1
        assert item.max_retries == 3
        assert item.error_message == "Error message"
        assert item.metadata == {"test": "data"}
    
    def test_get_queue_size(self, offline_queue, mock_database):
        """Test getting current queue size."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = [42]
        
        size = offline_queue._get_queue_size()
        
        assert size == 42
        mock_conn.execute.assert_called_with("SELECT COUNT(*) FROM offline_queue")
    
    def test_get_queue_size_exception(self, offline_queue, mock_database):
        """Test getting queue size with exception."""
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("Database error")
        
        size = offline_queue._get_queue_size()
        
        assert size == 0


class TestOfflineQueueItem:
    """Test cases for OfflineQueueItem dataclass."""
    
    def test_offline_queue_item_creation(self):
        """Test creating an offline queue item."""
        now = datetime.now()
        expires = now + timedelta(hours=24)
        
        item = OfflineQueueItem(
            id="test_item",
            item_type="order",
            item_id="order_123",
            priority=QueuePriority.HIGH,
            status=OfflineQueueStatus.QUEUED,
            created_at=now,
            updated_at=now,
            retry_count=2,
            max_retries=5,
            expires_at=expires,
            error_message="Test error",
            metadata={"key": "value"}
        )
        
        assert item.id == "test_item"
        assert item.item_type == "order"
        assert item.item_id == "order_123"
        assert item.priority == QueuePriority.HIGH
        assert item.status == OfflineQueueStatus.QUEUED
        assert item.created_at == now
        assert item.updated_at == now
        assert item.retry_count == 2
        assert item.max_retries == 5
        assert item.expires_at == expires
        assert item.error_message == "Test error"
        assert item.metadata == {"key": "value"}


class TestOfflineQueueEnums:
    """Test cases for offline queue enums."""
    
    def test_queue_priority_enum(self):
        """Test QueuePriority enum values."""
        assert QueuePriority.LOW.value == 1
        assert QueuePriority.NORMAL.value == 2
        assert QueuePriority.HIGH.value == 3
        assert QueuePriority.CRITICAL.value == 4
    
    def test_offline_queue_status_enum(self):
        """Test OfflineQueueStatus enum values."""
        assert OfflineQueueStatus.QUEUED.value == "queued"
        assert OfflineQueueStatus.PROCESSING.value == "processing"
        assert OfflineQueueStatus.COMPLETED.value == "completed"
        assert OfflineQueueStatus.FAILED.value == "failed"
        assert OfflineQueueStatus.EXPIRED.value == "expired"
