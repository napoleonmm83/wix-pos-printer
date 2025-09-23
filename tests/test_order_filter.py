"""
Test suite for the smart order filtering system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from wix_printer_service.order_filter import (
    SmartOrderFilter,
    RestaurantOrderFilter,
    OrderFilterCriteria,
    WixOrderStatus,
    WixFulfillmentStatus,
    WixPaymentStatus,
    COMMON_FILTERS,
    create_restaurant_filter
)


class TestOrderFilterCriteria:
    """Test OrderFilterCriteria dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        criteria = OrderFilterCriteria()
        assert criteria.order_statuses is None
        assert criteria.fulfillment_statuses is None
        assert criteria.payment_statuses is None
        assert criteria.exclude_archived is True
        assert criteria.exclude_test_orders is True
        assert criteria.minimum_order_value is None

    def test_custom_values(self):
        """Test setting custom values."""
        criteria = OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            payment_statuses=[WixPaymentStatus.PAID],
            minimum_order_value=10.0,
            exclude_archived=False
        )
        assert criteria.order_statuses == [WixOrderStatus.APPROVED]
        assert criteria.payment_statuses == [WixPaymentStatus.PAID]
        assert criteria.minimum_order_value == 10.0
        assert criteria.exclude_archived is False


class TestSmartOrderFilter:
    """Test SmartOrderFilter class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.filter = SmartOrderFilter()

    def test_build_api_filter_basic(self):
        """Test building basic API filter."""
        criteria = OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED],
            exclude_archived=True
        )

        api_filter = self.filter.build_api_filter(criteria)

        assert api_filter["status"]["$eq"] == "APPROVED"
        assert api_filter["archived"]["$eq"] is False

    def test_build_api_filter_multiple_statuses(self):
        """Test building API filter with multiple statuses."""
        criteria = OrderFilterCriteria(
            order_statuses=[WixOrderStatus.APPROVED, WixOrderStatus.PENDING],
            payment_statuses=[WixPaymentStatus.PAID, WixPaymentStatus.PARTIALLY_PAID]
        )

        api_filter = self.filter.build_api_filter(criteria)

        assert api_filter["status"]["$in"] == ["APPROVED", "PENDING"]
        assert api_filter["paymentStatus"]["$in"] == ["PAID", "PARTIALLY_PAID"]

    def test_build_api_filter_date_range(self):
        """Test building API filter with date range."""
        start_date = datetime(2023, 1, 1, 12, 0, 0)
        end_date = datetime(2023, 1, 2, 12, 0, 0)

        criteria = OrderFilterCriteria(
            created_after=start_date,
            created_before=end_date
        )

        api_filter = self.filter.build_api_filter(criteria)

        date_filter = api_filter["createdDate"]
        assert date_filter["$gte"] == "2023-01-01T12:00:00Z"
        assert date_filter["$lte"] == "2023-01-02T12:00:00Z"

    def test_build_api_filter_default_exclude_initialized(self):
        """Test that INITIALIZED orders are excluded by default."""
        criteria = OrderFilterCriteria()

        api_filter = self.filter.build_api_filter(criteria)

        assert api_filter["status"]["$ne"] == "INITIALIZED"

    def test_is_test_order_email_patterns(self):
        """Test test order detection based on email patterns."""
        test_cases = [
            ({"buyerInfo": {"email": "test@example.com"}}, True),
            ({"buyerInfo": {"email": "user@test.com"}}, True),
            ({"buyerInfo": {"email": "noreply@company.com"}}, True),
            ({"buyerInfo": {"email": "john@gmail.com"}}, False),
            ({"buyerInfo": {"email": "customer@business.com"}}, False),
        ]

        for order_data, expected in test_cases:
            result = self.filter._is_test_order(order_data)
            assert result == expected, f"Failed for {order_data}"

    def test_is_test_order_names(self):
        """Test test order detection based on names."""
        test_cases = [
            ({"buyerInfo": {"firstName": "Test", "lastName": "User"}}, True),
            ({"buyerInfo": {"firstName": "John", "lastName": "Dummy"}}, True),
            ({"buyerInfo": {"firstName": "Jane", "lastName": "Smith"}}, False),
        ]

        for order_data, expected in test_cases:
            result = self.filter._is_test_order(order_data)
            assert result == expected, f"Failed for {order_data}"

    def test_is_test_order_small_amounts(self):
        """Test test order detection based on small order amounts."""
        test_cases = [
            ({"totals": {"total": {"amount": "0.01"}}}, True),
            ({"totals": {"total": {"amount": "0.99"}}}, True),
            ({"totals": {"total": {"amount": "1.00"}}}, False),
            ({"totals": {"total": {"amount": "10.50"}}}, False),
        ]

        for order_data, expected in test_cases:
            result = self.filter._is_test_order(order_data)
            assert result == expected, f"Failed for {order_data}"

    def test_order_requires_shipping(self):
        """Test detection of orders requiring shipping."""
        test_cases = [
            ({"lineItems": [{"shippable": True}]}, True),
            ({"lineItems": [{"shippable": False}]}, False),
            ({"lineItems": [{}]}, True),  # Default to True if not specified
            ({"lineItems": []}, False),   # No items = no shipping required
        ]

        for order_data, expected in test_cases:
            result = self.filter._order_requires_shipping(order_data)
            assert result == expected, f"Failed for {order_data}"

    def test_apply_client_side_filters(self):
        """Test client-side filtering application."""
        orders = [
            {
                "id": "order-1",
                "totals": {"total": {"amount": "25.00"}},
                "buyerInfo": {"email": "customer@example.com"},
                "lineItems": [{"shippable": True}]
            },
            {
                "id": "order-2",
                "totals": {"total": {"amount": "0.50"}},  # Too small
                "buyerInfo": {"email": "test@example.com"},  # Test order
                "lineItems": [{"shippable": True}]
            },
            {
                "id": "order-3",
                "totals": {"total": {"amount": "15.00"}},
                "buyerInfo": {"email": "another@customer.com"},
                "lineItems": [{"shippable": False}]
            }
        ]

        criteria = OrderFilterCriteria(
            minimum_order_value=1.0,
            exclude_test_orders=True,
            requires_shipping=True
        )

        filtered = self.filter.apply_client_side_filters(orders, criteria)

        # Should only include order-1 (meets all criteria)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "order-1"


class TestRestaurantOrderFilter:
    """Test RestaurantOrderFilter specialized class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.filter = RestaurantOrderFilter()

    def test_get_printable_orders_filter(self):
        """Test printable orders filter configuration."""
        criteria = self.filter.get_printable_orders_filter()

        assert WixOrderStatus.APPROVED in criteria.order_statuses
        assert WixOrderStatus.PENDING in criteria.order_statuses
        assert WixPaymentStatus.PAID in criteria.payment_statuses
        assert WixFulfillmentStatus.NOT_FULFILLED in criteria.fulfillment_statuses
        assert criteria.exclude_archived is True
        assert criteria.exclude_test_orders is True
        assert criteria.minimum_order_value == 0.01

    def test_get_pending_fulfillment_filter(self):
        """Test pending fulfillment filter configuration."""
        criteria = self.filter.get_pending_fulfillment_filter()

        assert criteria.order_statuses == [WixOrderStatus.APPROVED]
        assert criteria.payment_statuses == [WixPaymentStatus.PAID]
        assert WixFulfillmentStatus.NOT_FULFILLED in criteria.fulfillment_statuses
        assert criteria.exclude_archived is True
        assert criteria.exclude_test_orders is True

    def test_get_completed_orders_filter(self):
        """Test completed orders filter configuration."""
        criteria = self.filter.get_completed_orders_filter(days_back=3)

        assert criteria.order_statuses == [WixOrderStatus.APPROVED]
        assert criteria.payment_statuses == [WixPaymentStatus.PAID]
        assert criteria.fulfillment_statuses == [WixFulfillmentStatus.FULFILLED]
        assert criteria.exclude_archived is True

        # Check date is approximately 3 days ago
        expected_date = datetime.now() - timedelta(days=3)
        assert criteria.created_after is not None
        assert abs((criteria.created_after - expected_date).total_seconds()) < 60


