"""
Unit tests for database operations.
Tests SQLite database initialization and CRUD operations.
"""
import pytest
import tempfile
import os
from datetime import datetime

from wix_printer_service.database import Database, DatabaseError
from wix_printer_service.models import (
    Order, PrintJob, OrderItem, CustomerInfo, DeliveryInfo,
    OrderStatus, PrintJobStatus
)


class TestDatabase:
    """Test cases for Database class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        db = Database(temp_file.name)
        yield db
        
        # Cleanup
        db.close()
        os.unlink(temp_file.name)
    
    def test_database_initialization(self, temp_db):
        """Test database initialization creates tables."""
        # Test that we can get a connection
        conn = temp_db.get_connection()
        
        # Check that tables exist
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('orders', 'print_jobs')
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'orders' in tables
        assert 'print_jobs' in tables
        
        conn.close()
    
    def test_save_and_get_order(self, temp_db):
        """Test saving and retrieving an order."""
        # Create test order
        items = [OrderItem(id="1", name="Test Item", quantity=2, price=10.0)]
        customer = CustomerInfo(email="test@example.com", first_name="John")
        delivery = DeliveryInfo(address="123 Main St")
        
        order = Order(
            id="test_order_123",
            wix_order_id="wix_123",
            status=OrderStatus.PENDING,
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=20.0
        )
        
        # Save order
        result = temp_db.save_order(order)
        assert result is True
        
        # Retrieve order
        retrieved_order = temp_db.get_order("test_order_123")
        
        assert retrieved_order is not None
        assert retrieved_order.id == "test_order_123"
        assert retrieved_order.wix_order_id == "wix_123"
        assert retrieved_order.status == OrderStatus.PENDING
        assert len(retrieved_order.items) == 1
        assert retrieved_order.items[0].name == "Test Item"
        assert retrieved_order.customer.email == "test@example.com"
        assert retrieved_order.delivery.address == "123 Main St"
        assert retrieved_order.total_amount == 20.0
    
    def test_get_nonexistent_order(self, temp_db):
        """Test retrieving a non-existent order."""
        order = temp_db.get_order("nonexistent_order")
        assert order is None
    
    def test_get_orders_by_status(self, temp_db):
        """Test retrieving orders by status."""
        # Create test orders with different statuses
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com")
        delivery = DeliveryInfo()
        
        order1 = Order(
            id="order_1", wix_order_id="wix_1", status=OrderStatus.PENDING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        order2 = Order(
            id="order_2", wix_order_id="wix_2", status=OrderStatus.PROCESSING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        order3 = Order(
            id="order_3", wix_order_id="wix_3", status=OrderStatus.PENDING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        
        # Save orders
        temp_db.save_order(order1)
        temp_db.save_order(order2)
        temp_db.save_order(order3)
        
        # Get pending orders
        pending_orders = temp_db.get_orders_by_status(OrderStatus.PENDING)
        assert len(pending_orders) == 2
        
        # Get processing orders
        processing_orders = temp_db.get_orders_by_status(OrderStatus.PROCESSING)
        assert len(processing_orders) == 1
        assert processing_orders[0].id == "order_2"
    
    def test_save_and_get_print_job(self, temp_db):
        """Test saving and retrieving print jobs."""
        # First create an order
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com")
        delivery = DeliveryInfo()
        
        order = Order(
            id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        temp_db.save_order(order)
        
        # Create print job
        job = PrintJob(
            order_id="test_order",
            job_type="kitchen",
            status=PrintJobStatus.PENDING,
            content="Test receipt content",
            printer_name="Kitchen Printer"
        )
        
        # Save print job
        job_id = temp_db.save_print_job(job)
        assert job_id is not None
        
        # Update job with ID and save again (test update path)
        job.id = job_id
        job.status = PrintJobStatus.COMPLETED
        job.printed_at = datetime.now()
        
        updated_job_id = temp_db.save_print_job(job)
        assert updated_job_id == job_id
    
    def test_get_pending_print_jobs(self, temp_db):
        """Test retrieving pending print jobs."""
        # Create test order
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com")
        delivery = DeliveryInfo()
        
        order = Order(
            id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        temp_db.save_order(order)
        
        # Create print jobs with different statuses
        job1 = PrintJob(
            order_id="test_order",
            job_type="kitchen",
            status=PrintJobStatus.PENDING,
            content="Kitchen receipt"
        )
        job2 = PrintJob(
            order_id="test_order",
            job_type="customer",
            status=PrintJobStatus.COMPLETED,
            content="Customer receipt"
        )
        job3 = PrintJob(
            order_id="test_order",
            job_type="delivery",
            status=PrintJobStatus.PENDING,
            content="Delivery receipt"
        )
        
        # Save jobs
        temp_db.save_print_job(job1)
        temp_db.save_print_job(job2)
        temp_db.save_print_job(job3)
        
        # Get pending jobs
        pending_jobs = temp_db.get_pending_print_jobs()
        assert len(pending_jobs) == 2
        
        # Check job types
        job_types = [job.job_type for job in pending_jobs]
        assert "kitchen" in job_types
        assert "delivery" in job_types
        assert "customer" not in job_types  # This one is completed
    
    def test_get_pending_print_jobs_with_max_attempts(self, temp_db):
        """Test that jobs with max attempts reached are not returned."""
        # Create test order
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com")
        delivery = DeliveryInfo()
        
        order = Order(
            id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        temp_db.save_order(order)
        
        # Create job that has reached max attempts
        job = PrintJob(
            order_id="test_order",
            job_type="kitchen",
            status=PrintJobStatus.PENDING,
            content="Kitchen receipt",
            attempts=3,  # Equal to max_attempts
            max_attempts=3
        )
        
        temp_db.save_print_job(job)
        
        # Should not return this job
        pending_jobs = temp_db.get_pending_print_jobs()
        assert len(pending_jobs) == 0
    
    def test_database_error_handling(self):
        """Test database error handling."""
        # Test with invalid database path
        with pytest.raises(DatabaseError):
            Database("/invalid/path/database.db")
    
    def test_connection_with_foreign_keys(self, temp_db):
        """Test that foreign key constraints are enabled."""
        conn = temp_db.get_connection()
        
        # Check foreign keys are enabled
        cursor = conn.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result[0] == 1  # Foreign keys should be enabled
        
        conn.close()
    
    def test_order_update(self, temp_db):
        """Test updating an existing order."""
        # Create and save initial order
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com")
        delivery = DeliveryInfo()
        
        order = Order(
            id="test_order", wix_order_id="wix_order", status=OrderStatus.PENDING,
            items=items, customer=customer, delivery=delivery, total_amount=10.0
        )
        temp_db.save_order(order)
        
        # Update order status
        order.status = OrderStatus.PROCESSING
        order.total_amount = 15.0
        
        # Save updated order
        result = temp_db.save_order(order)
        assert result is True
        
        # Retrieve and verify update
        updated_order = temp_db.get_order("test_order")
        assert updated_order.status == OrderStatus.PROCESSING
        assert updated_order.total_amount == 15.0
