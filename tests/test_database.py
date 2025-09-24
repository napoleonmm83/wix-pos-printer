"""
Unit tests for database operations.
Tests PostgreSQL database initialization and CRUD operations.
"""
import pytest
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables for the tests
load_dotenv()

from wix_printer_service.database import Database, DatabaseError
from wix_printer_service.models import (
    Order, PrintJob, OrderItem, CustomerInfo, DeliveryInfo,
    OrderStatus, PrintJobStatus
)

# Check if DATABASE_URL is set, skip all tests if not
DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL environment variable not set")

@pytest.fixture(scope="module")
def db_instance():
    """
    Provides a database instance for the entire test module.
    The database schema is created once.
    """
    try:
        db = Database()
        return db
    except DatabaseError as e:
        pytest.fail(f"Database connection failed: {e}")

@pytest.fixture(autouse=True)
def cleanup_tables(db_instance):
    """
    Fixture to automatically clean up tables before each test.
    This ensures test isolation.
    """
    tables = ["print_jobs", "orders", "health_metrics", "circuit_breaker_failures", "offline_queue"]
    with db_instance.get_connection() as conn:
        with conn.cursor() as cursor:
            for table in tables:
                # Use TRUNCATE and CASCADE to handle foreign key relationships
                cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
    yield


