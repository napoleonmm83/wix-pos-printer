#!/usr/bin/env python3
"""
Quick test for kitchen header simplification
"""

import sys
from pathlib import Path
import tempfile

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from wix_printer_service.models import Order, OrderItem, OrderStatus, CustomerInfo, DeliveryInfo
from wix_printer_service.configurable_receipt_formatter import ConfigurableKitchenReceiptFormatter
from wix_printer_service.config_manager import ConfigManager
from datetime import datetime

def test_kitchen_header():
    """Test the simplified kitchen header"""

    # Create minimal test order
    customer = CustomerInfo(first_name="Marcus", last_name="Martini")
    delivery = DeliveryInfo(address="Test Address", city="Test City")

    order = Order(
        id="test-123",
        wix_order_id="10033",
        status=OrderStatus.COMPLETED,
        items=[
            OrderItem(id="1", name="Nam Tok", quantity=3, price=18.50),
            OrderItem(id="2", name="Som Tam", quantity=2, price=15.50)
        ],
        customer=customer,
        delivery=delivery,
        total_amount=100.00,
        currency="CHF",
        raw_data={"number": 10033}
    )

    # Test with simple config
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)

        # Create minimal config
        import yaml
        config = {
            'restaurant': {'name': 'Thai Restaurant'},
            'branding': {'cuisine_type': 'thai'},
            'localization': {'language': 'de'}
        }

        with open(config_dir / "restaurant_config.yaml", 'w') as f:
            yaml.dump(config, f)

        # Load config and test
        config_manager = ConfigManager(str(config_dir))
        formatter = ConfigurableKitchenReceiptFormatter()
        formatter.config = config_manager

        receipt = formatter.format_receipt(order)

        # Show just the first few lines (header)
        lines = receipt.split('\n')
        print("=== KITCHEN RECEIPT HEADER (simplified) ===")
        for i, line in enumerate(lines[:10]):
            if line.strip():  # Only show non-empty lines
                # Remove ESC/POS control characters AND emojis for display
                clean_line = ''.join(c for c in line if ord(c) >= 32 and ord(c) < 127 or c in '\n\t')
                print(f"{i+1:2d}: {clean_line}")
        print("\n=== FULL STRUCTURE ===")
        # Show structure without control chars and emojis
        clean_receipt = ''.join(c for c in receipt if ord(c) >= 32 and ord(c) < 127 or c in '\n\t ')
        structure_lines = clean_receipt.split('\n')[:15]  # First 15 lines
        for i, line in enumerate(structure_lines):
            if line.strip():
                print(f"{i+1:2d}: {line}")

if __name__ == "__main__":
    test_kitchen_header()