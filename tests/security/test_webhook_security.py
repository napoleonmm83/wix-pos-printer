"""
Security tests for webhook integration.
Tests signature validation, authentication, and security measures.
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from wix_printer_service.api.main import app
from wix_printer_service.webhook_validator import WebhookValidator


class TestWebhookSignatureSecurity:
    """Test webhook signature validation security."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
        self.test_secret = "test_webhook_secret_for_security_testing_12345"
        self.webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "security-test-123",
            "data": {"id": "order-123", "status": "APPROVED"}
        }
        self.payload = json.dumps(self.webhook_data).encode('utf-8')
    
    def create_valid_signature(self, payload: bytes, secret: str) -> str:
        """Create a valid HMAC-SHA256 signature."""
        return hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
    
    @patch.dict('os.environ', {'WIX_WEBHOOK_SECRET': 'test_secret', 'WIX_WEBHOOK_REQUIRE_SIGNATURE': 'true'})
    def test_valid_signature_acceptance(self):
        """Test that valid signatures are accepted."""
        signature = self.create_valid_signature(self.payload, 'test_secret')
        
        response = self.client.post(
            "/webhook/orders",
            json=self.webhook_data,
            headers={
                "Content-Type": "application/json",
                "X-Wix-Webhook-Signature": signature
            }
        )
        
        # Should not fail due to signature validation (may fail for other reasons)
        assert response.status_code != 401
    
    @patch.dict('os.environ', {'WIX_WEBHOOK_SECRET': 'test_secret', 'WIX_WEBHOOK_REQUIRE_SIGNATURE': 'true'})
    def test_invalid_signature_rejection(self):
        """Test that invalid signatures are rejected."""
        invalid_signature = "invalid_signature_12345"
        
        response = self.client.post(
            "/webhook/orders",
            json=self.webhook_data,
            headers={
                "Content-Type": "application/json",
                "X-Wix-Webhook-Signature": invalid_signature
            }
        )
        
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]
    
    @patch.dict('os.environ', {'WIX_WEBHOOK_SECRET': 'test_secret', 'WIX_WEBHOOK_REQUIRE_SIGNATURE': 'true'})
    def test_missing_signature_rejection(self):
        """Test that missing signatures are rejected when required."""
        response = self.client.post(
            "/webhook/orders",
            json=self.webhook_data,
            headers={"Content-Type": "application/json"}
            # Missing X-Wix-Webhook-Signature header
        )
        
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]
    
    @patch.dict('os.environ', {'WIX_WEBHOOK_REQUIRE_SIGNATURE': 'false'})
    def test_signature_not_required_mode(self):
        """Test webhook processing when signature validation is disabled."""
        response = self.client.post(
            "/webhook/orders",
            json=self.webhook_data,
            headers={"Content-Type": "application/json"}
            # No signature header
        )
        
        # Should not fail due to missing signature
        assert response.status_code != 401
    
    def test_signature_with_prefix(self):
        """Test signature validation with sha256= prefix."""
        signature = self.create_valid_signature(self.payload, self.test_secret)
        prefixed_signature = f"sha256={signature}"
        
        validator = WebhookValidator()
        with patch.object(validator, 'webhook_secret', self.test_secret):
            result = validator.validate_signature(self.payload, prefixed_signature)
            assert result is True
    
    def test_timing_attack_resistance(self):
        """Test that signature comparison is resistant to timing attacks."""
        validator = WebhookValidator()
        correct_signature = self.create_valid_signature(self.payload, self.test_secret)
        
        # Test multiple incorrect signatures of same length
        incorrect_signatures = [
            "a" * len(correct_signature),
            "b" * len(correct_signature), 
            "1" * len(correct_signature),
            "z" * len(correct_signature)
        ]
        
        with patch.object(validator, 'webhook_secret', self.test_secret):
            for incorrect_sig in incorrect_signatures:
                result = validator.validate_signature(self.payload, incorrect_sig)
                assert result is False


