"""
Tests for offline queue manager.
"""
import pytest
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables for the tests
load_dotenv()

from wix_printer_service.database import Database
from wix_printer_service.offline_queue import (
    OfflineQueueManager, QueuePriority, OfflineQueueStatus, OfflineQueueItem
)
from wix_printer_service.models import (
    Order, PrintJob, OrderItem, OrderStatus, PrintJobStatus, CustomerInfo, DeliveryInfo
)

# Check if DATABASE_URL is set, skip all tests if not
DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL environment variable not set")

# --- Fixtures ---

@pytest.fixture(scope="module")
def db_instance():
    """Provides a database instance for the entire test module."""
    try:
        db = Database()
        return db
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")

@pytest.fixture
def offline_queue(db_instance):
    """Provides a clean OfflineQueueManager instance for each test."""
    # Truncate tables before each test that uses this fixture
    tables = ["offline_queue", "print_jobs", "orders"]
    with db_instance.get_connection() as conn:
        with conn.cursor() as cursor:
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
    
    return OfflineQueueManager(db_instance)

@pytest.fixture
def sample_order(db_instance):
    """Creates and saves a sample order, returning its ID."""
    now = datetime.now()
    order = Order(
        id="order_123",
        wix_order_id="wix_456",
        status=OrderStatus.PENDING,
        items=[OrderItem(id="item-1", name="Test Item", quantity=1, price=10.0)],
        customer=CustomerInfo(id="cust_1", email="test@example.com"),
        delivery=DeliveryInfo(),
        total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now
    )
    db_instance.save_order(order)
    return order

@pytest.fixture
def sample_print_job(db_instance, sample_order):
    """Creates and saves a sample print job, returning its ID."""
    now = datetime.now()
    job = PrintJob(
        order_id=sample_order.id,
        job_type="kitchen",
        status=PrintJobStatus.PENDING,
        content="Test content",
        created_at=now,
        updated_at=now
    )
    job_id = db_instance.save_print_job(job)
    return job_id

# --- Test Cases ---

def test_init(db_instance):
    """Test offline queue manager initialization."""
    queue = OfflineQueueManager(db_instance)
    assert queue.database == db_instance
    # Check if table was created
    with db_instance.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.offline_queue');")
            assert cursor.fetchone()[0] == 'offline_queue'

def test_queue_item_success(offline_queue, sample_print_job):
    """Test successfully queuing a generic item."""
    result = offline_queue.queue_item("print_job", str(sample_print_job), QueuePriority.HIGH)
    assert result is True
    
    items = offline_queue.get_next_items(limit=1)
    assert len(items) == 1
    assert items[0].item_id == str(sample_print_job)
    assert items[0].item_type == "print_job"
    assert items[0].priority == QueuePriority.HIGH.value

def test_queue_order_and_print_job(offline_queue, sample_order, sample_print_job):
    """Test queuing both an order and a print job."""
    assert offline_queue.queue_order(sample_order) is True
    assert offline_queue.queue_print_job(PrintJob(id=str(sample_print_job), order_id=sample_order.id, job_type="kitchen", status=PrintJobStatus.PENDING, content="Test")) is True

    items = offline_queue.get_next_items(limit=5)
    assert len(items) == 2
    item_types = {item.item_type for item in items}
    assert "order" in item_types
    assert "print_job" in item_types

def test_get_next_items_respects_priority(offline_queue, sample_print_job):
    """Test that get_next_items returns highest priority items first."""
    # Queue items with different priorities
    offline_queue.queue_item("print_job", "job_low", QueuePriority.LOW)
    offline_queue.queue_item("print_job", "job_high", QueuePriority.HIGH)
    offline_queue.queue_item("print_job", "job_normal", QueuePriority.NORMAL)

    items = offline_queue.get_next_items(limit=3)
    assert len(items) == 3
    assert items[0].item_id == "job_high"
    assert items[1].item_id == "job_normal"
    assert items[2].item_id == "job_low"

def test_update_item_status(offline_queue, sample_print_job):
    """Test updating an item's status."""
    offline_queue.queue_item("print_job", str(sample_print_job), QueuePriority.NORMAL)
    item = offline_queue.get_next_items(limit=1)[0]
    
    # Update status to PROCESSING
    result = offline_queue.update_item_status(item.id, OfflineQueueStatus.PROCESSING, "In progress")
    assert result is True

    # Verify item is no longer in 'queued'
    assert len(offline_queue.get_next_items(limit=1)) == 0

def test_increment_retry_count(offline_queue, sample_print_job):
    """Test incrementing an item's retry count."""
    offline_queue.queue_item("print_job", str(sample_print_job), QueuePriority.NORMAL)
    item_id = offline_queue.get_next_items(limit=1)[0].id

    result = offline_queue.increment_retry_count(item_id)
    assert result is True

def test_remove_item(offline_queue, sample_print_job):
    """Test removing an item from the queue."""
    offline_queue.queue_item("print_job", str(sample_print_job), QueuePriority.NORMAL)
    assert len(offline_queue.get_next_items(limit=1)) == 1

    item_id = offline_queue.get_next_items(limit=1)[0].id
    result = offline_queue.remove_item(item_id)
    assert result is True

    assert len(offline_queue.get_next_items(limit=1)) == 0

def test_get_queue_size(offline_queue, sample_print_job):
    """Test getting the current queue size."""
    assert offline_queue._get_queue_size() == 0
    offline_queue.queue_item("print_job", str(sample_print_job), QueuePriority.NORMAL)
    assert offline_queue._get_queue_size() == 1

class TestOfflineQueueEnums:
    """Test cases for offline queue enums."""
    def test_queue_priority_enum(self):
        assert QueuePriority.LOW.value == 1
        assert QueuePriority.NORMAL.value == 2
        assert QueuePriority.HIGH.value == 3
        assert QueuePriority.CRITICAL.value == 4

    def test_offline_queue_status_enum(self):
        assert OfflineQueueStatus.QUEUED.value == "queued"
        assert OfflineQueueStatus.PROCESSING.value == "processing"
        assert OfflineQueueStatus.COMPLETED.value == "completed"
        assert OfflineQueueStatus.FAILED.value == "failed"