class TestCommonFilters:
    """Test predefined common filters."""

    def test_printable_orders_filter(self):
        """Test printable orders common filter."""
        criteria = COMMON_FILTERS["printable_orders"]()

        assert isinstance(criteria, OrderFilterCriteria)
        assert WixOrderStatus.APPROVED in criteria.order_statuses
        assert criteria.exclude_test_orders is True

    def test_pending_fulfillment_filter(self):
        """Test pending fulfillment common filter."""
        criteria = COMMON_FILTERS["pending_fulfillment"]()

        assert isinstance(criteria, OrderFilterCriteria)
        assert criteria.order_statuses == [WixOrderStatus.APPROVED]
        assert WixFulfillmentStatus.NOT_FULFILLED in criteria.fulfillment_statuses

    def test_recent_paid_orders_filter(self):
        """Test recent paid orders common filter."""
        criteria = COMMON_FILTERS["recent_paid_orders"]()

        assert isinstance(criteria, OrderFilterCriteria)
        assert criteria.order_statuses == [WixOrderStatus.APPROVED]
        assert criteria.payment_statuses == [WixPaymentStatus.PAID]
        assert criteria.created_after is not None

    def test_all_common_filters_available(self):
        """Test that all expected common filters are available."""
        expected_filters = [
            "printable_orders",
            "pending_fulfillment",
            "completed_orders",
            "recent_paid_orders",
            "all_active_orders"
        ]

        for filter_name in expected_filters:
            assert filter_name in COMMON_FILTERS
            criteria = COMMON_FILTERS[filter_name]()
            assert isinstance(criteria, OrderFilterCriteria)


class TestFactoryFunction:
    """Test factory function."""

    def test_create_restaurant_filter(self):
        """Test restaurant filter factory function."""
        filter_instance = create_restaurant_filter()

        assert isinstance(filter_instance, RestaurantOrderFilter)
        assert hasattr(filter_instance, 'get_printable_orders_filter')
        assert hasattr(filter_instance, 'get_pending_fulfillment_filter')


class TestStatusEnums:
    """Test status enum values."""

    def test_wix_order_status_values(self):
        """Test WixOrderStatus enum values."""
        expected_values = ["INITIALIZED", "APPROVED", "CANCELED", "PENDING", "REFUNDED"]
        actual_values = [status.value for status in WixOrderStatus]

        for expected in expected_values:
            assert expected in actual_values

    def test_wix_fulfillment_status_values(self):
        """Test WixFulfillmentStatus enum values."""
        expected_values = ["NOT_FULFILLED", "FULFILLED", "CANCELED"]
        actual_values = [status.value for status in WixFulfillmentStatus]

        for expected in expected_values:
            assert expected in actual_values

    def test_wix_payment_status_values(self):
        """Test WixPaymentStatus enum values."""
        expected_values = ["PENDING", "PAID", "PARTIALLY_PAID", "NOT_PAID", "REFUNDED", "PARTIALLY_REFUNDED"]
        actual_values = [status.value for status in WixPaymentStatus]

        for expected in expected_values:
            assert expected in actual_values


if __name__ == "__main__":
    pytest.main([__file__, "-v"])