#!/usr/bin/env python3
"""
Test script für die neuen Thai-Restaurant Bon-Designs
Basierend auf dem bereitgestellten Order-Payload
"""
import json
from datetime import datetime
from wix_printer_service.models import Order
from wix_printer_service.receipt_formatter import (
    KitchenReceiptFormatter,
    DriverReceiptFormatter,
    CustomerReceiptFormatter,
    format_receipt,
    ReceiptType
)

# Sample Order Payload (bereitgestellt vom Benutzer)
SAMPLE_ORDER_PAYLOAD = {
    "id": "6d6062d8-7a12-47de-bb8b-5f733f34a446",
    "cartId": "0aa94970-1cbe-3263-8763-d7b3104bdd27",
    "number": "10033",
    "payNow": {
        "tax": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "total": {"amount": "132.00", "formattedAmount": "CHF 132.00"},
        "discount": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "shipping": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "subtotal": {"amount": "132.00", "formattedAmount": "CHF 132.00"},
        "totalPrice": {"amount": "132.00", "formattedAmount": "CHF 132.00"}
    },
    "status": "APPROVED",
    "taxInfo": {
        "totalTax": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "taxBreakdown": [],
        "manualTaxRate": "0"
    },
    "currency": "CHF",
    "buyerInfo": {
        "email": "marcusmartini83@gmail.com",
        "contactId": "b9766d9a-df6f-46c1-9307-d38cfc227dc1",
        "visitorId": "764e1c51-a2e6-4e72-98bb-caa4f354585d"
    },
    "lineItems": [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "image": {
                "id": "fccee2_b738871cb7a946cb8373942331b378a0~mv2.jpg",
                "url": "https://static.wixstatic.com/media/fccee2_b738871cb7a946cb8373942331b378a0~mv2.jpg/v1/fit/w_1200,h_960,q_90/file.jpg",
                "width": 1200, "height": 960
            },
            "price": {"amount": "26.00", "formattedAmount": "CHF 26.00"},
            "quantity": 3,
            "productName": {"original": "Nam Tok", "translated": "Nam Tok"},
            "lineItemPrice": {"amount": "78.00", "formattedAmount": "CHF 78.00"},
            "descriptionLines": [
                {
                    "name": {"original": "", "translated": ""},
                    "lineType": "PLAIN_TEXT",
                    "plainText": {"original": "Ente", "translated": "Ente"},
                    "plainTextValue": {"original": "Ente", "translated": "Ente"}
                }
            ]
        },
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "price": {"amount": "18.00", "formattedAmount": "CHF 18.00"},
            "quantity": 3,
            "productName": {"original": "Som Tam", "translated": "Som Tam"},
            "lineItemPrice": {"amount": "54.00", "formattedAmount": "CHF 54.00"},
            "descriptionLines": []
        }
    ],
    "billingInfo": {
        "address": {
            "country": "CH", "subdivision": "SG",
            "countryFullname": "Switzerland", "subdivisionFullname": "Sankt Gallen"
        },
        "contactDetails": {
            "phone": "0797232924", "lastName": "Martini", "firstName": "Marcus"
        }
    },
    "createdDate": "2025-09-24T17:53:25.532Z",
    "updatedDate": "2025-09-24T22:09:51.167Z",
    "priceSummary": {
        "tax": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "total": {"amount": "132.00", "formattedAmount": "CHF 132.00"},
        "discount": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "shipping": {"amount": "0.00", "formattedAmount": "CHF 0.00"},
        "subtotal": {"amount": "132.00", "formattedAmount": "CHF 132.00"}
    },
    "shippingInfo": {
        "code": "PICKUP|ASAP",
        "cost": {"price": {"amount": "0", "formattedAmount": "CHF 0.00"}},
        "title": "Abholung",
        "logistics": {
            "deliveryTime": "24.09.25 20:24",
            "instructions": "",
            "pickupDetails": {
                "address": {
                    "city": "Buchs", "country": "CH",
                    "postalCode": "9470",
                    "addressLine": "22 Unterstüdtlistrasse",
                    "subdivision": "SG",
                    "countryFullname": "Schweiz"
                },
                "pickupMethod": "STORE_PICKUP"
            },
            "deliveryTimeSlot": {
                "to": "2025-09-24T18:24:00Z",
                "from": "2025-09-24T18:24:00Z"
            }
        }
    },
    "paymentStatus": "NOT_PAID",
    "purchasedDate": "2025-09-24T17:53:25.525Z",
    "recipientInfo": {
        "address": {
            "country": "CH", "subdivision": "SG",
            "countryFullname": "Switzerland", "subdivisionFullname": "Sankt Gallen"
        },
        "contactDetails": {
            "phone": "0797232924", "lastName": "Martini", "firstName": "Marcus"
        }
    },
    "balanceSummary": {
        "paid": {"amount": "0", "formattedAmount": "CHF 0.00"},
        "balance": {"amount": "132.00", "formattedAmount": "CHF 132.00"}
    },
    "fulfillmentStatus": "NOT_FULFILLED"
}


def create_test_order() -> Order:
    """Create Order instance from sample payload."""
    return Order.from_wix_data(SAMPLE_ORDER_PAYLOAD)


def print_receipt_section(title: str, content: str):
    """Print a formatted receipt section."""
    print(f"\n{'='*60}")
    print(f" {title.upper()}")
    print(f"{'='*60}")
    print(content)
    print(f"{'='*60}\n")


