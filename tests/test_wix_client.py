"""
Unit tests for the Wix API client.
Tests authentication, API communication, and error handling.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import requests

from wix_printer_service.wix_client import WixClient, WixAPIError


class TestWixClient:
    """Test cases for the WixClient class."""
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    def test_init_success(self):
        """Test successful initialization with environment variables."""
        client = WixClient()
        
        assert client.api_key == 'test_key'
        assert client.site_id == 'test_site'
        assert client.base_url == 'https://www.wixapis.com'
        assert 'Authorization' in client.session.headers
        assert client.session.headers['Authorization'] == 'Bearer test_key'
    
    @patch.dict(os.environ, {}, clear=True)
    def test_init_missing_api_key(self):
        """Test initialization failure when API key is missing."""
        with pytest.raises(WixAPIError, match="WIX_API_KEY environment variable is required"):
            WixClient()
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key'}, clear=True)
    def test_init_missing_site_id(self):
        """Test initialization failure when site ID is missing."""
        with pytest.raises(WixAPIError, match="WIX_SITE_ID environment variable is required"):
            WixClient()
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    @patch('requests.Session.get')
    def test_connection_success(self, mock_get):
        """Test successful API connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        client = WixClient()
        result = client.test_connection()
        
        assert result is True
        mock_get.assert_called_once()
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    @patch('requests.Session.get')
    def test_connection_failure(self, mock_get):
        """Test API connection test failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response
        
        client = WixClient()
        result = client.test_connection()
        
        assert result is False
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    @patch('requests.Session.get')
    def test_connection_exception(self, mock_get):
        """Test API connection test with network exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        client = WixClient()
        result = client.test_connection()
        
        assert result is False
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    @patch('requests.Session.get')
    def test_get_orders_success(self, mock_get):
        """Test successful order retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'orders': [{'id': '123', 'status': 'pending'}]}
        mock_get.return_value = mock_response
        
        client = WixClient()
        result = client.get_orders(limit=10, offset=0)
        
        assert result is not None
        assert 'orders' in result
        mock_get.assert_called_once_with(
            'https://www.wixapis.com/stores/v1/sites/test_site/orders',
            params={'limit': 10, 'offset': 0},
            timeout=30
        )
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    @patch('requests.Session.get')
    def test_get_orders_api_error(self, mock_get):
        """Test order retrieval with API error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_get.return_value = mock_response
        
        client = WixClient()
        
        with pytest.raises(WixAPIError, match="API request failed: 400"):
            client.get_orders()
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    @patch('requests.Session.get')
    def test_get_orders_network_error(self, mock_get):
        """Test order retrieval with network error."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        client = WixClient()
        
        with pytest.raises(WixAPIError, match="Network error"):
            client.get_orders()
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    def test_validate_webhook_signature_success(self):
        """Test successful webhook signature validation."""
        client = WixClient()
        payload = b'{"test": "data"}'
        webhook_secret = "test_secret"
        
        # Calculate expected signature
        import hmac
        import hashlib
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        result = client.validate_webhook_signature(payload, expected_signature, webhook_secret)
        assert result is True
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    def test_validate_webhook_signature_failure(self):
        """Test webhook signature validation failure."""
        client = WixClient()
        payload = b'{"test": "data"}'
        webhook_secret = "test_secret"
        invalid_signature = "invalid_signature"
        
        result = client.validate_webhook_signature(payload, invalid_signature, webhook_secret)
        assert result is False
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    def test_validate_webhook_signature_exception(self):
        """Test webhook signature validation with exception."""
        client = WixClient()
        
        # Test with invalid parameters that cause an exception
        result = client.validate_webhook_signature(None, "signature", "secret")
        assert result is False
    
    @patch.dict(os.environ, {'WIX_API_KEY': 'test_key', 'WIX_SITE_ID': 'test_site'})
    def test_close_session(self):
        """Test closing the HTTP session."""
        client = WixClient()
        mock_session = Mock()
        client.session = mock_session
        
        client.close()
        
        mock_session.close.assert_called_once()
