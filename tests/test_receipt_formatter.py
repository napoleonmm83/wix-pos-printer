"""
Unit tests for receipt formatter.
Tests layout engine, formatters, and ESC/POS output.
"""
import pytest
import os
from unittest.mock import patch
from datetime import datetime

from wix_printer_service.receipt_formatter import (
    ESCPOSFormatter, BaseReceiptFormatter, KitchenReceiptFormatter,
    DriverReceiptFormatter, CustomerReceiptFormatter, ReceiptFormatterFactory,
    ReceiptType, TextStyle, TextAlignment, format_receipt
)
from wix_printer_service.models import (
    Order, OrderItem, CustomerInfo, DeliveryInfo, OrderStatus
)


class TestESCPOSFormatter:
    """Test cases for ESC/POS formatting utilities."""
    
    def test_format_text_normal(self):
        """Test normal text formatting."""
        result = ESCPOSFormatter.format_text("Test text")
        
        # Should include left alignment and text
        assert ESCPOSFormatter.ALIGN_LEFT in result
        assert "Test text" in result
    
    def test_format_text_bold(self):
        """Test bold text formatting."""
        result = ESCPOSFormatter.format_text("Bold text", TextStyle.BOLD)
        
        assert ESCPOSFormatter.BOLD_ON in result
        assert ESCPOSFormatter.BOLD_OFF in result
        assert "Bold text" in result
    
    def test_format_text_center_aligned(self):
        """Test center-aligned text."""
        result = ESCPOSFormatter.format_text("Centered", alignment=TextAlignment.CENTER)
        
        assert ESCPOSFormatter.ALIGN_CENTER in result
        assert ESCPOSFormatter.ALIGN_LEFT in result  # Reset to left
        assert "Centered" in result
    
    def test_create_separator(self):
        """Test separator line creation."""
        result = ESCPOSFormatter.create_separator("=", 10)
        assert result == "=========="
        
        result = ESCPOSFormatter.create_separator()
        assert len(result) == 32
        assert result == "=" * 32
    
    def test_create_two_column_line(self):
        """Test two-column line formatting."""
        result = ESCPOSFormatter.create_two_column_line("Left", "Right", 20)
        
        assert result.startswith("Left")
        assert result.endswith("Right")
        assert len(result) == 20
    
    def test_create_two_column_line_truncation(self):
        """Test two-column line with text truncation."""
        result = ESCPOSFormatter.create_two_column_line("Very long left text", "Right", 20)
        
        assert "..." in result
        assert result.endswith("Right")
        assert len(result) == 20
    
    def test_create_table_row(self):
        """Test table row creation."""
        columns = ["Item", "Qty", "Price"]
        widths = [10, 5, 7]
        
        result = ESCPOSFormatter.create_table_row(columns, widths)
        
        assert len(result) == sum(widths)
        assert "Item" in result
        assert "Qty" in result
        assert "Price" in result
    
    def test_create_table_row_truncation(self):
        """Test table row with column truncation."""
        columns = ["Very long item name", "1", "10.00"]
        widths = [8, 3, 6]
        
        result = ESCPOSFormatter.create_table_row(columns, widths)
        
        assert "..." in result
        assert len(result) == sum(widths)


