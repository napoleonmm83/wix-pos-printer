"""
Unit tests for data models.
Tests Order and PrintJob model functionality.
"""
import pytest
from datetime import datetime
import json

from wix_printer_service.models import (
    Order, PrintJob, OrderItem, CustomerInfo, DeliveryInfo,
    OrderStatus, PrintJobStatus
)


class TestOrderItem:
    """Test cases for OrderItem model."""
    
    def test_order_item_creation(self):
        """Test creating an OrderItem instance."""
        item = OrderItem(
            id="item_123",
            name="Test Product",
            quantity=2,
            price=15.99,
            sku="SKU123",
            variant="Large",
            notes="Extra cheese"
        )
        
        assert item.id == "item_123"
        assert item.name == "Test Product"
        assert item.quantity == 2
        assert item.price == 15.99
        assert item.sku == "SKU123"
        assert item.variant == "Large"
        assert item.notes == "Extra cheese"


class TestCustomerInfo:
    """Test cases for CustomerInfo model."""
    
    def test_customer_info_creation(self):
        """Test creating a CustomerInfo instance."""
        customer = CustomerInfo(
            id="cust_123",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            phone="+1234567890"
        )
        
        assert customer.id == "cust_123"
        assert customer.email == "test@example.com"
        assert customer.first_name == "John"
        assert customer.last_name == "Doe"
        assert customer.phone == "+1234567890"
    
    def test_customer_info_defaults(self):
        """Test CustomerInfo with default values."""
        customer = CustomerInfo()
        
        assert customer.id is None
        assert customer.email is None
        assert customer.first_name is None
        assert customer.last_name is None
        assert customer.phone is None


class TestDeliveryInfo:
    """Test cases for DeliveryInfo model."""
    
    def test_delivery_info_creation(self):
        """Test creating a DeliveryInfo instance."""
        delivery = DeliveryInfo(
            address="123 Main St",
            city="Test City",
            postal_code="12345",
            country="Test Country",
            delivery_instructions="Ring doorbell"
        )
        
        assert delivery.address == "123 Main St"
        assert delivery.city == "Test City"
        assert delivery.postal_code == "12345"
        assert delivery.country == "Test Country"
        assert delivery.delivery_instructions == "Ring doorbell"


class TestOrder:
    """Test cases for Order model."""
    
    def test_order_creation(self):
        """Test creating an Order instance."""
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com", first_name="John")
        delivery = DeliveryInfo(address="123 Main St")
        
        order = Order(
            id="order_123",
            wix_order_id="wix_456",
            status=OrderStatus.PENDING,
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=10.0
        )
        
        assert order.id == "order_123"
        assert order.wix_order_id == "wix_456"
        assert order.status == OrderStatus.PENDING
        assert len(order.items) == 1
        assert order.total_amount == 10.0
        assert order.currency == "EUR"  # default value
    
    def test_order_from_wix_data(self):
        """Test creating Order from Wix API data."""
        wix_data = {
            "id": "wix_order_123",
            "status": "pending",
            "dateCreated": "2025-09-18T10:00:00Z",
            "lineItems": [
                {
                    "id": "item_1",
                    "name": "Pizza Margherita",
                    "quantity": 2,
                    "price": {"amount": 12.50},
                    "sku": "PIZZA_MARG",
                    "notes": "Extra cheese"
                }
            ],
            "buyerInfo": {
                "id": "buyer_123",
                "email": "customer@example.com",
                "firstName": "Jane",
                "lastName": "Smith",
                "phone": "+1234567890"
            },
            "shippingInfo": {
                "deliveryAddress": {
                    "addressLine1": "456 Oak Ave",
                    "city": "Springfield",
                    "postalCode": "54321",
                    "country": "USA"
                },
                "deliveryInstructions": "Leave at door"
            },
            "totals": {
                "total": {
                    "amount": 25.0,
                    "currency": "USD"
                }
            }
        }
        
        order = Order.from_wix_data(wix_data)
        
        assert order.id == "wix_order_123"
        assert order.wix_order_id == "wix_order_123"
        assert order.status == OrderStatus.PENDING
        assert len(order.items) == 1
        assert order.items[0].name == "Pizza Margherita"
        assert order.items[0].quantity == 2
        assert order.items[0].price == 12.50
        assert order.customer.email == "customer@example.com"
        assert order.customer.first_name == "Jane"
        assert order.delivery.address == "456 Oak Ave"
        assert order.total_amount == 25.0
        assert order.currency == "USD"
        assert order.raw_data == wix_data
    
    def test_order_from_wix_data_minimal(self):
        """Test creating Order from minimal Wix API data."""
        wix_data = {
            "id": "minimal_order",
            "lineItems": [],
            "buyerInfo": {},
            "shippingInfo": {},
            "totals": {"total": {"amount": 0}}
        }
        
        order = Order.from_wix_data(wix_data)
        
        assert order.id == "minimal_order"
        assert order.status == OrderStatus.PENDING  # default
        assert len(order.items) == 0
        assert order.total_amount == 0
        assert order.currency == "EUR"  # default
    
    def test_order_to_dict(self):
        """Test converting Order to dictionary."""
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.0)]
        customer = CustomerInfo(email="test@example.com")
        delivery = DeliveryInfo(address="123 Main St")
        
        order = Order(
            id="order_123",
            wix_order_id="wix_456",
            status=OrderStatus.PENDING,
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=10.0
        )
        
        order_dict = order.to_dict()
        
        assert order_dict['id'] == "order_123"
        assert order_dict['wix_order_id'] == "wix_456"
        assert order_dict['status'] == "pending"
        assert order_dict['total_amount'] == 10.0
        assert 'items_json' in order_dict
        assert 'customer_json' in order_dict
        assert 'delivery_json' in order_dict
        
        # Test JSON fields can be parsed
        items_data = json.loads(order_dict['items_json'])
        assert len(items_data) == 1
        assert items_data[0]['name'] == "Test Item"


