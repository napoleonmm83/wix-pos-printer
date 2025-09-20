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
        """Format a kitchen receipt."""
        receipt = self._format_header("KÜCHE")
        
        # Order info
        receipt += self._format_order_info(order)
        
        # Items with preparation focus
        receipt += ESCPOSFormatter.format_text("ARTIKEL:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        
        for item in order.items:
            # Item name and quantity (bold for visibility)
            receipt += ESCPOSFormatter.format_text(
                f"{item.quantity}x {item.name}", 
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF
            
            # Variant information
            if item.variant:
                receipt += f"   Variante: {item.variant}" + ESCPOSFormatter.LF
            
            # Special requests (highlighted)
            if item.notes:
                receipt += ESCPOSFormatter.format_text(
                    f"   !!! {item.notes} !!!", 
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF
            
            # Check for allergy keywords
            if item.notes and self._contains_allergy_keywords(item.notes):
                receipt += ESCPOSFormatter.format_text(
                    "   *** ALLERGIE WARNUNG ***", 
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF
            
            receipt += ESCPOSFormatter.LF
        
        # Preparation time estimate
        prep_time = self._estimate_prep_time(order)
        if prep_time:
            receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.format_text(
                f"Geschätzte Zubereitungszeit: {prep_time} Min", 
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF
        
        # Order status
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        receipt += f"Status: {order.status.value.upper()}" + ESCPOSFormatter.LF
        
        receipt += self._format_footer()
        return receipt
    
    def _contains_allergy_keywords(self, text: str) -> bool:
        """Check if text contains allergy-related keywords."""
        allergy_keywords = [
            'allergie', 'allergisch', 'gluten', 'laktose', 'nuss', 'nüsse',
            'erdnuss', 'soja', 'ei', 'fisch', 'meeresfrüchte', 'sellerie'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in allergy_keywords)
    
    def _estimate_prep_time(self, order: Order) -> Optional[int]:
        """Estimate preparation time based on items."""
        # Simple estimation: 5 minutes base + 2 minutes per item
        if not order.items:
            return None
        
        base_time = 5
        item_time = len(order.items) * 2
        total_items = sum(item.quantity for item in order.items)
        complexity_time = total_items * 1
        
        return base_time + item_time + complexity_time


class DriverReceiptFormatter(BaseReceiptFormatter):
    """Formatter for driver receipts focused on delivery information."""
    
    def format_receipt(self, order: Order) -> str:
        """Format a driver receipt."""
        receipt = self._format_header("LIEFERUNG")
        
        # Order info
        receipt += self._format_order_info(order)
        
        # Delivery address (prominent)
        if order.delivery:
            receipt += ESCPOSFormatter.format_text("LIEFERADRESSE:", TextStyle.BOLD) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
            
            if order.delivery.address:
                receipt += ESCPOSFormatter.format_text(
                    order.delivery.address, 
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF
            
            if order.delivery.city:
                city_line = order.delivery.city
                if order.delivery.postal_code:
                    city_line = f"{order.delivery.postal_code} {city_line}"
                receipt += ESCPOSFormatter.format_text(
                    city_line, 
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF
            
            if order.delivery.country:
                receipt += order.delivery.country + ESCPOSFormatter.LF
            
            receipt += ESCPOSFormatter.LF
        
        # Customer contact
        if order.customer:
            receipt += ESCPOSFormatter.format_text("KONTAKT:", TextStyle.BOLD) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
            
            if order.customer.phone:
                receipt += ESCPOSFormatter.format_text(
                    f"Tel: {order.customer.phone}", 
                    TextStyle.BOLD
                ) + ESCPOSFormatter.LF
            
            if order.customer.email:
                receipt += f"Email: {order.customer.email}" + ESCPOSFormatter.LF
            
            receipt += ESCPOSFormatter.LF
        
        # Delivery instructions
        if order.delivery and order.delivery.delivery_instructions:
            receipt += ESCPOSFormatter.format_text("HINWEISE:", TextStyle.BOLD) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.format_text(
                order.delivery.delivery_instructions, 
                TextStyle.BOLD
            ) + ESCPOSFormatter.LF
            receipt += ESCPOSFormatter.LF
        
        # Order summary (compact)
        receipt += ESCPOSFormatter.format_text("BESTELLUNG:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        
        for item in order.items:
            receipt += f"{item.quantity}x {item.name}" + ESCPOSFormatter.LF
        
        # Total amount (use order total, not calculated total with tax)
        receipt += ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_two_column_line(
            "GESAMT:", 
            f"{order.total_amount:.2f}€"
        ) + ESCPOSFormatter.LF
        
        # Payment status
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        receipt += "Zahlung: Online bezahlt" + ESCPOSFormatter.LF
        
        receipt += self._format_footer()
        return receipt


class CustomerReceiptFormatter(BaseReceiptFormatter):
    """Formatter for customer receipts with full billing details."""
    
    def format_receipt(self, order: Order) -> str:
        """Format a customer receipt."""
        receipt = self._format_header("RECHNUNG")
        
        # Order info
        receipt += self._format_order_info(order)
        
        # Detailed item list with prices
        receipt += ESCPOSFormatter.format_text("ARTIKEL:", TextStyle.BOLD) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        
        # Table header
        receipt += ESCPOSFormatter.create_table_row(
            ["Artikel", "Anz", "Preis"], 
            [18, 6, 8]
        ) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        
        # Items
        for item in order.items:
            name = item.name[:18] if len(item.name) > 18 else item.name
            qty = f"{item.quantity}x"
            price = f"{item.price * item.quantity:.2f}€"
            
            receipt += ESCPOSFormatter.create_table_row(
                [name, qty, price], 
                [18, 6, 8]
            ) + ESCPOSFormatter.LF
            
            # Variant as sub-item
            if item.variant:
                receipt += f"  ({item.variant})" + ESCPOSFormatter.LF
        
        # Totals
        totals = self._calculate_totals(order)
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        
        receipt += ESCPOSFormatter.create_two_column_line(
            "Zwischensumme:", 
            f"{totals['subtotal']:.2f}€"
        ) + ESCPOSFormatter.LF
        
        receipt += ESCPOSFormatter.create_two_column_line(
            f"MwSt ({totals['tax_rate']*100:.0f}%):", 
            f"{totals['tax_amount']:.2f}€"
        ) + ESCPOSFormatter.LF
        
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text(
            ESCPOSFormatter.create_two_column_line("GESAMT:", f"{totals['total']:.2f}€"),
            TextStyle.BOLD
        ) + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("=") + ESCPOSFormatter.LF
        
        # Payment information
        receipt += ESCPOSFormatter.LF
        receipt += "Zahlungsart: Online-Zahlung" + ESCPOSFormatter.LF
        receipt += "Status: Bezahlt" + ESCPOSFormatter.LF
        
        # Legal footer
        receipt += ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.create_separator("-") + ESCPOSFormatter.LF
        receipt += ESCPOSFormatter.format_text(
            "Steuerliche Angaben", 
            TextStyle.BOLD, 
            TextAlignment.CENTER
        ) + ESCPOSFormatter.LF
        receipt += f"USt-IdNr: {os.getenv('VAT_ID', 'DE123456789')}" + ESCPOSFormatter.LF
        receipt += "Kleinunternehmer gem. §19 UStG" + ESCPOSFormatter.LF
        
        receipt += self._format_footer()
        return receipt


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