def test_database_initialization(db_instance):
    """Test database initialization creates tables."""
    with db_instance.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN ('orders', 'print_jobs', 'health_metrics');
            """)
            tables = [row[0] for row in cursor.fetchall()]
            assert 'orders' in tables
            assert 'print_jobs' in tables
            assert 'health_metrics' in tables

def test_save_and_get_order(db_instance):
    """Test saving and retrieving an order."""
    items = [OrderItem(id="item-1", name="Test Item", quantity=2, price=10.0)]
    customer = CustomerInfo(email="test@example.com", first_name="John", last_name="Doe")
    delivery = DeliveryInfo(address="123 Main St")
    
    order = Order(
        id="test_order_123",
        wix_order_id="wix_123",
        status=OrderStatus.PENDING,
        items=items,
        customer=customer,
        delivery=delivery,
        total_amount=20.0,
        currency="CHF",
        order_date=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    assert db_instance.save_order(order) is True
    
    retrieved_order = db_instance.get_order("test_order_123")
    
    assert retrieved_order is not None
    assert retrieved_order.id == "test_order_123"
    assert retrieved_order.wix_order_id == "wix_123"
    assert retrieved_order.status == OrderStatus.PENDING
    assert len(retrieved_order.items) == 1
    assert retrieved_order.items[0].name == "Test Item"
    assert retrieved_order.customer.email == "test@example.com"
    assert retrieved_order.delivery.address == "123 Main St"
    assert retrieved_order.total_amount == 20.0

def test_get_nonexistent_order(db_instance):
    """Test retrieving a non-existent order."""
    order = db_instance.get_order("nonexistent_order")
    assert order is None

def test_get_orders_by_status(db_instance):
    """Test retrieving orders by status."""
    items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
    customer = CustomerInfo(email="test@example.com", first_name="Jane", last_name="Doe")
    delivery = DeliveryInfo(address="456 Oak Ave")
    now = datetime.now()

    order1 = Order(id="order_1", wix_order_id="wix_1", status=OrderStatus.PENDING, items=items, customer=customer, delivery=delivery, total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    order2 = Order(id="order_2", wix_order_id="wix_2", status=OrderStatus.PROCESSING, items=items, customer=customer, delivery=delivery, total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    order3 = Order(id="order_3", wix_order_id="wix_3", status=OrderStatus.PENDING, items=items, customer=customer, delivery=delivery, total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    
    db_instance.save_order(order1)
    db_instance.save_order(order2)
    db_instance.save_order(order3)
    
    pending_orders = db_instance.get_orders_by_status(OrderStatus.PENDING)
    assert len(pending_orders) == 2
    
    processing_orders = db_instance.get_orders_by_status(OrderStatus.PROCESSING)
    assert len(processing_orders) == 1
    assert processing_orders[0].id == "order_2"

def test_save_and_get_print_job(db_instance):
    """Test saving and retrieving print jobs."""
    now = datetime.now()
    order = Order(id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING, items=[], customer=CustomerInfo(), delivery=DeliveryInfo(), total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    db_instance.save_order(order)
    
    job = PrintJob(
        order_id="test_order",
        job_type="kitchen",
        status=PrintJobStatus.PENDING,
        content="Test receipt content",
        created_at=now,
        updated_at=now
    )
    
    job_id = db_instance.save_print_job(job)
    assert job_id is not None
    
    job.id = job_id
    job.status = PrintJobStatus.COMPLETED
    job.printed_at = datetime.now()
    
    updated_job_id = db_instance.save_print_job(job)
    assert updated_job_id == job_id

def test_get_pending_print_jobs(db_instance):
    """Test retrieving pending print jobs."""
    now = datetime.now()
    order = Order(id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING, items=[], customer=CustomerInfo(), delivery=DeliveryInfo(), total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    db_instance.save_order(order)
    
    job1 = PrintJob(order_id="test_order", job_type="kitchen", status=PrintJobStatus.PENDING, content="Kitchen receipt", created_at=now, updated_at=now)
    job2 = PrintJob(order_id="test_order", job_type="customer", status=PrintJobStatus.COMPLETED, content="Customer receipt", created_at=now, updated_at=now)
    job3 = PrintJob(order_id="test_order", job_type="delivery", status=PrintJobStatus.PENDING, content="Delivery receipt", created_at=now, updated_at=now)
    
    db_instance.save_print_job(job1)
    db_instance.save_print_job(job2)
    db_instance.save_print_job(job3)
    
    pending_jobs = db_instance.get_pending_print_jobs()
    assert len(pending_jobs) == 2
    
    job_types = {job.job_type for job in pending_jobs}
    assert "kitchen" in job_types
    assert "delivery" in job_types
    assert "customer" not in job_types

def test_get_pending_print_jobs_with_max_attempts(db_instance):
    """Test that jobs with max attempts reached are not returned."""
    now = datetime.now()
    order = Order(id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING, items=[], customer=CustomerInfo(), delivery=DeliveryInfo(), total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    db_instance.save_order(order)
    
    job = PrintJob(
        order_id="test_order", job_type="kitchen", status=PrintJobStatus.PENDING,
        content="Kitchen receipt", attempts=3, max_attempts=3, created_at=now, updated_at=now
    )
    
    db_instance.save_print_job(job)
    
    pending_jobs = db_instance.get_pending_print_jobs()
    assert len(pending_jobs) == 0

def test_order_update(db_instance):
    """Test updating an existing order using ON CONFLICT."""
    now = datetime.now()
    order = Order(id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING, items=[], customer=CustomerInfo(), delivery=DeliveryInfo(), total_amount=10.0, currency="CHF", order_date=now, created_at=now, updated_at=now)
    db_instance.save_order(order)
    
    # Create a new order object with the same wix_order_id to simulate an update
    updated_order_obj = Order(id="test_order_new_id", wix_order_id="wix_order", status=OrderStatus.PROCESSING, items=[], customer=CustomerInfo(), delivery=DeliveryInfo(), total_amount=15.0, currency="CHF", order_date=now, created_at=now, updated_at=datetime.now())
    
    db_instance.save_order(updated_order_obj)
    
    # Retrieve by the unique wix_order_id
    retrieved_order = db_instance.get_order_by_wix_id("wix_order")
    assert retrieved_order is not None
    # The original ID should be kept, as wix_order_id is the conflict target
    assert retrieved_order.id == "test_order" 
    assert retrieved_order.status == OrderStatus.PROCESSING
    assert retrieved_order.total_amount == 15.0