class TestBaseReceiptFormatter:
    """Test cases for base receipt formatter."""
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing."""
        items = [
            OrderItem(
                id="1",
                name="Pizza Margherita",
                quantity=2,
                price=12.50,
                variant="Large",
                notes="Extra cheese"
            ),
            OrderItem(
                id="2",
                name="Coca Cola",
                quantity=1,
                price=2.50
            )
        ]
        
        customer = CustomerInfo(
            id="cust_1",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            phone="+49123456789"
        )
        
        delivery = DeliveryInfo(
            address="Musterstraße 123",
            city="Berlin",
            postal_code="12345",
            country="Germany",
            delivery_instructions="Ring doorbell"
        )
        
        return Order(
            id="order_123",
            wix_order_id="wix_456",
            status=OrderStatus.PENDING,
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=27.50,
            currency="EUR",
            created_at=datetime(2025, 9, 19, 12, 30)
        )
    
    @patch.dict(os.environ, {
        'RESTAURANT_NAME': 'Test Restaurant',
        'RESTAURANT_ADDRESS': 'Test Address',
        'RESTAURANT_PHONE': '+49123456789'
    })
    def test_format_header(self, sample_order):
        """Test header formatting."""
        
        class TestFormatter(BaseReceiptFormatter):
            def format_receipt(self, order):
                return self._format_header("TEST RECEIPT")
        
        formatter = TestFormatter()
        result = formatter._format_header("TEST RECEIPT")
        
        assert "Test Restaurant" in result
        assert "Test Address" in result
        assert "+49123456789" in result
        assert "TEST RECEIPT" in result
        assert ESCPOSFormatter.INIT in result
    
    def test_format_order_info(self, sample_order):
        """Test order info formatting."""
        
        class TestFormatter(BaseReceiptFormatter):
            def format_receipt(self, order):
                return self._format_order_info(order)
        
        formatter = TestFormatter()
        result = formatter._format_order_info(sample_order)
        
        assert "order_123" in result
        assert "John Doe" in result
        assert "19.09.2025" in result
    
    def test_format_items_without_prices(self, sample_order):
        """Test item formatting without prices."""
        
        class TestFormatter(BaseReceiptFormatter):
            def format_receipt(self, order):
                return self._format_items(order, show_prices=False)
        
        formatter = TestFormatter()
        result = formatter._format_items(sample_order, show_prices=False)
        
        assert "2x Pizza Margherita" in result
        assert "1x Coca Cola" in result
        assert "Large" in result
        assert "Extra cheese" in result
        assert "12.50" not in result  # Prices should not be shown
    
    def test_format_items_with_prices(self, sample_order):
        """Test item formatting with prices."""
        
        class TestFormatter(BaseReceiptFormatter):
            def format_receipt(self, order):
                return self._format_items(order, show_prices=True)
        
        formatter = TestFormatter()
        result = formatter._format_items(sample_order, show_prices=True)
        
        assert "Pizza Margherita" in result
        assert "2x" in result
        assert "12.50€" in result
        assert "2.50€" in result
    
    def test_calculate_totals(self, sample_order):
        """Test total calculations."""
        
        class TestFormatter(BaseReceiptFormatter):
            def format_receipt(self, order):
                return ""
        
        formatter = TestFormatter()
        totals = formatter._calculate_totals(sample_order)
        
        expected_subtotal = (2 * 12.50) + (1 * 2.50)  # 27.50
        expected_tax = expected_subtotal * 0.19  # 5.225
        expected_total = expected_subtotal + expected_tax  # 32.725
        
        assert totals['subtotal'] == expected_subtotal
        assert abs(totals['tax_amount'] - expected_tax) < 0.01
        assert abs(totals['total'] - expected_total) < 0.01
        assert totals['tax_rate'] == 0.19


class TestKitchenReceiptFormatter:
    """Test cases for kitchen receipt formatter."""
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing."""
        items = [
            OrderItem(
                id="1",
                name="Pizza Margherita",
                quantity=2,
                price=12.50,
                variant="Large",
                notes="Extra cheese, no olives"
            ),
            OrderItem(
                id="2",
                name="Gluten-free pasta",
                quantity=1,
                price=15.00,
                notes="Allergie: Gluten"
            )
        ]
        
        customer = CustomerInfo(
            first_name="John",
            last_name="Doe",
            phone="+49123456789"
        )
        
        return Order(
            id="order_123",
            wix_order_id="wix_456",
            status=OrderStatus.PENDING,
            items=items,
            customer=customer,
            delivery=DeliveryInfo(),
            total_amount=40.00,
            created_at=datetime(2025, 9, 19, 12, 30)
        )
    
    def test_format_kitchen_receipt(self, sample_order):
        """Test kitchen receipt formatting."""
        formatter = KitchenReceiptFormatter()
        result = formatter.format_receipt(sample_order)
        
        # Check header
        assert "KÜCHE" in result
        
        # Check order info
        assert "order_123" in result
        
        # Check items with emphasis
        assert "2x Pizza Margherita" in result
        assert "1x Gluten-free pasta" in result
        assert "Large" in result
        
        # Check special requests highlighting
        assert "!!! Extra cheese, no olives !!!" in result
        assert "!!! Allergie: Gluten !!!" in result
        
        # Check allergy warning
        assert "*** ALLERGIE WARNUNG ***" in result
        
        # Check preparation time
        assert "Geschätzte Zubereitungszeit:" in result
        
        # Check status
        assert "PENDING" in result
    
    def test_contains_allergy_keywords(self, sample_order):
        """Test allergy keyword detection."""
        formatter = KitchenReceiptFormatter()
        
        assert formatter._contains_allergy_keywords("Allergie: Gluten")
        assert formatter._contains_allergy_keywords("Keine Nüsse bitte")
        assert formatter._contains_allergy_keywords("Laktosefrei")
        assert not formatter._contains_allergy_keywords("Extra cheese")
        assert not formatter._contains_allergy_keywords("Well done")
    
    def test_estimate_prep_time(self, sample_order):
        """Test preparation time estimation."""
        formatter = KitchenReceiptFormatter()
        prep_time = formatter._estimate_prep_time(sample_order)
        
        # Should be base_time (5) + item_time (2*2) + complexity_time (3*1) = 12
        assert prep_time == 12