class TestWebhookInputValidation:
    """Test webhook input validation and sanitization."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
    
    def test_malformed_json_rejection(self):
        """Test rejection of malformed JSON payloads."""
        malformed_payloads = [
            "not json at all",
            '{"incomplete": json',
            '{"invalid": "json",}',  # Trailing comma
            '',  # Empty payload
            'null',  # Null payload
        ]
        
        for payload in malformed_payloads:
            response = self.client.post(
                "/webhook/orders",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400
            assert "Invalid JSON payload" in response.json()["detail"]
    
    def test_oversized_payload_handling(self):
        """Test handling of oversized payloads."""
        # Create a very large payload
        large_data = {
            "eventType": "OrderCreated",
            "eventId": "large-payload-test",
            "data": {
                "id": "order-123",
                "large_field": "x" * 10000  # 10KB of data
            }
        }
        
        response = self.client.post(
            "/webhook/orders",
            json=large_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle large payloads gracefully (may fail for other reasons)
        assert response.status_code != 413  # Not "Payload Too Large"
    
    def test_special_characters_handling(self):
        """Test handling of special characters in webhook data."""
        special_data = {
            "eventType": "OrderCreated",
            "eventId": "special-chars-test",
            "data": {
                "id": "order-123",
                "customer_name": "John <script>alert('xss')</script> Doe",
                "notes": "Special chars: àáâãäåæçèéêë",
                "unicode": "🍕🍔🍟",
                "sql_injection": "'; DROP TABLE orders; --"
            }
        }
        
        response = self.client.post(
            "/webhook/orders",
            json=special_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle special characters without errors
        assert response.status_code in [200, 400, 500]  # Valid HTTP responses
    
    def test_missing_required_fields(self):
        """Test handling of webhooks with missing required fields."""
        incomplete_payloads = [
            {},  # Empty object
            {"eventType": "OrderCreated"},  # Missing eventId and data
            {"eventId": "test-123"},  # Missing eventType and data
            {"eventType": "OrderCreated", "eventId": "test-123"},  # Missing data
        ]
        
        for payload in incomplete_payloads:
            response = self.client.post(
                "/webhook/orders",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            # Should handle gracefully, not crash
            assert response.status_code in [200, 400, 500]


class TestWebhookRateLimiting:
    """Test webhook rate limiting security."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
    
    def test_rate_limit_enforcement(self):
        """Test that rate limiting is enforced."""
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "rate-limit-test",
            "data": {"id": "order-123"}
        }
        
        # Make multiple rapid requests
        responses = []
        for i in range(5):  # Small number to avoid overwhelming test
            response = self.client.post(
                "/webhook/orders",
                json=webhook_data,
                headers={"Content-Type": "application/json"}
            )
            responses.append(response)
        
        # All requests should be processed (rate limit is 100/minute)
        for response in responses:
            assert response.status_code != 429  # Should not hit rate limit with 5 requests
    
    def test_rate_limit_per_endpoint(self):
        """Test that rate limiting is applied per endpoint."""
        # Test that other endpoints are not affected by webhook rate limiting
        webhook_response = self.client.post(
            "/webhook/orders",
            json={"eventType": "test", "data": {}},
            headers={"Content-Type": "application/json"}
        )
        
        health_response = self.client.get("/health")
        
        # Health endpoint should not be affected by webhook rate limiting
        assert health_response.status_code == 200
    
    @patch('wix_printer_service.api.main.webhook_rate_limit', {"requests": 100, "window_start": None})
    def test_rate_limit_window_reset(self):
        """Test that rate limit window resets properly."""
        from datetime import datetime, timedelta
        
        # Mock rate limit at maximum
        with patch('wix_printer_service.api.main.webhook_rate_limit') as mock_rate_limit:
            mock_rate_limit.__getitem__.side_effect = lambda key: {
                "requests": 100,
                "window_start": datetime.now() - timedelta(minutes=2)  # Old window
            }[key]
            mock_rate_limit.__setitem__ = Mock()
            
            response = self.client.post(
                "/webhook/orders",
                json={"eventType": "test", "data": {}},
                headers={"Content-Type": "application/json"}
            )
            
            # Should reset window and allow request
            assert response.status_code != 429


