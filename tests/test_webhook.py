"""
Unit tests for webhook endpoint.
Tests webhook handling, validation, and order processing.
"""
import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from wix_printer_service.api.main import app


class TestWebhookEndpoint:
    """Test cases for the webhook endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_webhook_data(self):
        """Sample webhook data for testing."""
        return {
            "eventType": "orders/created",
            "data": {
                "id": "test_order_123",
                "status": "pending",
                "dateCreated": "2025-09-18T10:00:00Z",
                "lineItems": [
                    {
                        "id": "item_1",
                        "name": "Pizza Margherita",
                        "quantity": 2,
                        "price": {"amount": 12.50},
                        "sku": "PIZZA_MARG"
                    }
                ],
                "buyerInfo": {
                    "email": "customer@example.com",
                    "firstName": "Jane",
                    "lastName": "Smith"
                },
                "shippingInfo": {
                    "deliveryAddress": {
                        "addressLine1": "456 Oak Ave",
                        "city": "Springfield"
                    }
                },
                "totals": {
                    "total": {
                        "amount": 25.0,
                        "currency": "USD"
                    }
                }
            }
        }
    
    @patch('wix_printer_service.api.main.get_order_service')
    def test_webhook_success(self, mock_get_service, client, sample_webhook_data):
        """Test successful webhook processing."""
        # Mock order service
        mock_service = Mock()
        mock_order = Mock()
        mock_order.id = "test_order_123"
        mock_service.process_webhook_order.return_value = mock_order
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/webhook/orders",
            json=sample_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["order_id"] == "test_order_123"
        
        # Verify service was called
        mock_service.process_webhook_order.assert_called_once_with(sample_webhook_data)
    
    @patch('wix_printer_service.api.main.get_order_service')
    def test_webhook_processing_failure(self, mock_get_service, client, sample_webhook_data):
        """Test webhook processing failure."""
        # Mock order service to return None (processing failed)
        mock_service = Mock()
        mock_service.process_webhook_order.return_value = None
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/webhook/orders",
            json=sample_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        response_data = response.json()
        assert "Failed to process order" in response_data["detail"]
    
    @patch('wix_printer_service.api.main.get_order_service')
    def test_webhook_service_exception(self, mock_get_service, client, sample_webhook_data):
        """Test webhook with service exception."""
        # Mock order service to raise exception
        mock_service = Mock()
        mock_service.process_webhook_order.side_effect = Exception("Service error")
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/webhook/orders",
            json=sample_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 500
        response_data = response.json()
        assert "Internal server error" in response_data["detail"]
    
    def test_webhook_invalid_json(self, client):
        """Test webhook with invalid JSON."""
        response = client.post(
            "/webhook/orders",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Unprocessable Entity
    
    @patch.dict(os.environ, {'WIX_WEBHOOK_SECRET': 'test_secret'})
    @patch('wix_printer_service.api.main.get_wix_client')
    @patch('wix_printer_service.api.main.get_order_service')
    def test_webhook_signature_validation_success(self, mock_get_service, mock_get_client, client, sample_webhook_data):
        """Test successful webhook signature validation."""
        # Mock Wix client
        mock_client = Mock()
        mock_client.validate_webhook_signature.return_value = True
        mock_get_client.return_value = mock_client
        
        # Mock order service
        mock_service = Mock()
        mock_order = Mock()
        mock_order.id = "test_order_123"
        mock_service.process_webhook_order.return_value = mock_order
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/webhook/orders",
            json=sample_webhook_data,
            headers={
                "Content-Type": "application/json",
                "x-wix-webhook-signature": "valid_signature"
            }
        )
        
        assert response.status_code == 200
        
        # Verify signature validation was called
        mock_client.validate_webhook_signature.assert_called_once()
    
    @patch.dict(os.environ, {'WIX_WEBHOOK_SECRET': 'test_secret'})
    @patch('wix_printer_service.api.main.get_wix_client')
    def test_webhook_signature_validation_failure(self, mock_get_client, client, sample_webhook_data):
        """Test webhook signature validation failure."""
        # Mock Wix client to return invalid signature
        mock_client = Mock()
        mock_client.validate_webhook_signature.return_value = False
        mock_get_client.return_value = mock_client
        
        response = client.post(
            "/webhook/orders",
            json=sample_webhook_data,
            headers={
                "Content-Type": "application/json",
                "x-wix-webhook-signature": "invalid_signature"
            }
        )
        
        assert response.status_code == 401
        response_data = response.json()
        assert "Invalid webhook signature" in response_data["detail"]
    
    @patch.dict(os.environ, {}, clear=True)  # No webhook secret configured
    @patch('wix_printer_service.api.main.get_order_service')
    def test_webhook_no_signature_validation(self, mock_get_service, client, sample_webhook_data):
        """Test webhook without signature validation when secret not configured."""
        # Mock order service
        mock_service = Mock()
        mock_order = Mock()
        mock_order.id = "test_order_123"
        mock_service.process_webhook_order.return_value = mock_order
        mock_get_service.return_value = mock_service
        
        response = client.post(
            "/webhook/orders",
            json=sample_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        # Should succeed even without signature when secret not configured


class TestOrderEndpoint:
    """Test cases for the order retrieval endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @patch('wix_printer_service.api.main.get_order_service')
    def test_get_order_success(self, mock_get_service, client):
        """Test successful order retrieval."""
        # Mock order service
        mock_service = Mock()
        mock_order = Mock()
        mock_order.to_dict.return_value = {
            "id": "test_order_123",
            "status": "pending",
            "total_amount": 25.0
        }
        mock_service.get_order_by_id.return_value = mock_order
        mock_get_service.return_value = mock_service
        
        response = client.get("/orders/test_order_123")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["order"]["id"] == "test_order_123"
        
        # Verify service was called
        mock_service.get_order_by_id.assert_called_once_with("test_order_123")
    
    @patch('wix_printer_service.api.main.get_order_service')
    def test_get_order_not_found(self, mock_get_service, client):
        """Test order not found."""
        # Mock order service to return None
        mock_service = Mock()
        mock_service.get_order_by_id.return_value = None
        mock_get_service.return_value = mock_service
        
        response = client.get("/orders/nonexistent_order")
        
        assert response.status_code == 404
        response_data = response.json()
        assert "Order not found" in response_data["detail"]
    
    @patch('wix_printer_service.api.main.get_order_service')
    def test_get_order_service_exception(self, mock_get_service, client):
        """Test order retrieval with service exception."""
        # Mock order service to raise exception
        mock_service = Mock()
        mock_service.get_order_by_id.side_effect = Exception("Service error")
        mock_get_service.return_value = mock_service
        
        response = client.get("/orders/test_order")
        
        assert response.status_code == 500
        response_data = response.json()
        assert "Internal server error" in response_data["detail"]


