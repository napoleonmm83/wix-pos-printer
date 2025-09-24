"""
Receipt Layout Engine for generating formatted receipts.
Provides base classes and utilities for creating professional receipt layouts.
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

from .models import Order, OrderItem, CustomerInfo, DeliveryInfo

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class ReceiptType(Enum):
    """Receipt type enumeration."""
    KITCHEN = "kitchen"
    DRIVER = "driver"
    CUSTOMER = "customer"


class TextAlignment(Enum):
    """Text alignment options."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class TextStyle(Enum):
    """Text style options."""
    NORMAL = "normal"
    BOLD = "bold"
    UNDERLINE = "underline"
    DOUBLE_HEIGHT = "double_height"
    DOUBLE_WIDTH = "double_width"


class ESCPOSFormatter:
    """Utility class for ESC/POS formatting commands."""
    
    # ESC/POS Commands
    ESC = '\x1b'
    INIT = ESC + '@'
    
    # Text formatting
    BOLD_ON = ESC + 'E' + '\x01'
    BOLD_OFF = ESC + 'E' + '\x00'
    UNDERLINE_ON = ESC + '-' + '\x01'
    UNDERLINE_OFF = ESC + '-' + '\x00'
    DOUBLE_HEIGHT_ON = ESC + '!' + '\x10'
    DOUBLE_WIDTH_ON = ESC + '!' + '\x20'
    DOUBLE_SIZE_ON = ESC + '!' + '\x30'
    RESET_SIZE = ESC + '!' + '\x00'
    
    # Alignment
    ALIGN_LEFT = ESC + 'a' + '\x00'
    ALIGN_CENTER = ESC + 'a' + '\x01'
    ALIGN_RIGHT = ESC + 'a' + '\x02'
    
    # Line feeds and cuts
    LF = '\n'
    CUT_PARTIAL = ESC + 'm'
    CUT_FULL = ESC + 'i'
    
    @staticmethod
    def format_text(text: str, style: TextStyle = TextStyle.NORMAL, 
                   alignment: TextAlignment = TextAlignment.LEFT) -> str:
        """
        Format text with specified style and alignment.
        
        Args:
            text: Text to format
            style: Text style to apply
            alignment: Text alignment
            
        Returns:
            Formatted text with ESC/POS commands
        """
        formatted = ""
        
        # Apply alignment
        if alignment == TextAlignment.CENTER:
            formatted += ESCPOSFormatter.ALIGN_CENTER
        elif alignment == TextAlignment.RIGHT:
            formatted += ESCPOSFormatter.ALIGN_RIGHT
        else:
            formatted += ESCPOSFormatter.ALIGN_LEFT
        
        # Apply style
        if style == TextStyle.BOLD:
            formatted += ESCPOSFormatter.BOLD_ON
        elif style == TextStyle.UNDERLINE:
            formatted += ESCPOSFormatter.UNDERLINE_ON
        elif style == TextStyle.DOUBLE_HEIGHT:
            formatted += ESCPOSFormatter.DOUBLE_HEIGHT_ON
        elif style == TextStyle.DOUBLE_WIDTH:
            formatted += ESCPOSFormatter.DOUBLE_WIDTH_ON
        
        # Add text
        formatted += text
        
        # Reset formatting
        if style != TextStyle.NORMAL:
            if style == TextStyle.BOLD:
                formatted += ESCPOSFormatter.BOLD_OFF
            elif style == TextStyle.UNDERLINE:
                formatted += ESCPOSFormatter.UNDERLINE_OFF
            elif style in [TextStyle.DOUBLE_HEIGHT, TextStyle.DOUBLE_WIDTH]:
                formatted += ESCPOSFormatter.RESET_SIZE
        
        # Reset alignment to left
        if alignment != TextAlignment.LEFT:
            formatted += ESCPOSFormatter.ALIGN_LEFT
        
        return formatted
    
    @staticmethod
    def create_separator(char: str = "=", width: int = 32) -> str:
        """Create a separator line."""
        return char * width
    
    @staticmethod
    def create_two_column_line(left: str, right: str, width: int = 32) -> str:
        """Create a line with text aligned to left and right."""
        available_width = width - len(right)
        if len(left) > available_width:
            left = left[:available_width-3] + "..."
        
        spaces_needed = width - len(left) - len(right)
        return left + " " * spaces_needed + right
    
    @staticmethod
    def create_table_row(columns: List[str], widths: List[int]) -> str:
        """Create a table row with specified column widths."""
        if len(columns) != len(widths):
            raise ValueError("Number of columns must match number of widths")
        
        row = ""
        for i, (col, width) in enumerate(zip(columns, widths)):
            if len(col) > width:
                col = col[:width-3] + "..."
            
            if i == len(columns) - 1:  # Last column - right align
                row += col.rjust(width)
            else:
                row += col.ljust(width)
        
        return row