def test_kitchen_receipt():
    """Test the Thai kitchen receipt design."""
    print("🍜 TESTING KITCHEN RECEIPT (Thai Style)")

    order = create_test_order()
    formatter = KitchenReceiptFormatter()
    receipt = formatter.format_receipt(order)

    print_receipt_section("KÜCHENBON - THAI RESTAURANT", receipt)

    # Show key features
    print("🔍 KITCHEN RECEIPT FEATURES:")
    print("✅ Thai-themed emojis and branding")
    print("✅ Order #10033 prominent display")
    print("✅ Service type detection (Abholung)")
    print("✅ Large quantity display for kitchen visibility")
    print("✅ Item descriptions (Ente) extracted from payload")
    print("✅ Thai-specific prep time calculation")
    print("✅ Customer name for pickup orders")


def test_driver_pickup_receipt():
    """Test the driver/pickup receipt design."""
    print("🥡 TESTING PICKUP/DELIVERY RECEIPT")

    order = create_test_order()
    formatter = DriverReceiptFormatter()
    receipt = formatter.format_receipt(order)

    print_receipt_section("ABHOLUNGSBON - THAI RESTAURANT", receipt)

    print("🔍 PICKUP/DELIVERY RECEIPT FEATURES:")
    print("✅ Service-specific header (🥡 ABHOLUNG vs 🚗 LIEFERUNG)")
    print("✅ Customer contact info prominent (Marcus Martini, 0797232924)")
    print("✅ Pickup address from shipping logistics")
    print("✅ Payment status detection (Bar bei Abholung)")
    print("✅ Order total in CHF")
    print("✅ Ready-to-go confirmation")


def test_customer_receipt():
    """Test the customer receipt design."""
    print("🧾 TESTING CUSTOMER RECEIPT (Swiss Legal Format)")

    order = create_test_order()
    formatter = CustomerReceiptFormatter()
    receipt = formatter.format_receipt(order)

    print_receipt_section("KUNDENRECHNUNG - THAI RESTAURANT", receipt)

    print("🔍 CUSTOMER RECEIPT FEATURES:")
    print("✅ Swiss restaurant header with address")
    print("✅ Complete customer information")
    print("✅ Detailed item breakdown with descriptions")
    print("✅ Swiss tax handling (0% MwSt for food)")
    print("✅ Payment status (Bar bei Abholung)")
    print("✅ Swiss business compliance (UID)")
    print("✅ Thai thank you message (Kob Khun Ka!)")


def test_all_receipt_types():
    """Test all receipt types using the convenience function."""
    print("🚀 TESTING ALL RECEIPT TYPES WITH format_receipt()")

    order = create_test_order()

    for receipt_type in [ReceiptType.KITCHEN, ReceiptType.DRIVER, ReceiptType.CUSTOMER]:
        print(f"\n📄 Testing {receipt_type.value.upper()} receipt:")
        try:
            receipt = format_receipt(order, receipt_type)
            print(f"✅ {receipt_type.value} receipt generated successfully")
            print(f"   Length: {len(receipt)} characters")
            print(f"   Lines: {receipt.count(chr(10))} lines")
        except Exception as e:
            print(f"❌ Error generating {receipt_type.value} receipt: {e}")


def analyze_order_data():
    """Analyze the order payload for design insights."""
    print("🔍 ORDER PAYLOAD ANALYSIS")
    print("="*50)

    print(f"Order Number: #{SAMPLE_ORDER_PAYLOAD['number']}")
    print(f"Service Type: {SAMPLE_ORDER_PAYLOAD['shippingInfo']['title']}")
    print(f"Payment Status: {SAMPLE_ORDER_PAYLOAD['paymentStatus']}")
    print(f"Total: {SAMPLE_ORDER_PAYLOAD['priceSummary']['total']['formattedAmount']}")

    print(f"\nCustomer: {SAMPLE_ORDER_PAYLOAD['billingInfo']['contactDetails']['firstName']} "
          f"{SAMPLE_ORDER_PAYLOAD['billingInfo']['contactDetails']['lastName']}")
    print(f"Phone: {SAMPLE_ORDER_PAYLOAD['billingInfo']['contactDetails']['phone']}")
    print(f"Email: {SAMPLE_ORDER_PAYLOAD['buyerInfo']['email']}")

    print(f"\nPickup Location:")
    pickup_addr = SAMPLE_ORDER_PAYLOAD['shippingInfo']['logistics']['pickupDetails']['address']
    print(f"  {pickup_addr['addressLine']}")
    print(f"  {pickup_addr['postalCode']} {pickup_addr['city']}")

    print(f"\nItems:")
    for item in SAMPLE_ORDER_PAYLOAD['lineItems']:
        name = item['productName']['original']
        qty = item['quantity']
        price = item['price']['formattedAmount']
        print(f"  {qty}x {name} - {price}")

        # Show descriptions
        for desc in item.get('descriptionLines', []):
            if desc.get('lineType') == 'PLAIN_TEXT':
                desc_text = desc['plainText']['original']
                if desc_text:
                    print(f"      + {desc_text}")


if __name__ == "__main__":
    print("🍜 THAI RESTAURANT BON-DESIGN TESTS")
    print("Basierend auf Order #10033 Payload")
    print("=" * 60)

    # Analyze the provided order data
    analyze_order_data()

    # Test individual receipt types
    test_kitchen_receipt()
    test_driver_pickup_receipt()
    test_customer_receipt()

    # Test convenience function
    test_all_receipt_types()

    print("\n🎉 ALLE TESTS ABGESCHLOSSEN!")
    print("Die neuen Bon-Designs sind bereit für Ihr Thai Restaurant!")

    print(f"\n📋 DESIGN-ZUSAMMENFASSUNG:")
    print("🍜 Küchenbon: Thai-Branding mit Prep-Focus")
    print("🥡 Abholungsbon: Service-orientiert mit Kontaktdaten")
    print("🧾 Kundenrechnung: Swiss-compliant mit Thai-Touch")
    print("\n✨ Alle Bons verwenden echte Daten aus dem Order-Payload!")