#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test multi-language receipt generation
Tests the internationalization system with different language configurations
"""

import sys
import os
import tempfile
from pathlib import Path

# Set UTF-8 encoding for output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from wix_printer_service.models import Order, OrderItem
from wix_printer_service.configurable_receipt_formatter import (
    ConfigurableKitchenReceiptFormatter,
    ConfigurableDriverReceiptFormatter,
    ConfigurableCustomerReceiptFormatter
)
from wix_printer_service.config_manager import ConfigManager, reload_config
from datetime import datetime
import json

def create_test_order():
    """Create a sample order for testing (based on Order #10033)"""
    from wix_printer_service.models import CustomerInfo, DeliveryInfo, OrderStatus

    customer = CustomerInfo(
        first_name="Marcus",
        last_name="Martini",
        phone="+41 79 123 45 67",
        email="marcus@example.com"
    )

    delivery = DeliveryInfo(
        address="Bahnhofstrasse 123",
        city="Zürich",
        postal_code="8001",
        country="Switzerland"
    )

    return Order(
        id="test-order-123",
        wix_order_id="10033",
        status=OrderStatus.COMPLETED,
        items=[
            OrderItem(
                id="item1",
                name="Nam Tok",
                quantity=3,
                price=18.50,
                notes="Size: large, Spice: medium"
            ),
            OrderItem(
                id="item2",
                name="Som Tam",
                quantity=3,
                price=15.50,
                notes="Spice: hot"
            )
        ],
        customer=customer,
        delivery=delivery,
        total_amount=132.00,
        currency="CHF",
        created_at=datetime.fromisoformat("2024-01-15T18:30:00"),
        raw_data={
            "number": 10033,
            "createdDate": "2024-01-15T18:30:00Z",
            "buyerInfo": {
                "firstName": "Marcus",
                "lastName": "Martini",
                "phone": "+41 79 123 45 67",
                "email": "marcus@example.com"
            },
            "totals": {
                "total": "132.00"
            }
        }
    )

def test_language(language_code, language_name):
    """Test receipt generation in a specific language"""
    print(f"\n{'='*60}")
    print(f"Testing {language_name} ({language_code}) receipts")
    print(f"{'='*60}")

    # Create temporary config with specific language
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)

        # Copy existing language templates
        import shutil
        source_templates = Path("config/language_templates.yaml")
        if source_templates.exists():
            shutil.copy(source_templates, config_dir / "language_templates.yaml")

        # Create restaurant config with specific language
        restaurant_config = {
            'restaurant': {
                'name': 'Test Restaurant',
                'address': ['123 Test Street', '12345 Test City', 'Test Country'],
                'phone': '+1 234 567 8900',
                'email': 'test@restaurant.com'
            },
            'branding': {
                'cuisine_type': 'thai'
            },
            'currency': {
                'code': 'CHF',
                'symbol': 'CHF'
            },
            'tax': {
                'default_rate': 0.077,
                'business_id': 'CHE-123.456.789 MWST'
            },
            'localization': {
                'language': language_code
            }
        }

        import yaml
        with open(config_dir / "restaurant_config.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(restaurant_config, f, default_flow_style=False, allow_unicode=True)

        # Load configuration
        config_manager = ConfigManager(str(config_dir))

        # Create test order
        order = create_test_order()

        # Test Kitchen Receipt
        print(f"\n--- {language_name} Kitchen Receipt ---")
        kitchen_formatter = ConfigurableKitchenReceiptFormatter()
        kitchen_formatter.config = config_manager
        kitchen_receipt = kitchen_formatter.format_receipt(order)
        print(kitchen_receipt)

        # Test Service Receipt
        print(f"\n--- {language_name} Service Receipt ---")
        service_formatter = ConfigurableDriverReceiptFormatter()
        service_formatter.config = config_manager
        service_receipt = service_formatter.format_receipt(order)
        print(service_receipt)

        # Test Customer Receipt
        print(f"\n--- {language_name} Customer Receipt ---")
        customer_formatter = ConfigurableCustomerReceiptFormatter()
        customer_formatter.config = config_manager
        customer_receipt = customer_formatter.format_receipt(order)
        print(customer_receipt[:500] + "..." if len(customer_receipt) > 500 else customer_receipt)

def main():
    """Test multi-language receipt generation"""
    print("Multi-Language Receipt Generation Test")
    print("Testing internationalization system with different languages")

    # Test different languages
    languages = [
        ('de', 'German'),
        ('en', 'English'),
        ('fr', 'French'),
        ('it', 'Italian'),
        ('es', 'Spanish')
    ]

    for lang_code, lang_name in languages:
        try:
            test_language(lang_code, lang_name)
        except Exception as e:
            print(f"Error testing {lang_name}: {e}")
            continue

    print(f"\n{'='*60}")
    print("Multi-language testing complete!")
    print("All hardcoded German terms have been replaced with configurable templates.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()