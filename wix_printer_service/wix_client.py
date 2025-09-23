"""
Wix API Client for handling authentication and API communication.
Provides secure connection to Wix Orders API with proper error handling.
"""
import os
import logging
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from .order_filter import SmartOrderFilter, RestaurantOrderFilter, OrderFilterCriteria, COMMON_FILTERS

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class WixAPIError(Exception):
    """Custom exception for Wix API related errors."""
    pass


class WixClient:
    """
    Client for communicating with the Wix Orders API.
    Handles authentication, request management, and error handling.
    """
    
    def __init__(self):
        """Initialize the Wix API client with authentication credentials."""
        self.api_key = os.getenv('WIX_API_KEY')
        self.site_id = os.getenv('WIX_SITE_ID')
        self.base_url = os.getenv('WIX_API_BASE_URL', 'https://www.wixapis.com')

        if not self.api_key:
            raise WixAPIError("WIX_API_KEY environment variable is required")
        if not self.site_id:
            raise WixAPIError("WIX_SITE_ID environment variable is required")

        self.session = requests.Session()
        # Wix API Key auth does NOT use the "Bearer" prefix; it expects the raw API key
        self.session.headers.update({
            'Authorization': self.api_key,
            'wix-site-id': self.site_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        # Initialize smart filtering system
        self.smart_filter = RestaurantOrderFilter()

        logger.info("Wix API client initialized successfully")
    
    def test_connection(self) -> bool:
        """
        Test the connection to Wix API.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Test with a small search (recommended for eCommerce Orders API)
            response = self.session.post(
                f'{self.base_url}/ecom/v1/orders/search',
                json={
                    'cursorPaging': {'limit': 1},
                    'filter': { 'status': { '$ne': 'INITIALIZED' } },
                    'sort': [{ 'fieldName': 'createdDate', 'order': 'DESC' }]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Wix API connection test successful")
                return True
            else:
                logger.error(f"Wix API connection test failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Wix API connection test failed with exception: {e}")
            return False
    
    def search_orders(self, limit: int = 50, cursor: Optional[str] = None, filter: Optional[Dict[str, Any]] = None, sort: Optional[list] = None) -> Dict[str, Any]:
        """
        Search orders via eCommerce Orders API.
        Uses POST /wix-ecom/v1/orders/search with filter/sort/cursorPaging.
        """
        try:
            body: Dict[str, Any] = {
                'cursorPaging': {'limit': limit}
            }
            if cursor:
                body['cursorPaging']['cursor'] = cursor
            if filter:
                body['filter'] = filter
            if sort:
                body['sort'] = sort
            else:
                body['sort'] = [{ 'fieldName': 'createdDate', 'order': 'DESC' }]

            response = self.session.post(
                f'{self.base_url}/ecom/v1/orders/search',
                json=body,
                timeout=30
            )
            if response.status_code == 200:
                return response.json() or {}
            logger.error(f"Search orders failed: {response.status_code} - {response.text}")
            raise WixAPIError(f"API request failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching orders: {e}")
            raise WixAPIError(f"Network error: {str(e)}")

    def get_orders_since(self, from_date: Optional[str], status: Optional[str], limit: int = 100, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        Search orders with a start date and optional status filter.
        """
        from datetime import datetime, time

        # Start with a base filter that can be expanded
        filt = { 'status': { '$ne': 'INITIALIZED' } } # Default filter

        if from_date:
            try:
                start_of_day = datetime.fromisoformat(from_date)
                start_of_day = datetime.combine(start_of_day.date(), time.min)
                filt['createdDate'] = { '$gte': start_of_day.isoformat() + "Z" }
            except ValueError:
                logger.warning(f"Invalid from_date format: {from_date}. Should be YYYY-MM-DD.")
        
        if status:
            filt['status'] = { '$eq': status.upper() }

        return self.search_orders(limit=limit, cursor=cursor, filter=filt)

    def search_orders_smart(self, criteria: OrderFilterCriteria, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        Search orders using smart filtering system.

        Args:
            criteria: Filter criteria to apply
            limit: Maximum number of orders to return
            cursor: Pagination cursor

        Returns:
            Filtered orders response
        """
        # Build API-level filter for optimal performance
        api_filter = self.smart_filter.build_api_filter(criteria)

        # Search orders with API filter
        response = self.search_orders(limit=limit, cursor=cursor, filter=api_filter)

        # Apply client-side filters for criteria that cannot be handled by API
        if 'orders' in response:
            filtered_orders = self.smart_filter.apply_client_side_filters(
                response['orders'], criteria
            )
            response['orders'] = filtered_orders

        return response

    def get_printable_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders that should be printed at the POS.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of printable orders
        """
        criteria = self.smart_filter.get_printable_orders_filter()
        response = self.search_orders_smart(criteria, limit=limit)
        return response.get('orders', [])

    def get_pending_fulfillment_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders that are pending fulfillment.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of orders pending fulfillment
        """
        criteria = self.smart_filter.get_pending_fulfillment_filter()
        response = self.search_orders_smart(criteria, limit=limit)
        return response.get('orders', [])

    def get_recent_orders(self, minutes_ago: int = 30, exclude_printed: bool = True) -> List[Dict[str, Any]]:
        """
        Get recent orders for auto-check processing.

        Args:
            minutes_ago: How many minutes back to look
            exclude_printed: Whether to exclude already printed orders

        Returns:
            List of recent orders
        """
        from datetime import datetime, timedelta
        from .order_filter import WixOrderStatus, WixFulfillmentStatus, WixPaymentStatus

        criteria = OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID, WixPaymentStatus.NOT_PAID],
            fulfillment_statuses=[WixFulfillmentStatus.NOT_FULFILLED],
            created_after=datetime.now() - timedelta(minutes=minutes_ago),
            exclude_archived=True,
            exclude_test_orders=True,
            minimum_order_value=0.01
        )

        response = self.search_orders_smart(criteria, limit=100)
        return response.get('orders', [])

    def get_orders_by_status(self, order_status: str = None, fulfillment_status: str = None,
                           payment_status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders filtered by specific status criteria.

        Args:
            order_status: Order status to filter by (APPROVED, PENDING, etc.)
            fulfillment_status: Fulfillment status to filter by (NOT_FULFILLED, FULFILLED, etc.)
            payment_status: Payment status to filter by (PAID, PENDING, etc.)
            limit: Maximum number of orders to return

        Returns:
            List of orders matching the status criteria
        """
        from .order_filter import WixOrderStatus, WixFulfillmentStatus, WixPaymentStatus

        criteria = OrderFilterCriteria(exclude_archived=True, exclude_test_orders=True)

        if order_status:
            try:
                criteria.order_statuses = [WixOrderStatus(order_status.upper())]
            except ValueError:
                logger.warning(f"Invalid order status: {order_status}")

        if fulfillment_status:
            try:
                criteria.fulfillment_statuses = [WixFulfillmentStatus(fulfillment_status.upper())]
            except ValueError:
                logger.warning(f"Invalid fulfillment status: {fulfillment_status}")

        if payment_status:
            try:
                criteria.payment_statuses = [WixPaymentStatus(payment_status.upper())]
            except ValueError:
                logger.warning(f"Invalid payment status: {payment_status}")

        response = self.search_orders_smart(criteria, limit=limit)
        return response.get('orders', [])

    def get_orders_with_common_filter(self, filter_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders using predefined common filter.

        Args:
            filter_name: Name of the common filter (printable_orders, pending_fulfillment, etc.)
            limit: Maximum number of orders to return

        Returns:
            List of filtered orders
        """
        if filter_name not in COMMON_FILTERS:
            raise WixAPIError(f"Unknown filter: {filter_name}. Available filters: {list(COMMON_FILTERS.keys())}")

        criteria = COMMON_FILTERS[filter_name]()
        response = self.search_orders_smart(criteria, limit=limit)
        return response.get('orders', [])

    def get_kitchen_orders(self, hours_back: int = 2, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders containing food items for kitchen printing.

        Args:
            hours_back: How many hours back to search
            limit: Maximum number of orders to return

        Returns:
            List of orders with food items for kitchen
        """
        from .order_filter import ItemCategory

        criteria = self.smart_filter.get_kitchen_orders_filter(hours_back=hours_back)
        response = self.search_orders_smart(criteria, limit=limit)
        orders = response.get('orders', [])

        # Filter orders that contain food items
        kitchen_orders = self.smart_filter.filter_orders_by_item_category(
            orders, [ItemCategory.FOOD, ItemCategory.SIDES]
        )

        return kitchen_orders

    def get_bar_orders(self, hours_back: int = 2, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders containing beverage items for bar printing.

        Args:
            hours_back: How many hours back to search
            limit: Maximum number of orders to return

        Returns:
            List of orders with beverage items for bar
        """
        from .order_filter import ItemCategory

        criteria = self.smart_filter.get_bar_orders_filter(hours_back=hours_back)
        response = self.search_orders_smart(criteria, limit=limit)
        orders = response.get('orders', [])

        # Filter orders that contain beverage items
        bar_orders = self.smart_filter.filter_orders_by_item_category(
            orders, [ItemCategory.BEVERAGES]
        )

        return bar_orders

    def get_orders_for_regular_polling(self, hours_back: int = 6, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get orders for regular API polling - optimized for auto-check functionality.
        This method should be used for the regular background task that fetches orders.

        Args:
            hours_back: How many hours back to search (default: 6 hours)
            limit: Maximum number of orders to return

        Returns:
            List of recent unfulfilled orders that need processing
        """
        criteria = self.smart_filter.get_recent_unfulfilled_orders_filter(hours_back=hours_back)
        response = self.search_orders_smart(criteria, limit=limit)
        orders = response.get('orders', [])

        logger.info(f"Regular polling found {len(orders)} unfulfilled orders from last {hours_back} hours")
        return orders

    def get_orders_by_fulfillment_status(self, fulfillment_status: str, hours_back: int = 24,
                                       limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get orders filtered specifically by fulfillment status and time.

        Args:
            fulfillment_status: Fulfillment status (NOT_FULFILLED, FULFILLED, CANCELED)
            hours_back: How many hours back to search
            limit: Maximum number of orders to return

        Returns:
            List of orders matching the fulfillment status criteria
        """
        from datetime import datetime, timedelta
        from .order_filter import WixFulfillmentStatus

        try:
            fulfillment_enum = WixFulfillmentStatus(fulfillment_status.upper())
        except ValueError:
            logger.warning(f"Invalid fulfillment status: {fulfillment_status}")
            return []

        from .order_filter import WixOrderStatus, WixPaymentStatus

        criteria = OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID],
            fulfillment_statuses=[fulfillment_enum],
            created_after=datetime.now() - timedelta(hours=hours_back),
            exclude_archived=True,
            exclude_test_orders=True,
            minimum_order_value=0.01
        )

        response = self.search_orders_smart(criteria, limit=limit)
        return response.get('orders', [])

    def validate_webhook_signature(self, payload: bytes, signature: str, webhook_secret: str) -> bool:
        """
        Validate webhook signature for security.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers
            webhook_secret: Secret key for webhook validation
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        import hmac
        import hashlib
        
        try:
            # Compute expected signature
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures securely
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if is_valid:
                logger.info("Webhook signature validation successful")
            else:
                logger.warning("Webhook signature validation failed")
                
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            logger.info("Wix API client session closed")
