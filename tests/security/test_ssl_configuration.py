"""
SSL configuration and security tests for public URL setup.
Tests SSL certificate validation, security headers, and HTTPS enforcement.
"""
import pytest
import ssl
import socket
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import requests
from fastapi.testclient import TestClient

from wix_printer_service.api.main import create_app


class TestSSLCertificateValidation:
    """Test SSL certificate validation functionality."""
    
    def test_ssl_context_configuration(self):
        """Test SSL context configuration."""
        context = ssl.create_default_context()
        
        # Verify default security settings
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.protocol == ssl.PROTOCOL_TLS_CLIENT
    
    def test_certificate_date_parsing(self):
        """Test certificate expiry date parsing."""
        def parse_cert_date(date_string):
            """Parse certificate date string."""
            try:
                return datetime.strptime(date_string, '%b %d %H:%M:%S %Y %Z')
            except ValueError:
                return None
        
        # Test valid date formats
        valid_date = "Dec 31 23:59:59 2025 GMT"
        parsed_date = parse_cert_date(valid_date)
        assert parsed_date is not None
        assert parsed_date.year == 2025
        assert parsed_date.month == 12
        assert parsed_date.day == 31
        
        # Test invalid date format
        invalid_date = "Invalid date format"
        parsed_date = parse_cert_date(invalid_date)
        assert parsed_date is None
    
    def test_certificate_expiry_calculation(self):
        """Test certificate expiry calculation."""
        def calculate_days_until_expiry(expiry_date):
            """Calculate days until certificate expiry."""
            if not expiry_date:
                return None
            return (expiry_date - datetime.now()).days
        
        # Test future expiry
        future_date = datetime.now() + timedelta(days=30)
        days = calculate_days_until_expiry(future_date)
        assert 29 <= days <= 30  # Account for timing differences
        
        # Test past expiry
        past_date = datetime.now() - timedelta(days=5)
        days = calculate_days_until_expiry(past_date)
        assert days < 0
        
        # Test None input
        days = calculate_days_until_expiry(None)
        assert days is None
    
    @patch('socket.create_connection')
    @patch('ssl.create_default_context')
    def test_ssl_certificate_retrieval(self, mock_ssl_context, mock_connection):
        """Test SSL certificate retrieval from server."""
        # Mock certificate data
        mock_cert = {
            'notAfter': 'Dec 31 23:59:59 2025 GMT',
            'notBefore': 'Jan 01 00:00:00 2025 GMT',
            'issuer': [
                ['countryName', 'US'],
                ['organizationName', "Let's Encrypt"],
                ['commonName', "Let's Encrypt Authority X3"]
            ],
            'subject': [
                ['countryName', 'US'],
                ['stateOrProvinceName', 'California'],
                ['localityName', 'San Francisco'],
                ['organizationName', 'Example Corp'],
                ['commonName', 'test.example.com']
            ],
            'subjectAltName': [
                ['DNS', 'test.example.com'],
                ['DNS', 'www.test.example.com']
            ],
            'serialNumber': '1234567890ABCDEF',
            'version': 3
        }
        
        # Mock SSL socket
        mock_ssl_socket = MagicMock()
        mock_ssl_socket.getpeercert.return_value = mock_cert
        
        # Mock SSL context
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssl_socket
        
        # Mock socket connection
        mock_socket = MagicMock()
        mock_connection.return_value.__enter__.return_value = mock_socket
        
        def get_ssl_certificate(hostname, port=443):
            """Get SSL certificate from server."""
            try:
                context = mock_ssl_context()
                with mock_connection((hostname, port), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                        return ssock.getpeercert()
            except Exception as e:
                return None
        
        cert = get_ssl_certificate('test.example.com')
        
        assert cert is not None
        assert cert['notAfter'] == 'Dec 31 23:59:59 2025 GMT'
        assert any('Let\'s Encrypt' in str(issuer) for issuer in cert['issuer'])
        assert any('test.example.com' in str(subject) for subject in cert['subject'])
    
    def test_certificate_chain_validation(self):
        """Test certificate chain validation logic."""
        def validate_certificate_chain(cert_data):
            """Validate certificate chain structure."""
            required_fields = ['notAfter', 'notBefore', 'issuer', 'subject']
            
            if not cert_data:
                return False, "Certificate data is empty"
            
            for field in required_fields:
                if field not in cert_data:
                    return False, f"Missing required field: {field}"
            
            # Check if certificate is self-signed
            issuer_cn = None
            subject_cn = None
            
            for item in cert_data.get('issuer', []):
                if item[0] == 'commonName':
                    issuer_cn = item[1]
                    break
            
            for item in cert_data.get('subject', []):
                if item[0] == 'commonName':
                    subject_cn = item[1]
                    break
            
            if issuer_cn == subject_cn:
                return False, "Certificate is self-signed"
            
            return True, "Certificate chain is valid"
        
        # Test valid certificate
        valid_cert = {
            'notAfter': 'Dec 31 23:59:59 2025 GMT',
            'notBefore': 'Jan 01 00:00:00 2025 GMT',
            'issuer': [['commonName', "Let's Encrypt Authority"]],
            'subject': [['commonName', 'test.example.com']]
        }
        
        is_valid, message = validate_certificate_chain(valid_cert)
        assert is_valid is True
        assert "valid" in message
        
        # Test self-signed certificate
        self_signed_cert = {
            'notAfter': 'Dec 31 23:59:59 2025 GMT',
            'notBefore': 'Jan 01 00:00:00 2025 GMT',
            'issuer': [['commonName', 'test.example.com']],
            'subject': [['commonName', 'test.example.com']]
        }
        
        is_valid, message = validate_certificate_chain(self_signed_cert)
        assert is_valid is False
        assert "self-signed" in message
        
        # Test missing fields
        incomplete_cert = {
            'notAfter': 'Dec 31 23:59:59 2025 GMT'
            # Missing other required fields
        }
        
        is_valid, message = validate_certificate_chain(incomplete_cert)
        assert is_valid is False
        assert "Missing required field" in message


@pytest.fixture
def client():
    """Create an isolated TestClient for each test."""
    app = create_app()
    with TestClient(app) as c:
        yield c

class TestSecurityHeaders:
    """Test security headers implementation."""
    
    def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = client.get("/health")
        
        # Check for security headers
        expected_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
        
        for header, expected_value in expected_headers.items():
            assert header in response.headers, f"Missing security header: {header}"
            assert response.headers[header] == expected_value, f"Incorrect value for {header}"
    
    def test_server_header_removed(self, client):
        """Test that server header is removed for security."""
        response = client.get("/health")
        
        # Server header should be removed
        assert "server" not in response.headers.keys()
        assert "Server" not in response.headers.keys()
    
    def test_security_headers_on_webhook_endpoint(self, client):
        """Test security headers on webhook endpoint."""
        # Test with invalid webhook data to avoid processing
        response = client.post(
            "/webhook/orders",
            json={"invalid": "data"},
            headers={"Content-Type": "application/json"}
        )
        
        # Regardless of response status, security headers should be present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Strict-Transport-Security" in response.headers
    
    def test_cors_headers_configuration(self, client):
        """Test CORS headers configuration."""
        # Test preflight request
        response = client.options(
            "/webhook/orders",
            headers={
                "Origin": "https://www.wix.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Should allow Wix domains
        assert response.status_code in [200, 204]
        
        # Test with non-Wix origin (should be restricted)
        response = client.options(
            "/webhook/orders",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # CORS should restrict non-Wix origins
        if "Access-Control-Allow-Origin" in response.headers:
            allowed_origin = response.headers["Access-Control-Allow-Origin"]
            assert "malicious-site.com" not in allowed_origin


class TestHTTPSEnforcement:
    """Test HTTPS enforcement and redirection."""
    
    def test_https_redirect_logic(self):
        """Test HTTPS redirect logic simulation."""
        def should_redirect_to_https(request_scheme, request_host):
            """Determine if request should be redirected to HTTPS."""
            if request_scheme == 'http':
                return True, f"https://{request_host}"
            return False, None
        
        # Test HTTP request (should redirect)
        should_redirect, redirect_url = should_redirect_to_https('http', 'test.example.com')
        assert should_redirect is True
        assert redirect_url == 'https://test.example.com'
        
        # Test HTTPS request (should not redirect)
        should_redirect, redirect_url = should_redirect_to_https('https', 'test.example.com')
        assert should_redirect is False
        assert redirect_url is None
    
    def test_hsts_header_configuration(self, client):
        """Test HSTS header configuration."""
        response = client.get("/health")
        
        hsts_header = response.headers.get("Strict-Transport-Security")
        assert hsts_header is not None
        
        # Parse HSTS header
        assert "max-age=" in hsts_header
        assert "includeSubDomains" in hsts_header
        
        # Extract max-age value
        max_age_part = [part for part in hsts_header.split(';') if 'max-age=' in part][0]
        max_age_value = int(max_age_part.split('=')[1].strip())
        
        # Should be at least 1 year (31536000 seconds)
        assert max_age_value >= 31536000
    
    def test_secure_cookie_configuration(self):
        """Test secure cookie configuration logic."""
        def configure_secure_cookies(is_https):
            """Configure secure cookie settings."""
            cookie_config = {
                'secure': is_https,
                'httponly': True,
                'samesite': 'strict'
            }
            
            if is_https:
                cookie_config['secure'] = True
            
            return cookie_config
        
        # Test HTTPS configuration
        https_config = configure_secure_cookies(True)
        assert https_config['secure'] is True
        assert https_config['httponly'] is True
        assert https_config['samesite'] == 'strict'
        
        # Test HTTP configuration
        http_config = configure_secure_cookies(False)
        assert http_config['secure'] is False
        assert http_config['httponly'] is True


class TestSSLConfigurationValidation:
    """Test SSL configuration validation."""
    
    def test_ssl_protocol_validation(self):
        """Test SSL protocol validation."""
        def validate_ssl_protocol(protocol_version):
            """Validate SSL protocol version."""
            secure_protocols = [
                ssl.PROTOCOL_TLS_CLIENT,
                ssl.PROTOCOL_TLS_SERVER
            ]
            
            # Check if protocol is secure
            if hasattr(ssl, 'PROTOCOL_TLS'):
                secure_protocols.append(ssl.PROTOCOL_TLS)
            
            return protocol_version in secure_protocols
        
        # Test secure protocol
        assert validate_ssl_protocol(ssl.PROTOCOL_TLS_CLIENT) is True
        
        # Test deprecated protocols (if available)
        if hasattr(ssl, 'PROTOCOL_SSLv3'):
            assert validate_ssl_protocol(ssl.PROTOCOL_SSLv3) is False
    
    def test_cipher_suite_validation(self):
        """Test cipher suite validation."""
        def validate_cipher_suites(context):
            """Validate SSL cipher suites."""
            try:
                # Get available ciphers
                ciphers = context.get_ciphers()
                
                # Check for secure ciphers
                secure_cipher_patterns = [
                    'ECDHE',  # Elliptic Curve Diffie-Hellman Ephemeral
                    'AES',    # Advanced Encryption Standard
                    'GCM',    # Galois/Counter Mode
                    'SHA256', # SHA-256 hash
                    'SHA384'  # SHA-384 hash
                ]
                
                secure_ciphers = []
                for cipher in ciphers:
                    cipher_name = cipher.get('name', '')
                    if any(pattern in cipher_name for pattern in secure_cipher_patterns):
                        secure_ciphers.append(cipher_name)
                
                return len(secure_ciphers) > 0, secure_ciphers
            except Exception:
                return False, []
        
        # Test with default context
        context = ssl.create_default_context()
        has_secure_ciphers, secure_ciphers = validate_cipher_suites(context)
        
        # Default context should have secure ciphers
        assert has_secure_ciphers is True
        assert len(secure_ciphers) > 0
    
    def test_certificate_verification_levels(self):
        """Test certificate verification levels."""
        verification_levels = {
            ssl.CERT_NONE: "No certificate verification",
            ssl.CERT_OPTIONAL: "Optional certificate verification", 
            ssl.CERT_REQUIRED: "Required certificate verification"
        }
        
        # Test that CERT_REQUIRED is the most secure
        assert ssl.CERT_REQUIRED > ssl.CERT_OPTIONAL
        assert ssl.CERT_REQUIRED > ssl.CERT_NONE
        
        # Test default context uses required verification
        context = ssl.create_default_context()
        assert context.verify_mode == ssl.CERT_REQUIRED


class TestSSLErrorHandling:
    """Test SSL error handling."""
    
    def test_ssl_error_classification(self):
        """Test SSL error classification."""
        def classify_ssl_error(error_message):
            """Classify SSL error types."""
            error_message = error_message.lower()
            
            if 'certificate verify failed' in error_message:
                return 'certificate_verification_failed'
            elif 'certificate has expired' in error_message:
                return 'certificate_expired'
            elif 'hostname mismatch' in error_message:
                return 'hostname_mismatch'
            elif 'self signed certificate' in error_message:
                return 'self_signed_certificate'
            elif 'connection refused' in error_message:
                return 'connection_refused'
            elif 'timeout' in error_message:
                return 'connection_timeout'
            else:
                return 'unknown_ssl_error'
        
        # Test various error classifications
        assert classify_ssl_error("certificate verify failed") == 'certificate_verification_failed'
        assert classify_ssl_error("certificate has expired") == 'certificate_expired'
        assert classify_ssl_error("hostname mismatch") == 'hostname_mismatch'
        assert classify_ssl_error("self signed certificate") == 'self_signed_certificate'
        assert classify_ssl_error("connection refused") == 'connection_refused'
        assert classify_ssl_error("timeout occurred") == 'connection_timeout'
        assert classify_ssl_error("unknown error") == 'unknown_ssl_error'
    
    def test_ssl_error_recovery_strategies(self):
        """Test SSL error recovery strategies."""
        def get_recovery_strategy(error_type):
            """Get recovery strategy for SSL error."""
            strategies = {
                'certificate_verification_failed': 'Check certificate chain and CA bundle',
                'certificate_expired': 'Renew SSL certificate',
                'hostname_mismatch': 'Verify domain name matches certificate',
                'self_signed_certificate': 'Install proper CA-signed certificate',
                'connection_refused': 'Check if HTTPS service is running',
                'connection_timeout': 'Check network connectivity and firewall',
                'unknown_ssl_error': 'Review SSL configuration and logs'
            }
            
            return strategies.get(error_type, 'Contact system administrator')
        
        # Test recovery strategies
        assert 'certificate chain' in get_recovery_strategy('certificate_verification_failed')
        assert 'Renew' in get_recovery_strategy('certificate_expired')
        assert 'domain name' in get_recovery_strategy('hostname_mismatch')
        assert 'CA-signed' in get_recovery_strategy('self_signed_certificate')


# Test utilities and fixtures
@pytest.fixture
def mock_ssl_certificate():
    """Fixture for mock SSL certificate."""
    return {
        'notAfter': 'Dec 31 23:59:59 2025 GMT',
        'notBefore': 'Jan 01 00:00:00 2025 GMT',
        'issuer': [
            ['countryName', 'US'],
            ['organizationName', "Let's Encrypt"],
            ['commonName', "Let's Encrypt Authority X3"]
        ],
        'subject': [
            ['countryName', 'US'],
            ['organizationName', 'Example Corp'],
            ['commonName', 'test.example.com']
        ],
        'subjectAltName': [
            ['DNS', 'test.example.com'],
            ['DNS', 'www.test.example.com']
        ],
        'serialNumber': '1234567890ABCDEF',
        'version': 3
    }


def create_test_ssl_context(verify_mode=ssl.CERT_REQUIRED):
    """Create test SSL context with specified verification mode."""
    context = ssl.create_default_context()
    context.verify_mode = verify_mode
    return context


def validate_security_headers(headers):
    """Validate that required security headers are present."""
    required_headers = [
        'X-Content-Type-Options',
        'X-Frame-Options', 
        'X-XSS-Protection',
        'Strict-Transport-Security',
        'Referrer-Policy'
    ]
    
    missing_headers = []
    for header in required_headers:
        if header not in headers:
            missing_headers.append(header)
    
    return len(missing_headers) == 0, missing_headers
