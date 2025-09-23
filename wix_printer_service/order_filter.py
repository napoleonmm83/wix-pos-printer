"""
Smart Order Filtering System for Wix eCommerce API.
Provides intelligent filtering based on order status, fulfillment status, and business logic.
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class WixOrderStatus(Enum):
    """
    Wix eCommerce Order Status values based on official API documentation.
    These represent the overall order lifecycle status.
    """
    INITIALIZED = "INITIALIZED"  # Order created but payment not completed
    APPROVED = "APPROVED"        # Order approved and ready for processing
    CANCELED = "CANCELED"        # Order has been canceled
    PENDING = "PENDING"          # Order pending approval/processing
    REFUNDED = "REFUNDED"        # Order has been refunded


class WixFulfillmentStatus(Enum):
    """
    Wix eCommerce Fulfillment Status values based on official API documentation.
    These represent the delivery/fulfillment state of the order.

    ⚠️  IMPORTANT: Based on official Wix API documentation, only these 3 statuses exist:
    - NOT_FULFILLED: Order not yet fulfilled
    - FULFILLED: Order completely fulfilled
    - CANCELED: Fulfillment canceled

    Note: PARTIALLY_FULFILLED is NOT supported by Wix API
    """
    NOT_FULFILLED = "NOT_FULFILLED"     # Order not yet fulfilled
    FULFILLED = "FULFILLED"             # Order completely fulfilled
    CANCELED = "CANCELED"               # Fulfillment canceled


class WixPaymentStatus(Enum):
    """
    Wix eCommerce Payment Status values based on official API documentation.
    These represent the payment state of the order.
    """
    PENDING = "PENDING"          # Payment pending
    PAID = "PAID"                # Payment completed
    PARTIALLY_PAID = "PARTIALLY_PAID"  # Partial payment received
    NOT_PAID = "NOT_PAID"        # No payment received
    REFUNDED = "REFUNDED"        # Payment refunded
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"  # Partial refund issued


@dataclass
class OrderFilterCriteria:
    """
    Comprehensive filter criteria for Wix orders.
    """
    # Status filters
    order_statuses: Optional[List[WixOrderStatus]] = None
    fulfillment_statuses: Optional[List[WixFulfillmentStatus]] = None
    payment_statuses: Optional[List[WixPaymentStatus]] = None

    # Date filters
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None

    # Business logic filters
    exclude_archived: bool = True
    exclude_test_orders: bool = True
    minimum_order_value: Optional[float] = None

    # Channel filters
    channel_types: Optional[List[str]] = None  # e.g., ['WEB', 'MOBILE']

    # Custom filters
    has_tracking_number: Optional[bool] = None
    requires_shipping: Optional[bool] = None


class SmartOrderFilter:
    """
    Intelligent order filtering system that combines API-level filters
    with client-side business logic for optimal performance.
    """

    def __init__(self):
        """Initialize the smart filter system."""
        self.logger = logging.getLogger(__name__)

    def build_api_filter(self, criteria: OrderFilterCriteria) -> Dict[str, Any]:
        """
        Build the filter object for Wix API requests.
        This optimizes performance by filtering at the API level where possible.

        Args:
            criteria: Filter criteria to apply

        Returns:
            Dict representing the API filter object
        """
        api_filter = {}

        # Always exclude INITIALIZED orders (standard practice)
        if not criteria.order_statuses or WixOrderStatus.INITIALIZED not in criteria.order_statuses:
            api_filter["status"] = {"$ne": "INITIALIZED"}

        # Order status filter
        if criteria.order_statuses:
            status_values = [status.value for status in criteria.order_statuses]
            if len(status_values) == 1:
                api_filter["status"] = {"$eq": status_values[0]}
            else:
                api_filter["status"] = {"$in": status_values}

        # Payment status filter
        if criteria.payment_statuses:
            payment_values = [status.value for status in criteria.payment_statuses]
            if len(payment_values) == 1:
                api_filter["paymentStatus"] = {"$eq": payment_values[0]}
            else:
                api_filter["paymentStatus"] = {"$in": payment_values}

        # Fulfillment status filter
        if criteria.fulfillment_statuses:
            fulfillment_values = [status.value for status in criteria.fulfillment_statuses]
            if len(fulfillment_values) == 1:
                api_filter["fulfillmentStatus"] = {"$eq": fulfillment_values[0]}
            else:
                api_filter["fulfillmentStatus"] = {"$in": fulfillment_values}

        # Date filters - try API level first, fallback to client-side
        if criteria.created_after or criteria.created_before:
            date_filter = {}
            if criteria.created_after:
                date_filter["$gte"] = criteria.created_after.isoformat() + "Z"
            if criteria.created_before:
                date_filter["$lte"] = criteria.created_before.isoformat() + "Z"
            api_filter["createdDate"] = date_filter

        # Archived filter
        if criteria.exclude_archived:
            api_filter["archived"] = {"$eq": False}

        # Channel filter
        if criteria.channel_types:
            if len(criteria.channel_types) == 1:
                api_filter["channelInfo.type"] = {"$eq": criteria.channel_types[0]}
            else:
                api_filter["channelInfo.type"] = {"$in": criteria.channel_types}

        self.logger.info(f"Built API filter: {api_filter}")
        return api_filter

    def apply_client_side_filters(self, orders: List[Dict[str, Any]],
                                  criteria: OrderFilterCriteria) -> List[Dict[str, Any]]:
        """
        Apply additional client-side filters that cannot be done at API level.

        Args:
            orders: List of orders from API
            criteria: Filter criteria to apply

        Returns:
            Filtered list of orders
        """
        filtered_orders = []

        for order in orders:
            if self._passes_client_filters(order, criteria):
                filtered_orders.append(order)

        self.logger.info(f"Client-side filtering: {len(orders)} -> {len(filtered_orders)} orders")
        return filtered_orders

    def _passes_client_filters(self, order: Dict[str, Any], criteria: OrderFilterCriteria) -> bool:
        """
        Check if an order passes client-side filter criteria.

        Args:
            order: Order object from API
            criteria: Filter criteria

        Returns:
            True if order passes all filters
        """
        # Minimum order value filter
        if criteria.minimum_order_value is not None:
            try:
                # Support both new priceSummary.total.amount and legacy totals.total.amount
                order_total = 0.0
                price_summary = order.get("priceSummary", {})
                if price_summary and "total" in price_summary:
                    order_total = float(price_summary.get("total", {}).get("amount", 0) or 0)
                else:
                    # Fallback to legacy totals structure
                    order_total = float(order.get("totals", {}).get("total", {}).get("amount", 0) or 0)

                if order_total < criteria.minimum_order_value:
                    return False
            except (ValueError, TypeError):
                self.logger.warning(f"Could not parse order total for order {order.get('id')}")

        # Test order detection (basic heuristics)
        if criteria.exclude_test_orders:
            if self._is_test_order(order):
                return False

        # Tracking number filter
        if criteria.has_tracking_number is not None:
            has_tracking = self._order_has_tracking_number(order)
            if criteria.has_tracking_number != has_tracking:
                return False

        # Shipping requirement filter
        if criteria.requires_shipping is not None:
            requires_shipping = self._order_requires_shipping(order)
            if criteria.requires_shipping != requires_shipping:
                return False

        # Updated date filter (API might not support this reliably)
        if criteria.updated_after or criteria.updated_before:
            try:
                updated_date = datetime.fromisoformat(
                    order.get("updatedDate", "").replace("Z", "+00:00")
                )
                if criteria.updated_after and updated_date < criteria.updated_after:
                    return False
                if criteria.updated_before and updated_date > criteria.updated_before:
                    return False
            except (ValueError, TypeError):
                self.logger.warning(f"Could not parse updatedDate for order {order.get('id')}")

        return True

    def _is_test_order(self, order: Dict[str, Any]) -> bool:
        """
        Detect if an order is likely a test order using heuristics.

        Args:
            order: Order object

        Returns:
            True if order appears to be a test order
        """
        # Check for test-like email patterns
        buyer_info = order.get("buyerInfo", {})
        email = buyer_info.get("email", "").lower()

        test_patterns = [
            "test@", "@test.", "example.com", "dummy@", "@dummy.",
            "noreply@", "@noreply.", "donotreply@"
        ]

        for pattern in test_patterns:
            if pattern in email:
                return True

        # Check for test-like names
        first_name = buyer_info.get("firstName", "").lower()
        last_name = buyer_info.get("lastName", "").lower()

        test_names = ["test", "dummy", "example", "sample"]
        if first_name in test_names or last_name in test_names:
            return True

        # Check for very small order amounts (potential test)
        try:
            total_amount = float(order.get("totals", {}).get("total", {}).get("amount", 0))
            if 0 < total_amount < 1.0:  # Orders under $1
                return True
        except (ValueError, TypeError):
            pass

        return False

    def _order_has_tracking_number(self, order: Dict[str, Any]) -> bool:
        """
        Check if order has tracking information.

        Args:
            order: Order object

        Returns:
            True if order has tracking information
        """
        # This would require checking fulfillment data
        # For now, return False as we'd need additional API calls
        return False

    def _order_requires_shipping(self, order: Dict[str, Any]) -> bool:
        """
        Check if order requires shipping (has physical items).

        Args:
            order: Order object

        Returns:
            True if order has shippable items
        """
        line_items = order.get("lineItems", [])
        for item in line_items:
            # Check if item is shippable
            if item.get("shippable", True):  # Default to True if not specified
                return True

        return False


class ItemCategory(Enum):
    """
    Item categories for kitchen filtering.
    """
    FOOD = "food"           # Warme/kalte Speisen für Küche
    BEVERAGES = "beverages" # Getränke für Bar
    DESSERTS = "desserts"   # Desserts für Dessert-Station
    SIDES = "sides"         # Beilagen
    UNKNOWN = "unknown"     # Unbekannte Kategorie


class RestaurantOrderFilter(SmartOrderFilter):
    """
    Specialized filter for restaurant orders with POS-specific logic.
    """

    def categorize_line_item(self, line_item: Dict[str, Any]) -> ItemCategory:
        """
        Categorize a line item based on its properties.

        Args:
            line_item: Order line item from Wix API

        Returns:
            ItemCategory for the item
        """
        # Get item name and description (support both legacy 'name' and new 'productName.original')
        name = ""
        if "productName" in line_item and isinstance(line_item["productName"], dict):
            name = line_item["productName"].get("original", "").lower()
        else:
            name = line_item.get("name", "").lower()

        description = line_item.get("description", "").lower()

        # Category detection keywords
        food_keywords = [
            "pizza", "pasta", "burger", "sandwich", "salat", "suppe", "soup",
            "schnitzel", "steak", "fisch", "chicken", "hähnchen", "fleisch",
            "vegetarian", "vegan", "warm", "gekocht", "gebraten", "gegrillt",
            "som tam", "somtam", "thai", "curry", "noodles", "reis", "rice",
            "gemüse", "vegetables", "salad"
        ]

        beverage_keywords = [
            "wasser", "water", "saft", "juice", "cola", "limo", "bier", "beer",
            "wein", "wine", "kaffee", "coffee", "tee", "tea", "smoothie",
            "cocktail", "drink", "getränk", "beverage", "valser", "evian",
            "mineralwasser", "sprudel", "prickelnd", "sparkling", "still"
        ]

        dessert_keywords = [
            "kuchen", "cake", "eis", "ice", "cream", "dessert", "nachspeise",
            "süß", "sweet", "schokolade", "chocolate", "torte"
        ]

        sides_keywords = [
            "pommes", "fries", "brot", "bread", "beilage", "side", "sauce",
            "dressing", "extra"
        ]

        # Check categories
        text_to_check = f"{name} {description}"

        if any(keyword in text_to_check for keyword in food_keywords):
            return ItemCategory.FOOD
        elif any(keyword in text_to_check for keyword in beverage_keywords):
            return ItemCategory.BEVERAGES
        elif any(keyword in text_to_check for keyword in dessert_keywords):
            return ItemCategory.DESSERTS
        elif any(keyword in text_to_check for keyword in sides_keywords):
            return ItemCategory.SIDES

        return ItemCategory.UNKNOWN

    def filter_orders_by_item_category(self, orders: List[Dict[str, Any]],
                                     required_categories: List[ItemCategory]) -> List[Dict[str, Any]]:
        """
        Filter orders that contain items from specified categories.

        Args:
            orders: List of orders
            required_categories: Categories that must be present

        Returns:
            Filtered orders containing items from required categories
        """
        filtered_orders = []

        for order in orders:
            line_items = order.get("lineItems", [])
            order_categories = set()

            # Categorize all items in the order
            for item in line_items:
                category = self.categorize_line_item(item)
                order_categories.add(category)

            # Check if order contains required categories
            if any(cat in order_categories for cat in required_categories):
                # Add category information to order for receipt generation
                order["_detected_categories"] = list(order_categories)
                filtered_orders.append(order)

        return filtered_orders

    def get_kitchen_orders_filter(self, hours_back: int = 2) -> OrderFilterCriteria:
        """
        Get filter criteria for kitchen orders (food items only).
        Includes unpaid orders for restaurant workflow (payment after preparation).

        Args:
            hours_back: How many hours back to search

        Returns:
            Filter criteria for kitchen orders
        """
        return OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID, WixPaymentStatus.NOT_PAID],
            fulfillment_statuses=[WixFulfillmentStatus.NOT_FULFILLED],
            exclude_archived=True,
            exclude_test_orders=True,
            minimum_order_value=0.01,
            created_after=datetime.now() - timedelta(hours=hours_back)
        )

    def get_bar_orders_filter(self, hours_back: int = 2) -> OrderFilterCriteria:
        """
        Get filter criteria for bar orders (beverages only).
        Includes unpaid orders for restaurant workflow (payment on delivery/cash).

        Args:
            hours_back: How many hours back to search

        Returns:
            Filter criteria for bar orders
        """
        return OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID, WixPaymentStatus.NOT_PAID],
            fulfillment_statuses=[WixFulfillmentStatus.NOT_FULFILLED],
            exclude_archived=True,
            exclude_test_orders=True,
            minimum_order_value=0.01,
            created_after=datetime.now() - timedelta(hours=hours_back)
        )

    def get_recent_unfulfilled_orders_filter(self, hours_back: int = 6) -> OrderFilterCriteria:
        """
        Get filter criteria for recent unfulfilled orders for regular API polling.
        Includes unpaid orders for restaurant workflow (payment after preparation/on delivery).

        Args:
            hours_back: How many hours back to search

        Returns:
            Filter criteria for recent unfulfilled orders
        """
        return OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID, WixPaymentStatus.NOT_PAID],
            fulfillment_statuses=[WixFulfillmentStatus.NOT_FULFILLED],
            exclude_archived=True,
            exclude_test_orders=True,
            minimum_order_value=0.01,
            created_after=datetime.now() - timedelta(hours=hours_back),
            updated_after=datetime.now() - timedelta(hours=hours_back)  # Also check recently updated orders
        )

    def get_printable_orders_filter(self) -> OrderFilterCriteria:
        return OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED, WixOrderStatus.PENDING],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID, WixPaymentStatus.NOT_PAID],
            fulfillment_statuses=[WixFulfillmentStatus.NOT_FULFILLED],
            exclude_archived=True,
            exclude_test_orders=True,
            minimum_order_value=0.01,  # Exclude zero-value orders
            created_after=datetime.now() - timedelta(hours=24)  # Only recent orders
        )

    def get_pending_fulfillment_filter(self) -> OrderFilterCriteria:
        """
        Get filter criteria for orders pending fulfillment.

        Returns:
            Filter criteria for pending fulfillment orders
        """
        return OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID, WixPaymentStatus.NOT_PAID],
            fulfillment_statuses=[WixFulfillmentStatus.NOT_FULFILLED],
            exclude_archived=True,
            exclude_test_orders=True
        )

    def get_completed_orders_filter(self, days_back: int = 7) -> OrderFilterCriteria:
        """
        Get filter criteria for completed orders.

        Args:
            days_back: Number of days to look back

        Returns:
            Filter criteria for completed orders
        """
        return OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            fulfillment_statuses=[WixFulfillmentStatus.FULFILLED],
            payment_statuses=[WixPaymentStatus.PAID],
            exclude_archived=True,
            created_after=datetime.now() - timedelta(days=days_back)
        )


# Factory function for easy access
def create_restaurant_filter() -> RestaurantOrderFilter:
    """
    Create a restaurant-specific order filter.

    Returns:
        Configured restaurant order filter
    """
    return RestaurantOrderFilter()


# Predefined filter configurations
COMMON_FILTERS = {
    "printable_orders": lambda: create_restaurant_filter().get_printable_orders_filter(),
    "pending_fulfillment": lambda: create_restaurant_filter().get_pending_fulfillment_filter(),
    "completed_orders": lambda: create_restaurant_filter().get_completed_orders_filter(),
    "kitchen_orders": lambda: create_restaurant_filter().get_kitchen_orders_filter(),
    "bar_orders": lambda: create_restaurant_filter().get_bar_orders_filter(),
    "recent_unfulfilled": lambda: create_restaurant_filter().get_recent_unfulfilled_orders_filter(),
    "recent_paid_orders": lambda: OrderFilterCriteria(
        order_statuses=[WixOrderStatus.APPROVED],
        payment_statuses=[WixPaymentStatus.PAID],
        created_after=datetime.now() - timedelta(hours=6),
        exclude_archived=True,
        exclude_test_orders=True
    ),
    "all_active_orders": lambda: OrderFilterCriteria(
        order_statuses=[WixOrderStatus.APPROVED, WixOrderStatus.PENDING],
        exclude_archived=True,
        exclude_test_orders=True
    )
}