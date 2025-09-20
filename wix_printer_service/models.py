"""
Data models for the Wix Printer Service.
Defines Order and PrintJob models for structured data handling.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import json


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PrintJobStatus(Enum):
    """Print job status enumeration."""
    PENDING = "pending"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrderItem:
    """Represents an item within an order."""
    id: str
    name: str
    quantity: int
    price: float
    sku: Optional[str] = None
    variant: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class CustomerInfo:
    """Customer information for an order."""
    id: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class DeliveryInfo:
    """Delivery information for an order."""
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    delivery_instructions: Optional[str] = None


@dataclass
class Order:
    """
    Represents a Wix order with all relevant information.
    Maps to the orders table in SQLite database.
    """
    id: str
    wix_order_id: str
    status: OrderStatus
    items: List[OrderItem]
    customer: CustomerInfo
    delivery: DeliveryInfo
    total_amount: float
    currency: str = "EUR"
    order_date: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    raw_data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_wix_data(cls, wix_data: Dict[str, Any]) -> 'Order':
        """
        Create an Order instance from Wix API data.
        
        Args:
            wix_data: Raw order data from Wix API
            
        Returns:
            Order instance
        """
        # Extract order items
        items = []
        for item_data in wix_data.get('lineItems', []):
            item = OrderItem(
                id=item_data.get('id', ''),
                name=item_data.get('name', ''),
                quantity=item_data.get('quantity', 1),
                price=float(item_data.get('price', {}).get('amount', 0)),
                sku=item_data.get('sku'),
                variant=item_data.get('variant'),
                notes=item_data.get('notes')
            )
            items.append(item)
        
        # Extract customer information
        buyer_info = wix_data.get('buyerInfo', {})
        customer = CustomerInfo(
            id=buyer_info.get('id'),
            email=buyer_info.get('email'),
            first_name=buyer_info.get('firstName'),
            last_name=buyer_info.get('lastName'),
            phone=buyer_info.get('phone')
        )
        
        # Extract delivery information
        shipping_info = wix_data.get('shippingInfo', {})
        delivery_address = shipping_info.get('deliveryAddress', {})
        delivery = DeliveryInfo(
            address=delivery_address.get('addressLine1'),
            city=delivery_address.get('city'),
            postal_code=delivery_address.get('postalCode'),
            country=delivery_address.get('country'),
            delivery_instructions=shipping_info.get('deliveryInstructions')
        )
        
        # Parse order date
        order_date = datetime.now()
        if 'dateCreated' in wix_data:
            try:
                order_date = datetime.fromisoformat(wix_data['dateCreated'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        return cls(
            id=wix_data.get('id', ''),
            wix_order_id=wix_data.get('id', ''),
            status=OrderStatus(wix_data.get('status', 'pending').lower()),
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=float(wix_data.get('totals', {}).get('total', {}).get('amount', 0)),
            currency=wix_data.get('totals', {}).get('total', {}).get('currency', 'EUR'),
            order_date=order_date,
            raw_data=wix_data
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Order to dictionary for database storage."""
        return {
            'id': self.id,
            'wix_order_id': self.wix_order_id,
            'status': self.status.value,
            'items_json': json.dumps([{
                'id': item.id,
                'name': item.name,
                'quantity': item.quantity,
                'price': item.price,
                'sku': item.sku,
                'variant': item.variant,
                'notes': item.notes
            } for item in self.items]),
            'customer_json': json.dumps({
                'id': self.customer.id,
                'email': self.customer.email,
                'first_name': self.customer.first_name,
                'last_name': self.customer.last_name,
                'phone': self.customer.phone
            }),
            'delivery_json': json.dumps({
                'address': self.delivery.address,
                'city': self.delivery.city,
                'postal_code': self.delivery.postal_code,
                'country': self.delivery.country,
                'delivery_instructions': self.delivery.delivery_instructions
            }),
            'total_amount': self.total_amount,
            'currency': self.currency,
            'order_date': self.order_date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'raw_data_json': json.dumps(self.raw_data) if self.raw_data else None
        }


@dataclass
class PrintJob:
    """
    Represents a print job in the queue.
    Maps to the print_jobs table in SQLite database.
    """
    id: Optional[str] = None
    order_id: str = ""
    job_type: str = "receipt"  # receipt, kitchen, delivery
    status: PrintJobStatus = PrintJobStatus.PENDING
    content: str = ""
    printer_name: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    printed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert PrintJob to dictionary for database storage."""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'job_type': self.job_type,
            'status': self.status.value,
            'content': self.content,
            'printer_name': self.printer_name,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'printed_at': self.printed_at.isoformat() if self.printed_at else None,
            'error_message': self.error_message
        }