class BaseReceiptFormatter(ABC):
    """Base class for receipt formatters."""
    
    def __init__(self):
        """Initialize the formatter with configuration."""
        self.restaurant_name = os.getenv('RESTAURANT_NAME', 'Restaurant')
        self.restaurant_address = os.getenv('RESTAURANT_ADDRESS', '')
        self.restaurant_phone = os.getenv('RESTAURANT_PHONE', '')
        self.restaurant_email = os.getenv('RESTAURANT_EMAIL', '')
        self.tax_rate = float(os.getenv('TAX_RATE', '0.19'))  # 19% default
        
        # Layout configuration
        self.receipt_width = int(os.getenv('RECEIPT_WIDTH', '32'))
        self.date_format = os.getenv('DATE_FORMAT', '%d.%m.%Y %H:%M')
        
        logger.debug(f"Initialized {self.__class__.__name__} formatter")
    
    @abstractmethod
    def format_receipt(self, order: Order) -> str:
        """
        Format a receipt for the given order.
        
        Args:
            order: Order to format
            
        Returns:
            Formatted receipt content
        """
        pass
    
    def _format_header(self, title: str) -> str:
        """Format receipt header with restaurant info and title."""
        header = ESCPOSFormatter.INIT
        
        # Restaurant name
        if self.restaurant_name:
            header += ESCPOSFormatter.format_text(
                self.restaurant_name, 
                TextStyle.BOLD, 
                TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        
        # Restaurant address
        if self.restaurant_address:
            header += ESCPOSFormatter.format_text(
                self.restaurant_address, 
                alignment=TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        
        # Restaurant contact
        if self.restaurant_phone:
            header += ESCPOSFormatter.format_text(
                f"Tel: {self.restaurant_phone}", 
                alignment=TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        
        # Separator
        header += ESCPOSFormatter.create_separator() + ESCPOSFormatter.LF
        
        # Receipt title
        header += ESCPOSFormatter.format_text(
            title, 
            TextStyle.BOLD, 
            TextAlignment.CENTER
        ) + ESCPOSFormatter.LF
        
        # Separator
        header += ESCPOSFormatter.create_separator() + ESCPOSFormatter.LF
        
        return header
    
    def _format_order_info(self, order: Order) -> str:
        """Format basic order information."""
        info = ""
        
        # Order ID
        info += f"Bestellung: {order.id}" + ESCPOSFormatter.LF
        
        # Order date
        if order.created_at:
            formatted_date = order.created_at.strftime(self.date_format)
            info += f"Datum: {formatted_date}" + ESCPOSFormatter.LF
        
        # Customer name if available
        if order.customer and (order.customer.first_name or order.customer.last_name):
            name_parts = []
            if order.customer.first_name:
                name_parts.append(order.customer.first_name)
            if order.customer.last_name:
                name_parts.append(order.customer.last_name)
            info += f"Kunde: {' '.join(name_parts)}" + ESCPOSFormatter.LF
        
        info += ESCPOSFormatter.LF
        return info
    
    def _format_items(self, order: Order, show_prices: bool = False) -> str:
        """Format order items."""
        items_text = ""
        
        for item in order.items:
            # Item name and quantity
            if show_prices:
                # Three column layout: Name | Qty | Price
                name_col = item.name[:18] if len(item.name) > 18 else item.name
                qty_col = f"{item.quantity}x"
                price_col = f"{item.price:.2f}€"
                
                items_text += ESCPOSFormatter.create_table_row(
                    [name_col, qty_col, price_col], 
                    [18, 6, 8]
                ) + ESCPOSFormatter.LF
            else:
                # Simple layout: Quantity x Name
                items_text += f"{item.quantity}x {item.name}" + ESCPOSFormatter.LF
            
            # Variant information
            if item.variant:
                items_text += f"   Variante: {item.variant}" + ESCPOSFormatter.LF
            
            # Notes/special requests
            if item.notes:
                items_text += ESCPOSFormatter.format_text(
                    f"   >>> {item.notes} <<<", 
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF
        
        return items_text
    
    def _format_footer(self) -> str:
        """Format receipt footer."""
        footer = ESCPOSFormatter.LF
        footer += ESCPOSFormatter.create_separator() + ESCPOSFormatter.LF
        footer += ESCPOSFormatter.format_text(
            "Vielen Dank!", 
            alignment=TextAlignment.CENTER
        ) + ESCPOSFormatter.LF
        
        if self.restaurant_email:
            footer += ESCPOSFormatter.format_text(
                self.restaurant_email, 
                alignment=TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        
        footer += ESCPOSFormatter.LF * 2
        return footer
    
    def _calculate_totals(self, order: Order) -> Dict[str, float]:
        """Calculate order totals including tax."""
        subtotal = sum(item.price * item.quantity for item in order.items)
        tax_amount = subtotal * self.tax_rate
        total = subtotal + tax_amount
        
        return {
            'subtotal': subtotal,
            'tax_amount': tax_amount,
            'tax_rate': self.tax_rate,
            'total': total
        }


class ReceiptFormatterFactory:
    """Factory for creating receipt formatters."""
    
    _formatters = {}
    
    @classmethod
    def register_formatter(cls, receipt_type: ReceiptType, formatter_class):
        """Register a formatter for a receipt type."""
        cls._formatters[receipt_type] = formatter_class
    
    @classmethod
    def create_formatter(cls, receipt_type: ReceiptType) -> BaseReceiptFormatter:
        """Create a formatter for the specified receipt type."""
        formatter_class = cls._formatters.get(receipt_type)
        if not formatter_class:
            raise ValueError(f"No formatter registered for receipt type: {receipt_type}")
        
        return formatter_class()
    
    @classmethod
    def get_available_types(cls) -> List[ReceiptType]:
        """Get list of available receipt types."""
        return list(cls._formatters.keys())


class KitchenReceiptFormatter(BaseReceiptFormatter):
    """Formatter for kitchen receipts focused on preparation details."""

    def format_receipt(self, order: Order) -> str:
        """Format a kitchen receipt with Thai restaurant styling."""
        receipt = ESCPOSFormatter.INIT

        # Thai Restaurant Header
        receipt += ESCPOSFormatter.format_text("🍜 THAI KÜCHE 🍜", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("BESTELLUNG ZUBEREITEN", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Order details with Wix order number
        wix_order_number = self._extract_order_number(order)
        if wix_order_number:
            receipt += ESCPOSFormatter.format_text(f"Bestellung #{wix_order_number}", TextStyle.BOLD) + ESCPOSFormatter.LF

        receipt += f"Order ID: {order.id[:8]}..." + ESCPOSFormatter.LF

        # Time and date
        if order.created_at:
            receipt += f"Zeit: {order.created_at.strftime('%H:%M')}" + ESCPOSFormatter.LF
            receipt += f"Datum: {order.created_at.strftime('%d.%m.%Y')}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Service type with emoji
        service_type = self._determine_service_type(order)
        if service_type == "pickup":
            receipt += ESCPOSFormatter.format_text("🥡 ABHOLUNG 🥡", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
        else:
            receipt += ESCPOSFormatter.format_text("🚗 LIEFERUNG 🚗", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Items with Thai-style formatting
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
                receipt += ESCPOSFormatter.format_text(
                    f"⚠️  SPEZIELL: {item.notes} ⚠️",
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF

                # Allergy warning with Thai context
                if self._contains_allergy_keywords(item.notes):
                    receipt += ESCPOSFormatter.format_text(
                        "🚨 ALLERGIE WARNUNG 🚨",
                        TextStyle.BOLD, TextAlignment.CENTER
                    ) + ESCPOSFormatter.LF

            receipt += ESCPOSFormatter.LF

        # Preparation priority and timing
        total_items = sum(item.quantity for item in order.items)
        prep_time = self._calculate_thai_prep_time(order)

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("ZUBEREITUNG:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += f"Gesamt Gerichte: {total_items}" + ESCPOSFormatter.LF
        receipt += f"Geschätzte Zeit: {prep_time} Min" + ESCPOSFormatter.LF

        # Customer name for pickup
        customer_name = self._get_customer_name(order)
        if customer_name and service_type == "pickup":
            receipt += ESCPOSFormatter.format_text(
                f"KUNDE: {customer_name}",
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF

        # Final instructions
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("🔥 FRISCH ZUBEREITEN 🔥", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF * 2
        receipt += ESCPOSFormatter.CUT_PARTIAL
        return receipt
    
    def _contains_allergy_keywords(self, text: str) -> bool:
        """Check if text contains allergy-related keywords."""
        allergy_keywords = [
            'allergie', 'allergisch', 'gluten', 'laktose', 'nuss', 'nüsse',
            'erdnuss', 'soja', 'ei', 'fisch', 'meeresfrüchte', 'sellerie'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in allergy_keywords)
    
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

    def _calculate_thai_prep_time(self, order: Order) -> int:
        """Calculate preparation time for Thai dishes."""
        if not order.items:
            return 10

        # Base time for kitchen setup
        base_time = 8

        # Time per unique dish type
        dish_time = len(order.items) * 3

        # Additional time for quantity
        total_quantity = sum(item.quantity for item in order.items)
        quantity_time = total_quantity * 2

        # Thai-specific complexity
        thai_complexity = 0
        for item in order.items:
            # Dishes like Nam Tok, Som Tam require more prep
            if any(word in item.name.lower() for word in ['nam tok', 'som tam', 'pad thai', 'curry']):
                thai_complexity += 3

        return base_time + dish_time + quantity_time + thai_complexity

    def _get_customer_name(self, order: Order) -> Optional[str]:
        """Get customer name from billing info or buyer info."""
        if order.raw_data:
            # Try billing info first
            billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
            first_name = billing_info.get('firstName', '')
            last_name = billing_info.get('lastName', '')

            if first_name or last_name:
                return f"{first_name} {last_name}".strip()

            # Fallback to buyer info
            buyer_info = order.raw_data.get('buyerInfo', {})
            return buyer_info.get('email', '').split('@')[0]  # Use email prefix as name

        return None

    def _estimate_prep_time(self, order: Order) -> Optional[int]:
        """Estimate preparation time based on items."""
        return self._calculate_thai_prep_time(order)


class DriverReceiptFormatter(BaseReceiptFormatter):
    """Formatter for driver/pickup receipts with enhanced delivery/pickup information."""

    def format_receipt(self, order: Order) -> str:
        """Format a delivery/pickup receipt."""
        receipt = ESCPOSFormatter.INIT

        # Determine service type
        service_type = self._determine_service_type(order)
        wix_order_number = self._extract_order_number(order)

        # Header based on service type
        if service_type == "pickup":
            receipt += ESCPOSFormatter.format_text("🥡 THAI ABHOLUNG 🥡", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.format_text("Bereit zur Abholung", TextStyle.NORMAL, TextAlignment.CENTER) + ESCPOSFormatter.LF
        else:
            receipt += ESCPOSFormatter.format_text("🚗 THAI LIEFERUNG 🚗", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.format_text("Lieferauftrag", TextStyle.NORMAL, TextAlignment.CENTER) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Order identification
        if wix_order_number:
            receipt += ESCPOSFormatter.format_text(
                f"BESTELLUNG #{wix_order_number}",
                TextStyle.DOUBLE_WIDTH, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += f"ID: {order.id[:8]}..." + ESCPOSFormatter.LF

        # Timing information
        if order.created_at:
            receipt += f"Bestellt: {order.created_at.strftime('%H:%M')}" + ESCPOSFormatter.LF

        # Get pickup/delivery time from payload
        delivery_time = self._extract_delivery_time(order)
        if delivery_time:
            if service_type == "pickup":
                receipt += f"Abholung: {delivery_time}" + ESCPOSFormatter.LF
            else:
                receipt += f"Lieferung: {delivery_time}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Customer information (prominent)
        customer_name = self._get_customer_name(order)
        customer_phone = self._get_customer_phone(order)

        receipt += ESCPOSFormatter.format_text("KUNDE:", TextStyle.BOLD) + ESCPOSFormatter.LF
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

        # Address for delivery or pickup location for pickup
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

        # Special delivery instructions
        delivery_instructions = self._extract_delivery_instructions(order)
        if delivery_instructions:
            receipt += ESCPOSFormatter.format_text("📝 HINWEISE:", TextStyle.BOLD) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.format_text(
                delivery_instructions,
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.LF

        # Order items (compact but clear)
        receipt += ESCPOSFormatter.format_text("BESTELLUNG:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        for item in order.items:
            receipt += f"{item.quantity}x {item.name}" + ESCPOSFormatter.LF
            # Add important variants/descriptions
            descriptions = self._extract_item_descriptions(item, order.raw_data)
            if descriptions:
                receipt += f"   ({descriptions[0]})" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Payment information
        payment_status = self._determine_payment_status(order)
        total_amount = self._get_total_amount(order)

        receipt += ESCPOSFormatter.format_text(
            ESCPOSFormatter.create_two_column_line("GESAMT:", f"CHF {total_amount:.2f}"),
            TextStyle.BOLD
        ) + ESCPOSFormatter.LF

        receipt += f"Zahlung: {payment_status}" + ESCPOSFormatter.LF

        # Final service instructions
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        if service_type == "pickup":
            receipt += ESCPOSFormatter.format_text(
                "✅ BEREIT ZUR ABHOLUNG ✅",
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF
        else:
            receipt += ESCPOSFormatter.format_text(
                "🚀 LIEFERUNG STARTEN 🚀",
                TextStyle.BOLD, TextAlignment.CENTER
            ) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF * 2
        receipt += ESCPOSFormatter.CUT_PARTIAL
        return receipt

    def _determine_service_type(self, order: Order) -> str:
        """Determine if this is pickup or delivery from shipping info."""
        if order.raw_data and 'shippingInfo' in order.raw_data:
            shipping_info = order.raw_data['shippingInfo']
            title = shipping_info.get('title', '').lower()
            if 'abholung' in title or 'pickup' in title:
                return "pickup"
        return "delivery"

    def _extract_order_number(self, order: Order) -> Optional[str]:
        """Extract order number from raw data."""
        if order.raw_data and 'number' in order.raw_data:
            return str(order.raw_data['number'])
        return None

    def _extract_delivery_time(self, order: Order) -> Optional[str]:
        """Extract delivery/pickup time from order."""
        if not order.raw_data or 'shippingInfo' not in order.raw_data:
            return None

        shipping_info = order.raw_data['shippingInfo']
        logistics = shipping_info.get('logistics', {})

        # Try delivery time first
        delivery_time = logistics.get('deliveryTime')
        if delivery_time:
            return delivery_time

        # Try delivery time slot
        time_slot = logistics.get('deliveryTimeSlot', {})
        from_time = time_slot.get('from')
        if from_time:
            # Parse ISO format and return readable time
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
                return dt.strftime('%d.%m.%Y %H:%M')
            except:
                pass

        return None

    def _get_customer_name(self, order: Order) -> Optional[str]:
        """Get customer name from billing or recipient info."""
        if not order.raw_data:
            return None

        # Try billing info first
        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        first_name = billing_info.get('firstName', '')
        last_name = billing_info.get('lastName', '')

        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        # Try recipient info
        recipient_info = order.raw_data.get('recipientInfo', {}).get('contactDetails', {})
        first_name = recipient_info.get('firstName', '')
        last_name = recipient_info.get('lastName', '')

        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        return None

    def _get_customer_phone(self, order: Order) -> Optional[str]:
        """Get customer phone from billing or recipient info."""
        if not order.raw_data:
            return None

        # Try billing info first
        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        phone = billing_info.get('phone')
        if phone:
            return phone

        # Try recipient info
        recipient_info = order.raw_data.get('recipientInfo', {}).get('contactDetails', {})
        return recipient_info.get('phone')

    def _extract_pickup_address(self, order: Order) -> Optional[str]:
        """Extract pickup address from shipping info."""
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
            elif address.get('city'):
                parts.append(address['city'])

            return '\n'.join(parts) if parts else None

        return None

    def _extract_delivery_address(self, order: Order) -> List[str]:
        """Extract delivery address lines."""
        if not order.delivery:
            return []

        address_lines = []
        if order.delivery.address:
            address_lines.append(order.delivery.address)

        if order.delivery.postal_code and order.delivery.city:
            address_lines.append(f"{order.delivery.postal_code} {order.delivery.city}")
        elif order.delivery.city:
            address_lines.append(order.delivery.city)

        if order.delivery.country:
            address_lines.append(order.delivery.country)

        return address_lines

    def _extract_delivery_instructions(self, order: Order) -> Optional[str]:
        """Extract delivery instructions from shipping info or delivery info."""
        # Try shipping info logistics first
        if order.raw_data and 'shippingInfo' in order.raw_data:
            logistics = order.raw_data['shippingInfo'].get('logistics', {})
            instructions = logistics.get('instructions')
            if instructions and instructions.strip():
                return instructions.strip()

        # Try delivery info
        if order.delivery and order.delivery.delivery_instructions:
            return order.delivery.delivery_instructions

        return None

    def _determine_payment_status(self, order: Order) -> str:
        """Determine payment status from raw data."""
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
        """Get total amount from price summary or order total."""
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


class CustomerReceiptFormatter(BaseReceiptFormatter):
    """Formatter for customer receipts with full billing details and Swiss-specific formatting."""

    def format_receipt(self, order: Order) -> str:
        """Format a customer receipt with Thai restaurant branding."""
        receipt = ESCPOSFormatter.INIT

        # Restaurant header with Thai branding
        receipt += ESCPOSFormatter.format_text("🍜 THAI RESTAURANT 🍜", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("Unterstüdtlistrasse 22", TextStyle.NORMAL, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("9470 Buchs SG", TextStyle.NORMAL, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("Schweiz", TextStyle.NORMAL, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Receipt type and order number
        receipt += ESCPOSFormatter.format_text("KUNDENRECHNUNG", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF

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

        # Service type
        service_type = self._determine_service_type(order)
        receipt += f"Service: {service_type.title()}" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Customer information
        customer_name = self._get_customer_name(order)
        customer_phone = self._get_customer_phone(order)
        customer_email = self._get_customer_email(order)

        if customer_name or customer_phone or customer_email:
            receipt += ESCPOSFormatter.format_text("KUNDE:", TextStyle.BOLD) + ESCPOSFormatter.LF
            if customer_name:
                receipt += f"{customer_name}" + ESCPOSFormatter.LF
            if customer_phone:
                receipt += f"Tel: {customer_phone}" + ESCPOSFormatter.LF
            if customer_email:
                receipt += f"Email: {customer_email}" + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.LF

        # Service details (pickup address or delivery address)
        if service_type == "pickup":
            pickup_address = self._extract_pickup_address(order)
            if pickup_address:
                receipt += ESCPOSFormatter.format_text("ABHOLUNG:", TextStyle.BOLD) + ESCPOSFormatter.LF
                receipt += pickup_address + ESCPOSFormatter.LF
        else:
            delivery_address = self._extract_delivery_address(order)
            if delivery_address:
                receipt += ESCPOSFormatter.format_text("LIEFERADRESSE:", TextStyle.BOLD) + ESCPOSFormatter.LF
                for line in delivery_address:
                    receipt += line + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Detailed item list with prices
        receipt += ESCPOSFormatter.format_text("BESTELLUNG:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Table header
        receipt += ESCPOSFormatter.create_table_row(
            ["Artikel", "Anz", "CHF"],
            [16, 8, 8]
        ) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Items with descriptions
        subtotal = 0.0
        for item in order.items:
            # Get actual prices from raw data
            item_price = self._get_item_price(item, order.raw_data)
            item_total = item_price * item.quantity
            subtotal += item_total

            # Main item line
            name = item.name[:16] if len(item.name) > 16 else item.name
            qty = f"{item.quantity}x"
            price = f"{item_total:.2f}"

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
                receipt += f"  (à CHF {item_price:.2f})" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF

        # Totals calculation
        total_amount = self._get_total_amount(order)

        # Swiss tax handling (most food is 0% VAT)
        tax_info = self._get_swiss_tax_info(order)

        receipt += ESCPOSFormatter.create_two_column_line(
            "Zwischensumme:",
            f"CHF {subtotal:.2f}"
        ) + ESCPOSFormatter.LF

        if tax_info['tax_amount'] > 0:
            receipt += ESCPOSFormatter.create_two_column_line(
                f"MwSt ({tax_info['tax_rate']:.1f}%):",
                f"CHF {tax_info['tax_amount']:.2f}"
            ) + ESCPOSFormatter.LF

        # Final total
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text(
            ESCPOSFormatter.create_two_column_line("GESAMT:", f"CHF {total_amount:.2f}"),
            TextStyle.BOLD
        ) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF

        # Payment information
        payment_status = self._determine_payment_status(order)
        receipt += f"Zahlungsart: {payment_status}" + ESCPOSFormatter.LF

        # Payment status details
        payment_status_raw = order.raw_data.get('paymentStatus', '').upper() if order.raw_data else ''
        if payment_status_raw == 'NOT_PAID':
            receipt += "Status: Offen (Bar bei Abholung)" + ESCPOSFormatter.LF
        else:
            receipt += "Status: Bezahlt" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF

        # Swiss legal footer
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("Vielen Dank für Ihren Besuch!", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF

        # Business information
        receipt += ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("Steuerliche Angaben", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF

        # Swiss business details
        receipt += "UID: CHE-XXX.XXX.XXX MWST" + ESCPOSFormatter.LF
        if tax_info['tax_amount'] == 0:
            receipt += "Lebensmittel: 0% MwSt" + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("🙏 Kob Khun Ka! 🙏", TextStyle.BOLD, TextAlignment.CENTER) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text("(Vielen Dank auf Thai)", TextStyle.NORMAL, TextAlignment.CENTER) + ESCPOSFormatter.LF

        receipt += ESCPOSFormatter.LF * 2
        receipt += ESCPOSFormatter.CUT_PARTIAL
        return receipt

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

    def _get_customer_name(self, order: Order) -> Optional[str]:
        """Get customer name from billing or recipient info."""
        if not order.raw_data:
            return None

        # Try billing info first
        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        first_name = billing_info.get('firstName', '')
        last_name = billing_info.get('lastName', '')

        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        # Try recipient info
        recipient_info = order.raw_data.get('recipientInfo', {}).get('contactDetails', {})
        first_name = recipient_info.get('firstName', '')
        last_name = recipient_info.get('lastName', '')

        if first_name or last_name:
            return f"{first_name} {last_name}".strip()

        return None

    def _get_customer_phone(self, order: Order) -> Optional[str]:
        """Get customer phone from billing or recipient info."""
        if not order.raw_data:
            return None

        # Try billing info first
        billing_info = order.raw_data.get('billingInfo', {}).get('contactDetails', {})
        phone = billing_info.get('phone')
        if phone:
            return phone

        # Try recipient info
        recipient_info = order.raw_data.get('recipientInfo', {}).get('contactDetails', {})
        return recipient_info.get('phone')

    def _get_customer_email(self, order: Order) -> Optional[str]:
        """Get customer email from buyer info."""
        if not order.raw_data:
            return None

        buyer_info = order.raw_data.get('buyerInfo', {})
        return buyer_info.get('email')

    def _extract_pickup_address(self, order: Order) -> Optional[str]:
        """Extract pickup address from shipping info."""
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
            elif address.get('city'):
                parts.append(address['city'])

            return '\n'.join(parts) if parts else None

        return None

    def _extract_delivery_address(self, order: Order) -> List[str]:
        """Extract delivery address lines."""
        if not order.delivery:
            return []

        address_lines = []
        if order.delivery.address:
            address_lines.append(order.delivery.address)

        if order.delivery.postal_code and order.delivery.city:
            address_lines.append(f"{order.delivery.postal_code} {order.delivery.city}")
        elif order.delivery.city:
            address_lines.append(order.delivery.city)

        if order.delivery.country:
            address_lines.append(order.delivery.country)

        return address_lines

    def _get_item_price(self, item: OrderItem, raw_data: dict) -> float:
        """Get actual item price from raw data."""
        if not raw_data or 'lineItems' not in raw_data:
            return item.price

        # Find matching line item in raw data
        for line_item in raw_data['lineItems']:
            if line_item.get('id') == item.id:
                # Try various price fields
                price_data = line_item.get('price', {})
                if isinstance(price_data, dict) and 'amount' in price_data:
                    try:
                        return float(price_data['amount'])
                    except:
                        pass

                # Try priceBeforeDiscounts
                price_before = line_item.get('priceBeforeDiscounts', {})
                if isinstance(price_before, dict) and 'amount' in price_before:
                    try:
                        return float(price_before['amount'])
                    except:
                        pass

        return item.price

    def _get_total_amount(self, order: Order) -> float:
        """Get total amount from price summary or order total."""
        if order.raw_data and 'priceSummary' in order.raw_data:
            total = order.raw_data['priceSummary'].get('total', {})
            amount = total.get('amount')
            if amount:
                try:
                    return float(amount)
                except:
                    pass

        return order.total_amount

    def _get_swiss_tax_info(self, order: Order) -> dict:
        """Get Swiss tax information from order."""
        if not order.raw_data:
            return {'tax_rate': 0.0, 'tax_amount': 0.0}

        # Check taxInfo or taxSummary
        tax_info = order.raw_data.get('taxInfo', {}) or order.raw_data.get('taxSummary', {})

        if tax_info:
            total_tax = tax_info.get('totalTax', {})
            if isinstance(total_tax, dict) and 'amount' in total_tax:
                try:
                    tax_amount = float(total_tax['amount'])
                    # Calculate rate if we have both tax amount and total
                    if tax_amount > 0:
                        total_amount = self._get_total_amount(order)
                        if total_amount > 0:
                            tax_rate = (tax_amount / (total_amount - tax_amount)) * 100
                            return {'tax_rate': tax_rate, 'tax_amount': tax_amount}
                    return {'tax_rate': 0.0, 'tax_amount': tax_amount}
                except:
                    pass

        return {'tax_rate': 0.0, 'tax_amount': 0.0}

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

    def _determine_payment_status(self, order: Order) -> str:
        """Determine payment status from raw data."""
        if not order.raw_data:
            return "Unbekannt"

        payment_status = order.raw_data.get('paymentStatus', '').upper()
        if payment_status == 'NOT_PAID':
            return "Bar bei Abholung/Lieferung"
        elif payment_status in ['PAID', 'FULLY_PAID']:
            return "Online bezahlt"
        else:
            return f"Status: {payment_status}"


# Register formatters
ReceiptFormatterFactory.register_formatter(ReceiptType.KITCHEN, KitchenReceiptFormatter)
ReceiptFormatterFactory.register_formatter(ReceiptType.DRIVER, DriverReceiptFormatter)
ReceiptFormatterFactory.register_formatter(ReceiptType.CUSTOMER, CustomerReceiptFormatter)


def format_receipt(order: Order, receipt_type: ReceiptType) -> str:
    """
    Convenience function to format a receipt.
    
    Args:
        order: Order to format
        receipt_type: Type of receipt to generate
        
    Returns:
        Formatted receipt content
    """
    try:
        formatter = ReceiptFormatterFactory.create_formatter(receipt_type)
        return formatter.format_receipt(order)
    except Exception as e:
        logger.error(f"Error formatting {receipt_type.value} receipt: {e}")
        raise
