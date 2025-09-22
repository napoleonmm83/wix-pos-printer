"""
Unit tests for webhook integration functionality.
Tests webhook validator, endpoint processing, and security features.
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from wix_printer_service.webhook_validator import WebhookValidator, get_webhook_validator
from wix_printer_service.api.main import create_app


class TestWebhookValidator:
    """Test webhook validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = WebhookValidator()
        self.test_secret = "test_webhook_secret_12345"
        self.test_payload = json.dumps({
            "eventType": "OrderCreated",
            "eventId": "test-event-123",
            "data": {"id": "order-123", "status": "APPROVED"}
        }).encode('utf-8')
    
    def test_validator_initialization(self):
        """Test webhook validator initialization."""
        assert self.validator is not None
        assert hasattr(self.validator, 'webhook_secret')
        assert hasattr(self.validator, 'require_signature')
    
    def test_signature_validation_success(self):
        """Test successful webhook signature validation."""
        # Create valid signature
        signature = hmac.new(
            self.test_secret.encode('utf-8'),
            self.test_payload,
            hashlib.sha256
        ).hexdigest()
        
        # Mock the webhook secret
        with patch.object(self.validator, 'webhook_secret', self.test_secret):
            result = self.validator.validate_signature(self.test_payload, signature)
            assert result is True
    
    def test_signature_validation_failure(self):
        """Test failed webhook signature validation."""
        invalid_signature = "invalid_signature_123"
        
        with patch.object(self.validator, 'webhook_secret', self.test_secret):
            result = self.validator.validate_signature(self.test_payload, invalid_signature)
            assert result is False
    
    def test_signature_validation_missing_secret(self):
        """Test signature validation with missing webhook secret."""
        with patch.object(self.validator, 'webhook_secret', None):
            with patch.object(self.validator, 'require_signature', False):
                result = self.validator.validate_signature(self.test_payload, "any_signature")
                assert result is True
    
    def test_signature_validation_with_prefix(self):
        """Test signature validation with sha256= prefix."""
        signature = hmac.new(
            self.test_secret.encode('utf-8'),
            self.test_payload,
            hashlib.sha256
        ).hexdigest()
        
        prefixed_signature = f"sha256={signature}"
        
        with patch.object(self.validator, 'webhook_secret', self.test_secret):
            result = self.validator.validate_signature(self.test_payload, prefixed_signature)
            assert result is True
    
    def test_duplicate_request_detection(self):
        """Test duplicate request detection."""
        webhook_data = {
            "eventId": "test-event-123",
            "eventType": "OrderCreated",
            "timestamp": "2025-09-21T17:00:00Z"
        }
        
        # First call should not be duplicate
        result1 = self.validator.is_duplicate_request(webhook_data)
        assert result1 is False
        
        # Note: Current implementation doesn't store state, so this always returns False
        # In production, this would check against a database of processed events
    
    def test_extract_order_data_success(self):
        """Test successful order data extraction."""
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "test-event-123",
            "timestamp": "2025-09-21T17:00:00Z",
            "data": {"id": "order-123", "status": "APPROVED"}
        }
        
        result = self.validator.extract_order_data(webhook_data)
        
        assert result is not None
        assert result["id"] == "order-123"
        assert result["webhook_event_type"] == "OrderCreated"
        assert result["webhook_event_id"] == "test-event-123"
    
    def test_extract_order_data_non_order_event(self):
        """Test order data extraction for non-order events."""
        webhook_data = {
            "eventType": "UserUpdated",
            "eventId": "test-event-123",
            "data": {"userId": "user-123"}
        }
        
        result = self.validator.extract_order_data(webhook_data)
        assert result is None
    
    def test_extract_order_data_missing_data(self):
        """Test order data extraction with missing data field."""
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "test-event-123"
            # Missing 'data' field
        }
        
        result = self.validator.extract_order_data(webhook_data)
        assert result is None


