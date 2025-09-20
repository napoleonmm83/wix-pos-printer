"""
Wix API Client for handling authentication and API communication.
Provides secure connection to Wix Orders API with proper error handling.
"""
import os
import logging
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

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
        self.base_url = 'https://www.wixapis.com'
        
        if not self.api_key:
            raise WixAPIError("WIX_API_KEY environment variable is required")
        if not self.site_id:
            raise WixAPIError("WIX_SITE_ID environment variable is required")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        logger.info("Wix API client initialized successfully")
    
    def test_connection(self) -> bool:
        """
        Test the connection to Wix API.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Test with a simple API call to verify credentials
            response = self.session.get(
                f'{self.base_url}/stores/v1/sites/{self.site_id}/orders',
                params={'limit': 1},
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
    
    def get_orders(self, limit: int = 50, offset: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve orders from Wix API.
        
        Args:
            limit: Maximum number of orders to retrieve
            offset: Number of orders to skip
            
        Returns:
            Dict containing orders data or None if failed
        """
        try:
            response = self.session.get(
                f'{self.base_url}/stores/v1/sites/{self.site_id}/orders',
                params={'limit': limit, 'offset': offset},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully retrieved {limit} orders from Wix API")
                return response.json()
            else:
                logger.error(f"Failed to retrieve orders: {response.status_code} - {response.text}")
                raise WixAPIError(f"API request failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving orders from Wix API: {e}")
            raise WixAPIError(f"Network error: {str(e)}")
    
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