class TestPrintJob:
    """Test cases for PrintJob model."""
    
    def test_print_job_creation(self):
        """Test creating a PrintJob instance."""
        job = PrintJob(
            id="job_123",
            order_id="order_456",
            job_type="kitchen",
            status=PrintJobStatus.PENDING,
            content="Test receipt content",
            printer_name="Kitchen Printer"
        )
        
        assert job.id == "job_123"
        assert job.order_id == "order_456"
        assert job.job_type == "kitchen"
        assert job.status == PrintJobStatus.PENDING
        assert job.content == "Test receipt content"
        assert job.printer_name == "Kitchen Printer"
        assert job.attempts == 0
        assert job.max_attempts == 3
    
    def test_print_job_defaults(self):
        """Test PrintJob with default values."""
        job = PrintJob(order_id="order_123")
        
        assert job.id is None
        assert job.order_id == "order_123"
        assert job.job_type == "receipt"
        assert job.status == PrintJobStatus.PENDING
        assert job.content == ""
        assert job.attempts == 0
        assert job.max_attempts == 3
        assert job.printed_at is None
        assert job.error_message is None
    
    def test_print_job_to_dict(self):
        """Test converting PrintJob to dictionary."""
        job = PrintJob(
            id="job_123",
            order_id="order_456",
            job_type="customer",
            status=PrintJobStatus.COMPLETED,
            content="Receipt content"
        )
        
        job_dict = job.to_dict()
        
        assert job_dict['id'] == "job_123"
        assert job_dict['order_id'] == "order_456"
        assert job_dict['job_type'] == "customer"
        assert job_dict['status'] == "completed"
        assert job_dict['content'] == "Receipt content"
        assert job_dict['attempts'] == 0
        assert job_dict['max_attempts'] == 3
        assert job_dict['printed_at'] is None


class TestEnums:
    """Test cases for enum classes."""
    
    def test_order_status_values(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.PROCESSING.value == "processing"
        assert OrderStatus.COMPLETED.value == "completed"
        assert OrderStatus.CANCELLED.value == "cancelled"
    
    def test_print_job_status_values(self):
        """Test PrintJobStatus enum values."""
        assert PrintJobStatus.PENDING.value == "pending"
        assert PrintJobStatus.PRINTING.value == "printing"
        assert PrintJobStatus.COMPLETED.value == "completed"
        assert PrintJobStatus.FAILED.value == "failed"