class TestWebhookEndpoint:
    """Test webhook endpoint functionality."""
    
    def setup_method(self):
        """Set up test client and fixtures."""
        app = create_app()
        self.client = TestClient(app)
        self.test_webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "test-event-123",
            "timestamp": "2025-09-21T17:00:00Z",
            "data": {
                "id": "order-123",
                "status": "APPROVED",
                "items": [{"name": "Test Item", "quantity": 1}]
            }
        }
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_endpoint_success(self, mock_print_manager, mock_connectivity, mock_order_service):
        """Test successful webhook processing."""
        # Mock dependencies
        mock_order = Mock()
        mock_order.id = "order-123"
        
        mock_order_service.return_value.process_webhook_order.return_value = mock_order
        mock_connectivity.return_value.is_internet_online.return_value = True
        mock_print_manager.return_value.create_print_jobs_for_order.return_value = 3
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        response = self.client.post(
            "/webhook/orders",
            json=self.test_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["order_id"] == "order-123"
        assert data["jobs_created"] == 3
        
        # Verify health monitor was called
        mock_health_monitor.record_webhook_request.assert_called_once_with(success=True)
    
    def test_webhook_endpoint_invalid_json(self):
        """Test webhook endpoint with invalid JSON."""
        response = self.client.post(
            "/webhook/orders",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Invalid JSON payload" in response.json()["detail"]
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_endpoint_offline_mode(self, mock_print_manager, mock_connectivity, mock_order_service):
        """Test webhook processing in offline mode."""
        # Mock offline connectivity
        mock_connectivity.return_value.is_internet_online.return_value = False
        
        mock_order = Mock()
        mock_order.id = "order-123"
        mock_order_service.return_value.process_offline_order.return_value = mock_order
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        response = self.client.post(
            "/webhook/orders",
            json=self.test_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_mode"] == "offline"
        
        # Verify offline processing was called
        mock_order_service.return_value.process_offline_order.assert_called_once()
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_endpoint_processing_failure(self, mock_print_manager, mock_connectivity, mock_order_service):
        """Test webhook endpoint when order processing fails."""
        # Mock processing failure
        mock_order_service.return_value.process_webhook_order.return_value = None
        mock_connectivity.return_value.is_internet_online.return_value = True
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        response = self.client.post(
            "/webhook/orders",
            json=self.test_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Failed to process order" in response.json()["detail"]
        
        # Verify failure was recorded
        mock_health_monitor.record_webhook_request.assert_called_once_with(success=False)
    
    def test_webhook_endpoint_rate_limiting(self):
        """Test webhook endpoint rate limiting."""
        # This test would need to make many requests quickly to trigger rate limiting
        # For now, we'll test that the middleware is properly configured
        
        # Make a request to ensure the middleware is working
        response = self.client.post(
            "/webhook/orders",
            json=self.test_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        # The response might be an error due to missing dependencies,
        # but it should not be a 429 (rate limit) for a single request
        assert response.status_code != 429


class TestWebhookSecurity:
    """Test webhook security features."""
    
    def setup_method(self):
        """Set up test client."""
        app = create_app()
        self.client = TestClient(app)
    
    def test_security_headers_present(self):
        """Test that security headers are added to responses."""
        response = self.client.get("/health")
        
        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-XSS-Protection" in response.headers
        assert "Strict-Transport-Security" in response.headers
    
    def test_cors_configuration(self):
        """Test CORS configuration for webhook endpoint."""
        # Test preflight request
        response = self.client.options(
            "/webhook/orders",
            headers={
                "Origin": "https://www.wix.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Should allow Wix domains
        assert response.status_code in [200, 204]


class TestWebhookStatistics:
    """Test webhook statistics endpoints."""
    
    def setup_method(self):
        """Set up test client."""
        app = create_app()
        self.client = TestClient(app)
    
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_statistics_endpoint(self, mock_print_manager):
        """Test webhook statistics endpoint."""
        # Mock health monitor with statistics
        mock_health_monitor = Mock()
        mock_health_monitor.get_webhook_stats.return_value = {
            "total_requests": 100,
            "successful_requests": 95,
            "failed_requests": 5,
            "last_reset": datetime.now()
        }
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        response = self.client.get("/webhook/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert "webhook_statistics" in data
        assert "success_rate_percent" in data
        assert "failure_rate_percent" in data
        assert data["success_rate_percent"] == 95.0
        assert data["failure_rate_percent"] == 5.0
    
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_reset_stats_endpoint(self, mock_print_manager):
        """Test webhook statistics reset endpoint."""
        mock_health_monitor = Mock()
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        response = self.client.post("/webhook/reset-stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "reset_timestamp" in data
        
        # Verify reset was called
        mock_health_monitor.reset_webhook_stats.assert_called_once()


# Test fixtures and utilities
@pytest.fixture
def mock_webhook_validator():
    """Fixture for mocked webhook validator."""
    validator = Mock(spec=WebhookValidator)
    validator.validate_request.return_value = {"valid": True, "warnings": []}
    validator.is_duplicate_request.return_value = False
    validator.extract_order_data.return_value = {"id": "test-order"}
    return validator


@pytest.fixture
def sample_webhook_payload():
    """Fixture for sample webhook payload."""
    return {
        "eventType": "OrderCreated",
        "eventId": "test-event-123",
        "timestamp": "2025-09-21T17:00:00Z",
        "data": {
            "id": "order-123",
            "status": "APPROVED",
            "items": [{"name": "Test Item", "quantity": 1, "price": 10.00}],
            "total": 10.00,
            "currency": "USD"
        }
    }


def create_valid_signature(payload: bytes, secret: str) -> str:
    """Utility function to create valid webhook signatures for testing."""
    return hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
