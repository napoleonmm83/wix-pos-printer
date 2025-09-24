"""
Configurable Receipt Formatter - Uses ConfigManager for customization
Replaces hardcoded Thai-specific elements with configurable options
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .models import Order, OrderItem
from .receipt_formatter import (
    BaseReceiptFormatter, ESCPOSFormatter, TextStyle, TextAlignment,
    ReceiptType, ReceiptFormatterFactory
)
from .config_manager import get_config

logger = logging.getLogger(__name__)


class ConfigurableKitchenReceiptFormatter(BaseReceiptFormatter):
    """Kitchen receipt formatter that uses configuration for customization."""

    def __init__(self):
        super().__init__()
        self.config = get_config()

    def format_receipt(self, order: Order) -> str:
        """Format a kitchen receipt with configurable styling."""
        receipt = ESCPOSFormatter.INIT

        # Kitchen Header - minimal und klar für hektische Küche (keine Emojis für Thermodrucker)
        kitchen_header = self.config.get_text('kitchen', 'header', 'KÜCHE')
        receipt += ESCPOSFormatter.format_text(
            kitchen_header,
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Order details with Wix order number
        wix_order_number = self._extract_order_number(order)
        if wix_order_number:
            order_text = self.config.get_text('kitchen', 'order_number', 'BESTELLUNG')
            receipt += ESCPOSFormatter.format_text(
                f"{order_text} #{wix_order_number}",
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF

        receipt += f"Order ID: {order.id[:8]}..." + ESCPOSFormatter.LF

        # Time and date
        if order.created_at:
            receipt += f"Zeit: {order.created_at.strftime('%H:%M')}" + ESCPOSFormatter.LF
            receipt += f"Datum: {order.created_at.strftime('%d.%m.%Y')}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Service type (ohne Emojis für Thermodrucker)
        service_type = self._determine_service_type(order)

        if service_type == "pickup":
            pickup_text = self.config.get_text('kitchen', 'pickup', 'ABHOLUNG')
            receipt += ESCPOSFormatter.format_text(
                pickup_text,
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        else:
            delivery_text = self.config.get_text('kitchen', 'delivery', 'LIEFERUNG')
            receipt += ESCPOSFormatter.format_text(
                delivery_text,
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Items with configurable cuisine styling
        receipt += ESCPOSFormatter.format_text("GERICHTE:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-", 32) + ESCPOSFormatter.LF

        for item in order.items:
            # Large quantity and name for kitchen visibility
            receipt += ESCPOSFormatter.format_text(
                f"[{item.quantity}x] {item.name}",
                TextStyle.DOUBLE_HEIGHT
            ) + ESCPOSFormatter.LF

            # Extract description/variant from order payload
            descriptions = self._extract_item_descriptions(item, order.raw_data)
            for desc in descriptions:
                receipt += ESCPOSFormatter.format_text(
                    f"     → {desc}",
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF

            # Special cooking instructions
            if item.notes:
                special_text = self.config.get_text('kitchen', 'special', 'SPEZIELL')
                receipt += ESCPOSFormatter.format_text(
                    f">>> {special_text}: {item.notes} <<<",
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF

                # Allergy warning (ohne Emojis)
                if self._contains_allergy_keywords(item.notes):
                    allergy_text = self.config.get_text('kitchen', 'allergy_warning', 'ALLERGIE WARNUNG')
                    receipt += ESCPOSFormatter.format_text(
                        f"!!! {allergy_text} !!!",
                        TextStyle.BOLD, TextAlignment.CENTER
                    ) + ESCPOSFormatter.LF

            receipt += ESCPOSFormatter.LF

        # Preparation priority and timing
        total_items = sum(item.quantity for item in order.items)
        prep_time = self._calculate_prep_time(order)

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        preparation_text = self.config.get_text('kitchen', 'preparation', 'ZUBEREITUNG')
        receipt += ESCPOSFormatter.format_text(f"{preparation_text}:", TextStyle.BOLD) + ESCPOSFormatter.LF
        total_dishes_text = self.config.get_text('kitchen', 'total_dishes', 'Gesamt Gerichte')
        estimated_time_text = self.config.get_text('kitchen', 'estimated_time', 'Geschätzte Zeit')
        minutes_text = self.config.get_text('kitchen', 'minutes', 'Min')
        receipt += f"{total_dishes_text}: {total_items}" + ESCPOSFormatter.LF
        receipt += f"{estimated_time_text}: {prep_time} {minutes_text}" + ESCPOSFormatter.LF

        # Customer name for pickup
        customer_name = self._get_customer_name(order)
        if customer_name and service_type == "pickup":
            customer_text = self.config.get_text('kitchen', 'customer', 'KUNDE')
            receipt += ESCPOSFormatter.format_text(
                f"{customer_text}: {customer_name}",
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF

        # Final instructions (ohne Emojis)
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        fresh_prepare_text = self.config.get_text('kitchen', 'fresh_prepare', 'FRISCH ZUBEREITEN')
        receipt += ESCPOSFormatter.format_text(
            f"*** {fresh_prepare_text} ***",
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF * 2
        receipt += ESCPOSFormatter.CUT_PARTIAL
        return receipt

    def _calculate_prep_time(self, order: Order) -> int:
        """Calculate preparation time using configurable modifiers."""
        if not order.items:
            return 10

        # Base time for kitchen setup
        base_time = 8

        # Time per unique dish type
        dish_time = len(order.items) * 3

        # Additional time for quantity
        total_quantity = sum(item.quantity for item in order.items)
        quantity_time = total_quantity * 2

        # Cuisine-specific complexity using config
        cuisine_complexity = 0
        for item in order.items:
            modifier = self.config.get_prep_time_modifier(item.name)
            cuisine_complexity += modifier * item.quantity

        return base_time + dish_time + quantity_time + cuisine_complexity

    def _extract_order_number(self, order: Order) -> Optional[str]:
        """Extract order number from raw data."""
        if order.raw_data and 'number' in order.raw_data:
            return str(order.raw_data['number'])
        return None

    def _determine_service_type(self, order: Order) -> str:
        """Determine if this is pickup or delivery from shipping info."""
        if order.raw_data and 'shippingInfo' in order.raw_data:
            shipping_info = order.raw_data['shippingInfo']
            title = shipping_info.get('title', '').lower()
            if 'abholung' in title or 'pickup' in title:
                return "pickup"
        return "delivery"

    def _extract_item_descriptions(self, item: OrderItem, raw_data: dict) -> List[str]:
        """Extract item descriptions from raw order data."""
        descriptions = []

        if not raw_data or 'lineItems' not in raw_data:
            return descriptions

        # Find matching line item in raw data
        for line_item in raw_data['lineItems']:
            if line_item.get('id') == item.id:
                # Extract description lines
                desc_lines = line_item.get('descriptionLines', [])
                for desc_line in desc_lines:
                    if desc_line.get('lineType') == 'PLAIN_TEXT':
                        text = desc_line.get('plainText', {}).get('original', '')
                        if text and text.strip():
                            descriptions.append(text.strip())
                break

        return descriptions

    def _get_customer_name(self, order: Order) -> Optional[str]:
        """Get customer name from billing info or buyer info."""
        if order.raw_data:
            # Try billing info first
            billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
            first_name = billing_info.get('firstName', '')
            last_name = billing_info.get('lastName', '')

            if first_name or last_name:
                return f"{first_name} {last_name}".strip()

        return None

    def _contains_allergy_keywords(self, text: str) -> bool:
        """Check if text contains allergy-related keywords."""
        allergy_keywords = [
            'allergie', 'allergisch', 'gluten', 'laktose', 'nuss', 'nüsse',
            'erdnuss', 'soja', 'ei', 'fisch', 'meeresfrüchte', 'sellerie'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in allergy_keywords)


class ConfigurableDriverReceiptFormatter(BaseReceiptFormatter):
    """Driver/pickup receipt formatter with configuration support."""

    def __init__(self):
        super().__init__()
        self.config = get_config()

    def format_receipt(self, order: Order) -> str:
        """Format a delivery/pickup receipt with configurable branding."""
        receipt = ESCPOSFormatter.INIT

        # Determine service type
        service_type = self._determine_service_type(order)
        wix_order_number = self._extract_order_number(order)

        # Header based on service type (ohne Emojis für Thermodrucker)
        if service_type == "pickup":
            pickup_text = self.config.get_text('service', 'pickup_location', 'ABHOLUNG')
            receipt += ESCPOSFormatter.format_text(
                f"{self.config.restaurant.name.upper()} - {pickup_text}",
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
            ready_pickup_text = self.config.get_text('service', 'ready_pickup', 'Bereit zur Abholung')
            receipt += ESCPOSFormatter.format_text(
                ready_pickup_text,
                TextStyle.NORMAL, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        else:
            delivery_text = self.config.get_text('service', 'delivery_address', 'LIEFERUNG')
            receipt += ESCPOSFormatter.format_text(
                f"{self.config.restaurant.name.upper()} - {delivery_text}",
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
            start_delivery_text = self.config.get_text('service', 'start_delivery', 'Lieferauftrag')
            receipt += ESCPOSFormatter.format_text(
                start_delivery_text,
                TextStyle.NORMAL, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Order identification
        if wix_order_number:
            order_text = self.config.get_text('service', 'order_number', 'BESTELLUNG')
            receipt += ESCPOSFormatter.format_text(
                f"{order_text} #{wix_order_number}",
                TextStyle.DOUBLE_WIDTH, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        order_id_text = self.config.get_text('service', 'order_id', 'ID')
        receipt += f"{order_id_text}: {order.id[:8]}..." + ESCPOSFormatter.LF

        # Timing information
        if order.created_at:
            ordered_at_text = self.config.get_text('service', 'ordered_at', 'Bestellt')
            receipt += f"{ordered_at_text}: {order.created_at.strftime('%H:%M')}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Customer information (prominent)
        customer_name = self._get_customer_name(order)
        customer_phone = self._get_customer_phone(order)

        customer_text = self.config.get_text('service', 'customer', 'KUNDE')
        receipt += ESCPOSFormatter.format_text(f"{customer_text}:", TextStyle.BOLD) + ESCPOSFormatter.LF
        if customer_name:
            receipt += ESCPOSFormatter.format_text(
                customer_name.upper(),
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF

        if customer_phone:
            receipt += ESCPOSFormatter.format_text(
                f"📞 {customer_phone}",
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Address information
        if service_type == "pickup":
            pickup_address = self._extract_pickup_address(order)
            if pickup_address:
                receipt += ESCPOSFormatter.format_text("ABHOLORT:", TextStyle.BOLD) + ESCPOSFormatter.LF
                receipt += ESCPOSFormatter.format_text(pickup_address, TextStyle.BOLD) + ESCPOSFormatter.LF
        else:
            delivery_address = self._extract_delivery_address(order)
            if delivery_address:
                receipt += ESCPOSFormatter.format_text("LIEFERADRESSE:", TextStyle.BOLD) + ESCPOSFormatter.LF
                for line in delivery_address:
                    receipt += ESCPOSFormatter.format_text(line, TextStyle.BOLD) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Order items (compact but clear)
        order_text = self.config.get_text('service', 'order', 'BESTELLUNG')
        receipt += ESCPOSFormatter.format_text(f"{order_text}:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        for item in order.items:
            receipt += f"{item.quantity}x {item.name}" + ESCPOSFormatter.LF
            # Add important variants/descriptions
            descriptions = self._extract_item_descriptions(item, order.raw_data)
            if descriptions:
                receipt += f"   ({descriptions[0]})" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Payment information with configurable currency
        payment_status = self._determine_payment_status(order)
        total_amount = self._get_total_amount(order)

        receipt += ESCPOSFormatter.format_text(
            ESCPOSFormatter.create_two_column_line(
                self.config.get_text('service', 'total', 'GESAMT') + ":",
                self.config.localization.currency.format_amount(total_amount)
            ),
            TextStyle.BOLD
        ) + ESCPOSFormatter.LF

        receipt += f"Zahlung: {payment_status}" + ESCPOSFormatter.LF

        # Final service instructions
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        if service_type == "pickup":
            ready_text = self.config.get_text('service', 'ready_pickup', 'BEREIT ZUR ABHOLUNG')
            receipt += ESCPOSFormatter.format_text(
                f">>> {ready_text} <<<",
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        else:
            start_text = self.config.get_text('service', 'start_delivery', 'LIEFERUNG STARTEN')
            receipt += ESCPOSFormatter.format_text(
                f">>> {start_text} <<<",
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF * 2
        receipt += ESCPOSFormatter.CUT_PARTIAL
        return receipt

    # Helper methods (similar to kitchen formatter, sharing common functionality)
    def _determine_service_type(self, order: Order) -> str:
        if order.raw_data and 'shippingInfo' in order.raw_data:
            shipping_info = order.raw_data['shippingInfo']
            title = shipping_info.get('title', '').lower()
            if 'abholung' in title or 'pickup' in title:
                return "pickup"
        return "delivery"

    def _extract_order_number(self, order: Order) -> Optional[str]:
        if order.raw_data and 'number' in order.raw_data:
            return str(order.raw_data['number'])
        return None

    def _get_customer_name(self, order: Order) -> Optional[str]:
        if not order.raw_data:
            return None

        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        first_name = billing_info.get('firstName', '')
        last_name = billing_info.get('lastName', '')

        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        return None

    def _get_customer_phone(self, order: Order) -> Optional[str]:
        if not order.raw_data:
            return None

        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        return billing_info.get('phone')

    def _extract_pickup_address(self, order: Order) -> Optional[str]:
        if not order.raw_data or 'shippingInfo' not in order.raw_data:
            return None

        shipping_info = order.raw_data['shippingInfo']
        logistics = shipping_info.get('logistics', {})
        pickup_details = logistics.get('pickupDetails', {})
        address = pickup_details.get('address', {})

        if address:
            parts = []
            if address.get('addressLine'):
                parts.append(address['addressLine'])
            if address.get('postalCode') and address.get('city'):
                parts.append(f"{address['postalCode']} {address['city']}")

            return '\n'.join(parts) if parts else None

        return None

    def _extract_delivery_address(self, order: Order) -> List[str]:
        if not order.delivery:
            return []

        address_lines = []
        if order.delivery.address:
            address_lines.append(order.delivery.address)

        if order.delivery.postal_code and order.delivery.city:
            address_lines.append(f"{order.delivery.postal_code} {order.delivery.city}")
        elif order.delivery.city:
            address_lines.append(order.delivery.city)

        return address_lines

    def _extract_item_descriptions(self, item: OrderItem, raw_data: dict) -> List[str]:
        descriptions = []

        if not raw_data or 'lineItems' not in raw_data:
            return descriptions

        for line_item in raw_data['lineItems']:
            if line_item.get('id') == item.id:
                desc_lines = line_item.get('descriptionLines', [])
                for desc_line in desc_lines:
                    if desc_line.get('lineType') == 'PLAIN_TEXT':
                        text = desc_line.get('plainText', {}).get('original', '')
                        if text and text.strip():
                            descriptions.append(text.strip())
                break

        return descriptions

    def _determine_payment_status(self, order: Order) -> str:
        if not order.raw_data:
            return "Unbekannt"

        payment_status = order.raw_data.get('paymentStatus', '').upper()
        if payment_status == 'NOT_PAID':
            return "Bar bei Abholung/Lieferung"
        elif payment_status in ['PAID', 'FULLY_PAID']:
            return "Online bezahlt"
        else:
            return f"Status: {payment_status}"

    def _get_total_amount(self, order: Order) -> float:
        if order.raw_data and 'priceSummary' in order.raw_data:
            total = order.raw_data['priceSummary'].get('total', {})
            amount = total.get('amount')
            if amount:
                try:
                    return float(amount)
                except:
                    pass

        return order.total_amount


class ConfigurableCustomerReceiptFormatter(BaseReceiptFormatter):
    """Customer receipt formatter with full configuration support."""

    def __init__(self):
        super().__init__()
        self.config = get_config()

    def format_receipt(self, order: Order) -> str:
        """Format a customer receipt with configurable branding and regional settings."""
        receipt = ESCPOSFormatter.INIT

        # Restaurant header (ohne Emojis für Thermodrucker)
        receipt += ESCPOSFormatter.format_text(
            self.config.restaurant.name.upper(),
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        # Configurable address
        for address_line in self.config.restaurant.address_lines:
            receipt += ESCPOSFormatter.format_text(
                address_line,
                TextStyle.NORMAL, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        if self.config.restaurant.phone:
            receipt += ESCPOSFormatter.format_text(
                f"Tel: {self.config.restaurant.phone}",
                TextStyle.NORMAL, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Receipt type and order number
        receipt += ESCPOSFormatter.format_text(
            self.config.get_text('customer', 'invoice', 'KUNDENRECHNUNG'),
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        wix_order_number = self._extract_order_number(order)
        if wix_order_number:
            receipt += ESCPOSFormatter.format_text(
                f"Bestellung #{wix_order_number}",
                TextStyle.DOUBLE_WIDTH, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Order details
        receipt += f"Bestell-ID: {order.id[:12]}..." + ESCPOSFormatter.LF

        if order.created_at:
            receipt += f"Datum: {order.created_at.strftime('%d.%m.%Y')}" + ESCPOSFormatter.LF
            receipt += f"Zeit: {order.created_at.strftime('%H:%M')}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Customer information
        customer_name = self._get_customer_name(order)
        customer_phone = self._get_customer_phone(order)
        customer_email = self._get_customer_email(order)

        if customer_name or customer_phone or customer_email:
            customer_text = self.config.get_text('service', 'customer', 'KUNDE')
            receipt += ESCPOSFormatter.format_text(f"{customer_text}:", TextStyle.BOLD) + ESCPOSFormatter.LF
            if customer_name:
                receipt += f"{customer_name}" + ESCPOSFormatter.LF
            if customer_phone:
                receipt += f"Tel: {customer_phone}" + ESCPOSFormatter.LF
            if customer_email:
                receipt += f"Email: {customer_email}" + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Detailed item list with configurable currency
        order_text = self.config.get_text('service', 'order', 'BESTELLUNG')
        receipt += ESCPOSFormatter.format_text(f"{order_text}:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Table header with configurable currency symbol
        receipt += ESCPOSFormatter.create_table_row(
            ["Artikel", "Anz", self.config.localization.currency.code],
            [16, 8, 8]
        ) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Items with descriptions
        subtotal = 0.0
        for item in order.items:
            item_price = self._get_item_price(item, order.raw_data)
            item_total = item_price * item.quantity
            subtotal += item_total

            # Main item line with configurable currency formatting
            name = item.name[:16] if len(item.name) > 16 else item.name
            qty = f"{item.quantity}x"
            price = f"{item_total:.{self.config.localization.currency.decimal_places}f}"

            receipt += ESCPOSFormatter.create_table_row(
                [name, qty, price],
                [16, 8, 8]
            ) + ESCPOSFormatter.LF

            # Item descriptions/variants
            descriptions = self._extract_item_descriptions(item, order.raw_data)
            for desc in descriptions:
                receipt += f"  + {desc}" + ESCPOSFormatter.LF

            # Unit price if quantity > 1
            if item.quantity > 1:
                receipt += f"  (à {self.config.localization.currency.format_amount(item_price)})" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Configurable tax calculation
        total_amount = self._get_total_amount(order)
        tax_info = self._calculate_tax(order, subtotal)

        receipt += ESCPOSFormatter.create_two_column_line(
            "Zwischensumme:",
            self.config.localization.currency.format_amount(subtotal)
        ) + ESCPOSFormatter.LF

        if tax_info['tax_amount'] > 0:
            receipt += ESCPOSFormatter.create_two_column_line(
                f"MwSt ({tax_info['tax_rate']:.1f}%):",
                self.config.localization.currency.format_amount(tax_info['tax_amount'])
            ) + ESCPOSFormatter.LF

        # Final total
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text(
            ESCPOSFormatter.create_two_column_line(
                self.config.get_text('service', 'total', 'GESAMT') + ":",
                self.config.localization.currency.format_amount(total_amount)
            ),
            TextStyle.BOLD
        ) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Payment information
        payment_status = self._determine_payment_status(order)
        receipt += f"Zahlungsart: {payment_status}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Configurable legal footer
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text(
            "Vielen Dank für Ihren Besuch!",
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        # Business information
        receipt += ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text(
            "Steuerliche Angaben",
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        # Configurable business ID
        receipt += self.config.localization.tax.business_id_format + ESCPOSFormatter.LF

        if self.config.localization.tax.footer_text:
            receipt += self.config.localization.tax.footer_text + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Configurable thank you message
        receipt += ESCPOSFormatter.format_text(
            self.config.branding.thank_you_message,
            TextStyle.BOLD, TextAlignment.CENTER
        ) + ESCPOSFormatter.LF

        if self.config.branding.thank_you_translation:
            receipt += ESCPOSFormatter.format_text(
                self.config.branding.thank_you_translation,
                TextStyle.NORMAL, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF * 2
        receipt += ESCPOSFormatter.CUT_PARTIAL
        return receipt

    def _calculate_tax(self, order: Order, subtotal: float) -> Dict[str, float]:
        """Calculate tax using configurable tax rates."""
        # Default to configuration tax rate
        tax_rate = self.config.localization.tax.get_rate_for_item_type("food")

        # Try to get actual tax from order data
        if order.raw_data:
            tax_info = order.raw_data.get('taxInfo', {}) or order.raw_data.get('taxSummary', {})
            if tax_info:
                total_tax = tax_info.get('totalTax', {})
                if isinstance(total_tax, dict) and 'amount' in total_tax:
                    try:
                        tax_amount = float(total_tax['amount'])
                        if tax_amount > 0 and subtotal > 0:
                            calculated_rate = (tax_amount / subtotal) * 100
                            return {'tax_rate': calculated_rate, 'tax_amount': tax_amount}
                        return {'tax_rate': 0.0, 'tax_amount': tax_amount}
                    except:
                        pass

        # Fallback to configuration rate
        tax_amount = subtotal * tax_rate
        return {'tax_rate': tax_rate * 100, 'tax_amount': tax_amount}

    # Helper methods (similar to other formatters)
    def _extract_order_number(self, order: Order) -> Optional[str]:
        if order.raw_data and 'number' in order.raw_data:
            return str(order.raw_data['number'])
        return None

    def _get_customer_name(self, order: Order) -> Optional[str]:
        if not order.raw_data:
            return None

        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        first_name = billing_info.get('firstName', '')
        last_name = billing_info.get('lastName', '')

        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        return None

    def _get_customer_phone(self, order: Order) -> Optional[str]:
        if not order.raw_data:
            return None

        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        return billing_info.get('phone')

    def _get_customer_email(self, order: Order) -> Optional[str]:
        if not order.raw_data:
            return None

        buyer_info = order.raw_data.get('buyerInfo', {})
        return buyer_info.get('email')

    def _get_item_price(self, item: OrderItem, raw_data: dict) -> float:
        if not raw_data or 'lineItems' not in raw_data:
            return item.price

        for line_item in raw_data['lineItems']:
            if line_item.get('id') == item.id:
                price_data = line_item.get('price', {})
                if isinstance(price_data, dict) and 'amount' in price_data:
                    try:
                        return float(price_data['amount'])
                    except:
                        pass

        return item.price

    def _get_total_amount(self, order: Order) -> float:
        if order.raw_data and 'priceSummary' in order.raw_data:
            total = order.raw_data['priceSummary'].get('total', {})
            amount = total.get('amount')
            if amount:
                try:
                    return float(amount)
                except:
                    pass

        return order.total_amount

    def _extract_item_descriptions(self, item: OrderItem, raw_data: dict) -> List[str]:
        descriptions = []

        if not raw_data or 'lineItems' not in raw_data:
            return descriptions

        for line_item in raw_data['lineItems']:
            if line_item.get('id') == item.id:
                desc_lines = line_item.get('descriptionLines', [])
                for desc_line in desc_lines:
                    if desc_line.get('lineType') == 'PLAIN_TEXT':
                        text = desc_line.get('plainText', {}).get('original', '')
                        if text and text.strip():
                            descriptions.append(text.strip())
                break

        return descriptions

    def _determine_payment_status(self, order: Order) -> str:
        if not order.raw_data:
            return "Unbekannt"

        payment_status = order.raw_data.get('paymentStatus', '').upper()
        if payment_status == 'NOT_PAID':
            return "Bar bei Abholung/Lieferung"
        elif payment_status in ['PAID', 'FULLY_PAID']:
            return "Online bezahlt"
        else:
            return f"Status: {payment_status}"


# Register the new configurable formatters
ReceiptFormatterFactory.register_formatter(ReceiptType.KITCHEN, ConfigurableKitchenReceiptFormatter)
ReceiptFormatterFactory.register_formatter(ReceiptType.DRIVER, ConfigurableDriverReceiptFormatter)
ReceiptFormatterFactory.register_formatter(ReceiptType.CUSTOMER, ConfigurableCustomerReceiptFormatter)