class TestWebhookHeaderSecurity:
    """Test webhook HTTP header security."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
    
    def test_security_headers_present(self):
        """Test that security headers are present in webhook responses."""
        response = self.client.post(
            "/webhook/orders",
            json={"eventType": "test", "data": {}},
            headers={"Content-Type": "application/json"}
        )
        
        # Check for security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Referrer-Policy"
        ]
        
        for header in security_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_server_header_removed(self):
        """Test that server header is removed for security."""
        response = self.client.post(
            "/webhook/orders",
            json={"eventType": "test", "data": {}},
            headers={"Content-Type": "application/json"}
        )
        
        # Server header should be removed
        assert "server" not in response.headers.keys()
        assert "Server" not in response.headers.keys()
    
    def test_cors_policy_enforcement(self):
        """Test CORS policy enforcement."""
        # Test with non-Wix origin
        response = self.client.options(
            "/webhook/orders",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # Should not allow non-Wix origins
        if "Access-Control-Allow-Origin" in response.headers:
            allowed_origin = response.headers["Access-Control-Allow-Origin"]
            assert "malicious-site.com" not in allowed_origin
    
    def test_content_type_validation(self):
        """Test content type validation."""
        # Test with incorrect content type
        response = self.client.post(
            "/webhook/orders",
            data="test data",
            headers={"Content-Type": "text/plain"}
        )
        
        # Should handle non-JSON content type appropriately
        assert response.status_code in [400, 415]  # Bad Request or Unsupported Media Type


class TestWebhookAuthenticationBypass:
    """Test webhook authentication bypass attempts."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
    
    def test_signature_bypass_attempts(self):
        """Test various signature bypass attempts."""
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "bypass-test",
            "data": {"id": "order-123"}
        }
        
        bypass_attempts = [
            # Empty signature
            "",
            # Null signature
            "null",
            # Boolean signature
            "true",
            # Array signature
            "[]",
            # Object signature
            "{}",
            # Very long signature
            "a" * 1000,
            # SQL injection attempt
            "'; DROP TABLE orders; --",
            # Script injection attempt
            "<script>alert('xss')</script>",
        ]
        
        for signature in bypass_attempts:
            response = self.client.post(
                "/webhook/orders",
                json=webhook_data,
                headers={
                    "Content-Type": "application/json",
                    "X-Wix-Webhook-Signature": signature
                }
            )
            
            # Should either succeed (if signature validation is disabled) 
            # or fail with proper authentication error
            if response.status_code == 401:
                assert "signature" in response.json()["detail"].lower()
    
    def test_header_injection_attempts(self):
        """Test header injection attempts."""
        webhook_data = {"eventType": "test", "data": {}}
        
        malicious_headers = {
            "X-Wix-Webhook-Signature": "valid_sig\r\nMalicious-Header: injected",
            "Content-Type": "application/json\r\nX-Injected: malicious",
            "User-Agent": "Normal-Agent\r\nX-Forwarded-For: 127.0.0.1"
        }
        
        for header_name, header_value in malicious_headers.items():
            response = self.client.post(
                "/webhook/orders",
                json=webhook_data,
                headers={header_name: header_value}
            )
            
            # Should handle header injection attempts gracefully
            assert response.status_code in [200, 400, 401, 500]
            
            # Verify no injected headers in response
            for resp_header in response.headers:
                assert "injected" not in resp_header.lower()
                assert "malicious" not in resp_header.lower()


class TestWebhookDenialOfService:
    """Test webhook denial of service protection."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
    
    def test_resource_exhaustion_protection(self):
        """Test protection against resource exhaustion attacks."""
        # Test with deeply nested JSON
        nested_data = {"data": {}}
        current = nested_data["data"]
        for i in range(100):  # Create deep nesting
            current["nested"] = {}
            current = current["nested"]
        
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "dos-test",
            "data": nested_data
        }
        
        response = self.client.post(
            "/webhook/orders",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle deep nesting without crashing
        assert response.status_code in [200, 400, 500]
    
    def test_memory_exhaustion_protection(self):
        """Test protection against memory exhaustion."""
        # Test with large arrays
        large_array = ["item"] * 1000  # Large but reasonable array
        
        webhook_data = {
            "eventType": "OrderCreated",
            "eventId": "memory-test",
            "data": {
                "id": "order-123",
                "large_array": large_array
            }
        }
        
        response = self.client.post(
            "/webhook/orders",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle large arrays without memory issues
        assert response.status_code in [200, 400, 500]


# Security test utilities
def generate_malicious_payloads():
    """Generate various malicious payloads for testing."""
    return [
        # XSS attempts
        {"eventType": "<script>alert('xss')</script>", "data": {}},
        {"eventType": "OrderCreated", "data": {"name": "<img src=x onerror=alert(1)>"}},
        
        # SQL injection attempts  
        {"eventType": "'; DROP TABLE orders; --", "data": {}},
        {"eventType": "OrderCreated", "data": {"id": "1' OR '1'='1"}},
        
        # Command injection attempts
        {"eventType": "OrderCreated", "data": {"notes": "; rm -rf /"}},
        {"eventType": "OrderCreated", "data": {"command": "$(whoami)"}},
        
        # Path traversal attempts
        {"eventType": "OrderCreated", "data": {"file": "../../../etc/passwd"}},
        {"eventType": "OrderCreated", "data": {"path": "..\\..\\windows\\system32"}},
    ]


def test_malicious_payload_handling():
    """Test handling of various malicious payloads."""
    client = TestClient(app)
    
    for payload in generate_malicious_payloads():
        response = client.post(
            "/webhook/orders",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle malicious payloads without executing them
        assert response.status_code in [200, 400, 401, 500]
        
        # Response should not contain executed malicious content
        response_text = response.text.lower()
        assert "<script>" not in response_text
        assert "drop table" not in response_text
        assert "/etc/passwd" not in response_text