class TestDriverReceiptFormatter:
    """Test cases for driver receipt formatter."""
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing."""
        items = [
            OrderItem(id="1", name="Pizza", quantity=1, price=15.00),
            OrderItem(id="2", name="Salad", quantity=1, price=8.00)
        ]
        
        customer = CustomerInfo(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+49987654321"
        )
        
        delivery = DeliveryInfo(
            address="Hauptstraße 456",
            city="Munich",
            postal_code="80331",
            country="Germany",
            delivery_instructions="Leave at door, ring twice"
        )
        
        return Order(
            id="order_456",
            wix_order_id="wix_789",
            status=OrderStatus.PROCESSING,
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=23.00,
            created_at=datetime(2025, 9, 19, 18, 45)
        )
    
    def test_format_driver_receipt(self, sample_order):
        """Test driver receipt formatting."""
        formatter = DriverReceiptFormatter()
        result = formatter.format_receipt(sample_order)
        
        # Check header
        assert "LIEFERUNG" in result
        
        # Check delivery address (prominent)
        assert "LIEFERADRESSE:" in result
        assert "Hauptstraße 456" in result
        assert "80331 Munich" in result
        assert "Germany" in result
        
        # Check customer contact
        assert "KONTAKT:" in result
        assert "+49987654321" in result
        assert "jane@example.com" in result
        
        # Check delivery instructions
        assert "HINWEISE:" in result
        assert "Leave at door, ring twice" in result
        
        # Check order summary
        assert "BESTELLUNG:" in result
        assert "1x Pizza" in result
        assert "1x Salad" in result
        
        # Check total
        assert "GESAMT:" in result
        assert "23.00€" in result
        
        # Check payment status
        assert "Online bezahlt" in result


class TestCustomerReceiptFormatter:
    """Test cases for customer receipt formatter."""
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing."""
        items = [
            OrderItem(id="1", name="Burger", quantity=2, price=12.00),
            OrderItem(id="2", name="Fries", quantity=1, price=4.50, variant="Large")
        ]
        
        customer = CustomerInfo(
            first_name="Bob",
            last_name="Johnson",
            email="bob@example.com"
        )
        
        return Order(
            id="order_789",
            wix_order_id="wix_012",
            status=OrderStatus.COMPLETED,
            items=items,
            customer=customer,
            delivery=DeliveryInfo(),
            total_amount=28.50,
            created_at=datetime(2025, 9, 19, 20, 15)
        )
    
    def test_format_customer_receipt(self, sample_order):
        """Test customer receipt formatting."""
        formatter = CustomerReceiptFormatter()
        result = formatter.format_receipt(sample_order)
        
        # Check header
        assert "RECHNUNG" in result
        
        # Check detailed item list
        assert "ARTIKEL:" in result
        assert "Artikel" in result and "Anz" in result and "Preis" in result  # Table header
        assert "Burger" in result
        assert "2x" in result
        assert "24.00€" in result  # 2 * 12.00
        assert "Fries" in result
        assert "4.50€" in result
        assert "(Large)" in result  # Variant
        
        # Check totals calculation
        assert "Zwischensumme:" in result
        assert "MwSt (19%):" in result
        assert "GESAMT:" in result
        
        # Check payment info
        assert "Online-Zahlung" in result
        assert "Bezahlt" in result
        
        # Check legal footer
        assert "Steuerliche Angaben" in result
        assert "USt-IdNr:" in result


class TestReceiptFormatterFactory:
    """Test cases for receipt formatter factory."""
    
    def test_create_kitchen_formatter(self):
        """Test creating kitchen formatter."""
        formatter = ReceiptFormatterFactory.create_formatter(ReceiptType.KITCHEN)
        assert isinstance(formatter, KitchenReceiptFormatter)
    
    def test_create_driver_formatter(self):
        """Test creating driver formatter."""
        formatter = ReceiptFormatterFactory.create_formatter(ReceiptType.DRIVER)
        assert isinstance(formatter, DriverReceiptFormatter)
    
    def test_create_customer_formatter(self):
        """Test creating customer formatter."""
        formatter = ReceiptFormatterFactory.create_formatter(ReceiptType.CUSTOMER)
        assert isinstance(formatter, CustomerReceiptFormatter)
    
    def test_get_available_types(self):
        """Test getting available receipt types."""
        types = ReceiptFormatterFactory.get_available_types()
        
        assert ReceiptType.KITCHEN in types
        assert ReceiptType.DRIVER in types
        assert ReceiptType.CUSTOMER in types
        assert len(types) == 3


class TestFormatReceiptFunction:
    """Test cases for the format_receipt convenience function."""
    
    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing."""
        items = [OrderItem(id="1", name="Test Item", quantity=1, price=10.00)]
        customer = CustomerInfo(first_name="Test", last_name="User")
        
        return Order(
            id="test_order",
            wix_order_id="test_wix",
            status=OrderStatus.PENDING,
            items=items,
            customer=customer,
            delivery=DeliveryInfo(),
            total_amount=10.00,
            created_at=datetime.now()
        )
    
    def test_format_kitchen_receipt(self, sample_order):
        """Test formatting kitchen receipt via convenience function."""
        result = format_receipt(sample_order, ReceiptType.KITCHEN)
        
        assert "KÜCHE" in result
        assert "Test Item" in result
    
    def test_format_driver_receipt(self, sample_order):
        """Test formatting driver receipt via convenience function."""
        result = format_receipt(sample_order, ReceiptType.DRIVER)
        
        assert "LIEFERUNG" in result
        assert "Test Item" in result
    
    def test_format_customer_receipt(self, sample_order):
        """Test formatting customer receipt via convenience function."""
        result = format_receipt(sample_order, ReceiptType.CUSTOMER)
        
        assert "RECHNUNG" in result
        assert "Test Item" in result
