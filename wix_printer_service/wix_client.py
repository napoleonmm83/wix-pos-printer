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
