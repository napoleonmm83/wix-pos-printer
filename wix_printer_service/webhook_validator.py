"""
Webhook signature validation utility for Wix webhooks.
Provides secure validation of incoming webhook requests.
"""
import os
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class WebhookValidator:
    """
    Validates Wix webhook signatures and requests for security.
    """
    
    def __init__(self):
        """Initialize webhook validator with configuration."""
        self.webhook_secret = os.getenv('WIX_WEBHOOK_SECRET')
        self.require_signature = os.getenv('WIX_WEBHOOK_REQUIRE_SIGNATURE', 'true').lower() == 'true'
        
        if not self.webhook_secret and self.require_signature:
            logger.warning("WIX_WEBHOOK_SECRET not configured - webhook signature validation disabled")
            self.require_signature = False
    
    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate Wix webhook signature.
        
        Args:
            payload: Raw request payload bytes
            signature: Signature from X-Wix-Webhook-Signature header
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured - skipping signature validation")
            return not self.require_signature
        
        if not signature:
            logger.warning("Missing webhook signature")
            return not self.require_signature
        
        try:
            # Wix uses HMAC-SHA256 for webhook signatures
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Remove any prefix (like 'sha256=') from the signature
            if '=' in signature:
                signature = signature.split('=', 1)[1]
            
            # Use constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature. Expected: {expected_signature[:8]}..., Got: {signature[:8]}...")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False
    
    def validate_request(self, request: Request, payload: bytes) -> Dict[str, Any]:
        """
        Validate webhook request including signature and headers.
        
        Args:
            request: FastAPI request object
            payload: Raw request payload bytes
            
        Returns:
            dict: Validation result with status and details
            
        Raises:
            HTTPException: If validation fails and strict mode is enabled
        """
        result = {
            "valid": True,
            "signature_valid": True,
            "content_type_valid": True,
            "user_agent_valid": True,
            "warnings": []
        }
        
        # Check Content-Type
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            result["content_type_valid"] = False
            result["warnings"].append(f"Unexpected Content-Type: {content_type}")
        
        # Check User-Agent (Wix webhooks should have specific user agent)
        user_agent = request.headers.get("user-agent", "")
        if not user_agent.startswith("Wix"):
            result["user_agent_valid"] = False
            result["warnings"].append(f"Unexpected User-Agent: {user_agent}")
        
        # Validate signature
        signature = request.headers.get("X-Wix-Webhook-Signature")
        if not self.validate_signature(payload, signature):
            result["signature_valid"] = False
            result["valid"] = False
            
            if self.require_signature:
                logger.error("Webhook signature validation failed")
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid webhook signature"
                )
            else:
                result["warnings"].append("Signature validation failed but not required")
        
        # Overall validation
        if not result["content_type_valid"] or not result["user_agent_valid"]:
            result["valid"] = False
            
            # In strict mode, reject requests with invalid headers
            if self.require_signature:
                logger.error(f"Webhook validation failed: {result['warnings']}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid webhook request headers"
                )
        
        return result
    
    def is_duplicate_request(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Check if this webhook request is a duplicate.
        
        Args:
            webhook_data: Parsed webhook payload
            
        Returns:
            bool: True if this appears to be a duplicate request
        """
        # Basic duplicate detection based on event ID and timestamp
        event_id = webhook_data.get('eventId')
        event_type = webhook_data.get('eventType')
        timestamp = webhook_data.get('timestamp')
        
        if not event_id:
            logger.warning("Webhook missing eventId - cannot check for duplicates")
            return False
        
        # In a production system, you would store processed event IDs
        # and check against them. For now, we'll implement basic logic.
        logger.info(f"Processing webhook event: {event_type} - {event_id}")
        
        # TODO: Implement actual duplicate detection with database storage
        return False
    
    def extract_order_data(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract order data from webhook payload.
        
        Args:
            webhook_data: Raw webhook payload
            
        Returns:
            dict: Extracted order data or None if not an order event
        """
        event_type = webhook_data.get('eventType', '')
        
        # Handle different Wix webhook event types
        if event_type in ['OrderCreated', 'OrderUpdated', 'OrderPaid']:
            # Extract order data from webhook
            order_data = webhook_data.get('data', {})
            
            if not order_data:
                logger.warning(f"Webhook {event_type} missing order data")
                return None
            
            # Add event metadata
            order_data['webhook_event_type'] = event_type
            order_data['webhook_event_id'] = webhook_data.get('eventId')
            order_data['webhook_timestamp'] = webhook_data.get('timestamp')
            
            return order_data
        
        else:
            logger.info(f"Ignoring non-order webhook event: {event_type}")
            return None


# Global validator instance
_webhook_validator = None


def get_webhook_validator() -> WebhookValidator:
    """Get global webhook validator instance."""
    global _webhook_validator
    if _webhook_validator is None:
        _webhook_validator = WebhookValidator()
    return _webhook_validator
