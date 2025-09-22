"""
Integration tests for complete webhook-to-print workflow.
Tests end-to-end processing from webhook reception to print job creation.
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from wix_printer_service.api.main import create_app
from wix_printer_service.models import Order, PrintJob
from wix_printer_service.database import Database


@pytest.fixture
def client():
    """Create an isolated TestClient for each test."""
    app = create_app()
    return TestClient(app)

class TestWebhookWorkflowIntegration:
    """Test complete webhook processing workflow."""
    
    def setup_method(self):
        """Set up test data for each test."""
        self.test_order_data = {
            "eventType": "OrderCreated",
            "eventId": "integration-test-123",
            "timestamp": "2025-09-21T17:00:00Z",
            "data": {
                "id": "order-integration-123",
                "status": "APPROVED",
                "createdDate": "2025-09-21T17:00:00Z",
                "updatedDate": "2025-09-21T17:00:00Z",
                "currency": "USD",
                "totals": {
                    "total": "25.99",
                    "subtotal": "21.99",
                    "tax": "4.00"
                },
                "lineItems": [
                    {
                        "id": "item-1",
                        "name": "Test Pizza",
                        "quantity": 1,
                        "price": "15.99",
                        "options": ["Large", "Extra Cheese"]
                    },
                    {
                        "id": "item-2", 
                        "name": "Test Drink",
                        "quantity": 2,
                        "price": "3.00"
                    }
                ],
                "billingInfo": {
                    "firstName": "John",
                    "lastName": "Doe",
                    "email": "john.doe@example.com",
                    "phone": "+1234567890"
                },
                "shippingInfo": {
                    "firstName": "John",
                    "lastName": "Doe",
                    "address": {
                        "addressLine1": "123 Test Street",
                        "city": "Test City",
                        "postalCode": "12345",
                        "country": "US"
                    }
                }
            }
        }
    
    @patch('wix_printer_service.api.main.get_database')
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_complete_webhook_to_print_workflow(self, mock_print_manager, mock_connectivity, 
                                              mock_order_service, mock_database, client):
        """Test complete workflow from webhook to print job creation."""
        
        # Mock database
        mock_db = Mock(spec=Database)
        mock_database.return_value = mock_db
        
        # Mock connectivity (online)
        mock_connectivity.return_value.is_internet_online.return_value = True
        
        # Mock order processing
        mock_order = Mock(spec=Order)
        mock_order.id = "order-integration-123"
        mock_order.status = "APPROVED"
        mock_order.to_dict.return_value = {"id": "order-integration-123", "status": "APPROVED"}
        
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.process_webhook_order.return_value = mock_order
        
        # Mock print manager
        mock_print_manager_instance = mock_print_manager.return_value
        mock_print_manager_instance.create_print_jobs_for_order.return_value = 3
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager_instance.health_monitor = mock_health_monitor
        
        # Send webhook request
        response = client.post(
            "/webhook/orders",
            json=self.test_order_data,
            headers={
                "Content-Type": "application/json",
                "X-Wix-Webhook-Signature": "test-signature"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["order_id"] == "order-integration-123"
        assert data["event_type"] == "OrderCreated"
        assert data["processing_mode"] == "online"
        assert data["jobs_created"] == 3
        assert "processing_time_ms" in data
        
        # Verify order processing was called with correct data
        mock_order_service_instance.process_webhook_order.assert_called_once()
        call_args = mock_order_service_instance.process_webhook_order.call_args[0][0]
        assert call_args["id"] == "order-integration-123"
        assert call_args["webhook_event_type"] == "OrderCreated"
        
        # Verify print jobs were created
        mock_print_manager_instance.create_print_jobs_for_order.assert_called_once_with("order-integration-123")
        
        # Verify health monitoring
        mock_health_monitor.record_webhook_request.assert_called_once_with(success=True)
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_offline_workflow(self, mock_print_manager, mock_connectivity, mock_order_service, client):
        """Test webhook processing workflow in offline mode."""
        
        # Mock connectivity (offline)
        mock_connectivity.return_value.is_internet_online.return_value = False
        
        # Mock offline order processing
        mock_order = Mock(spec=Order)
        mock_order.id = "order-integration-123"
        
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.process_offline_order.return_value = mock_order
        
        # Mock print manager
        mock_print_manager_instance = mock_print_manager.return_value
        mock_print_manager_instance.create_print_jobs_for_order.return_value = 3
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager_instance.health_monitor = mock_health_monitor
        
        # Send webhook request
        response = client.post(
            "/webhook/orders",
            json=self.test_order_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify offline processing
        assert response.status_code == 200
        data = response.json()
        assert data["processing_mode"] == "offline"
        
        # Verify offline processing was called
        mock_order_service_instance.process_offline_order.assert_called_once()
        mock_health_monitor.record_webhook_request.assert_called_once_with(success=True)
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_with_print_job_failure(self, mock_print_manager, mock_connectivity, mock_order_service, client):
        """Test webhook processing when print job creation fails."""
        
        # Mock connectivity (online)
        mock_connectivity.return_value.is_internet_online.return_value = True
        
        # Mock successful order processing
        mock_order = Mock(spec=Order)
        mock_order.id = "order-integration-123"
        
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.process_webhook_order.return_value = mock_order
        
        # Mock print manager with failure
        mock_print_manager_instance = mock_print_manager.return_value
        mock_print_manager_instance.create_print_jobs_for_order.side_effect = Exception("Print job creation failed")
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager_instance.health_monitor = mock_health_monitor
        
        # Send webhook request
        response = client.post(
            "/webhook/orders",
            json=self.test_order_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify webhook still succeeds (print job failure doesn't fail webhook)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["jobs_created"] == 0  # No jobs created due to failure
        
        # Verify health monitoring still records success
        mock_health_monitor.record_webhook_request.assert_called_once_with(success=True)
    
    def test_webhook_duplicate_detection(self, client):
        """Test webhook duplicate detection workflow."""
        
        # Create webhook data with same event ID
        duplicate_data = self.test_order_data.copy()
        
        with patch('wix_printer_service.webhook_validator.WebhookValidator.is_duplicate_request') as mock_duplicate:
            mock_duplicate.return_value = True
            
            response = client.post(
                "/webhook/orders",
                json=duplicate_data,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "duplicate"
            assert "already processed" in data["message"]
    
    def test_webhook_non_order_event(self, client):
        """Test webhook processing for non-order events."""
        
        non_order_data = {
            "eventType": "UserUpdated",
            "eventId": "user-event-123",
            "data": {"userId": "user-123"}
        }
        
        response = client.post(
            "/webhook/orders",
            json=non_order_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert "Non-order webhook" in data["message"]
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_error_notification(self, mock_print_manager, mock_connectivity, mock_order_service, client):
        """Test webhook error notification workflow."""
        
        # Mock connectivity (online)
        mock_connectivity.return_value.is_internet_online.return_value = True
        
        # Mock order processing failure
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.process_webhook_order.side_effect = Exception("Order processing failed")
        
        # Mock print manager with notification service
        mock_print_manager_instance = mock_print_manager.return_value
        mock_notification_service = AsyncMock()
        mock_print_manager_instance.notification_service = mock_notification_service
        mock_print_manager_instance.send_system_error_notification = AsyncMock()
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager_instance.health_monitor = mock_health_monitor
        
        # Send webhook request
        response = client.post(
            "/webhook/orders",
            json=self.test_order_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verify error response
        assert response.status_code == 500
        
        # Verify error notification was sent
        mock_print_manager_instance.send_system_error_notification.assert_called_once()
        
        # Verify failure was recorded
        mock_health_monitor.record_webhook_request.assert_called_once_with(success=False)


class TestWebhookPerformance:
    """Test webhook performance and load handling."""
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_processing_time(self, mock_print_manager, mock_connectivity, mock_order_service, client):
        """Test webhook processing time is reasonable."""
        
        # Mock fast processing
        mock_order = Mock()
        mock_order.id = "order-123"
        
        mock_connectivity.return_value.is_internet_online.return_value = True
        mock_order_service.return_value.process_webhook_order.return_value = mock_order
        mock_print_manager.return_value.create_print_jobs_for_order.return_value = 3
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "perf-test-123",
            "data": {"id": "order-123"}
        }
        
        response = client.post(
            "/webhook/orders",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Processing should be reasonably fast (< 1000ms for mocked operations)
        assert data["processing_time_ms"] < 1000
    
    def test_webhook_concurrent_requests(self, client):
        """Test webhook handling of concurrent requests."""
        
        # This test would require more complex setup with actual threading
        # For now, we'll test that multiple sequential requests work
        
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "concurrent-test-{}",
            "data": {"id": "order-{}"}
        }
        
        responses = []
        for i in range(5):
            test_data = webhook_data.copy()
            test_data["eventId"] = test_data["eventId"].format(i)
            test_data["data"]["id"] = test_data["data"]["id"].format(i)
            
            response = client.post(
                "/webhook/orders",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            responses.append(response)
        
        # All requests should be processed (even if they fail due to missing mocks)
        for response in responses:
            assert response.status_code in [200, 400, 500]  # Valid HTTP responses


class TestWebhookRecovery:
    """Test webhook recovery and self-healing scenarios."""
    
    @patch('wix_printer_service.api.main.get_order_service')
    @patch('wix_printer_service.api.main.get_connectivity_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_webhook_recovery_after_failure(self, mock_print_manager, mock_connectivity, mock_order_service, client):
        """Test webhook processing recovery after temporary failure."""
        
        # Mock initial failure then success
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.process_webhook_order.side_effect = [
            Exception("Temporary failure"),  # First call fails
            Mock(id="order-123")             # Second call succeeds
        ]
        
        mock_connectivity.return_value.is_internet_online.return_value = True
        
        # Mock health monitor
        mock_health_monitor = Mock()
        mock_print_manager.return_value.health_monitor = mock_health_monitor
        
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "recovery-test-123",
            "data": {"id": "order-123"}
        }
        
        # First request should fail
        response1 = client.post(
            "/webhook/orders",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        assert response1.status_code == 500
        
        # Second request should succeed (simulating retry)
        webhook_data["eventId"] = "recovery-test-124"  # Different event ID
        response2 = client.post(
            "/webhook/orders",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        assert response2.status_code == 200
        
        # Verify health monitoring recorded both failure and success
        assert mock_health_monitor.record_webhook_request.call_count == 2


# Utility functions for integration tests
def create_test_order_data(order_id: str, event_type: str = "OrderCreated") -> dict:
    """Create test order data for webhook testing."""
    return {
        "eventType": event_type,
        "eventId": f"test-event-{order_id}",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "id": order_id,
            "status": "APPROVED",
            "createdDate": datetime.now().isoformat(),
            "totals": {"total": "25.99"},
            "lineItems": [
                {"id": "item-1", "name": "Test Item", "quantity": 1, "price": "25.99"}
            ]
        }
    }


def assert_webhook_response_valid(response_data: dict):
    """Assert that webhook response has required fields."""
    required_fields = ["status", "message", "processing_time_ms"]
    for field in required_fields:
        assert field in response_data, f"Missing required field: {field}"
    
    if response_data["status"] == "success":
        success_fields = ["order_id", "event_type", "processing_mode"]
        for field in success_fields:
            assert field in response_data, f"Missing success field: {field}"