class TestStatusEndpoint:
    """Test cases for the API status endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @patch('wix_printer_service.api.main.get_database')
    @patch('wix_printer_service.api.main.get_wix_client')
    def test_api_status_all_connected(self, mock_get_client, mock_get_db, client):
        """Test API status with all services connected."""
        # Mock database
        mock_db = Mock()
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value = mock_db
        
        # Mock Wix client
        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_get_client.return_value = mock_client
        
        response = client.get("/api/status")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["service"] == "running"
        assert response_data["database"] == "connected"
        assert response_data["wix_api"] == "connected"
    
    @patch('wix_printer_service.api.main.get_database')
    @patch('wix_printer_service.api.main.get_wix_client')
    def test_api_status_database_disconnected(self, mock_get_client, mock_get_db, client):
        """Test API status with database disconnected."""
        # Mock database to raise exception
        mock_db = Mock()
        mock_db.get_connection.side_effect = Exception("DB error")
        mock_get_db.return_value = mock_db
        
        # Mock Wix client
        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_get_client.return_value = mock_client
        
        response = client.get("/api/status")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["database"] == "disconnected"
        assert response_data["wix_api"] == "connected"
    
    @patch('wix_printer_service.api.main.get_database')
    @patch('wix_printer_service.api.main.get_wix_client')
    def test_api_status_wix_not_configured(self, mock_get_client, mock_get_db, client):
        """Test API status with Wix client not configured."""
        # Mock database
        mock_db = Mock()
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value = mock_db
        
        # Mock Wix client not configured
        mock_get_client.return_value = None
        
        response = client.get("/api/status")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["database"] == "connected"
        assert response_data["wix_api"] == "not_configured"
