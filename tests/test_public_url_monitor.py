"""
Unit tests for public URL monitoring functionality.
Tests SSL certificate validation, DNS resolution, and health monitoring.
"""
import pytest
import ssl
import socket
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import requests

from wix_printer_service.public_url_monitor import (
    PublicUrlMonitor, 
    PublicUrlStatus, 
    SSLCertificateInfo, 
    PublicUrlHealth,
    get_public_url_monitor
)


class TestPublicUrlMonitor:
    """Test public URL monitoring functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = PublicUrlMonitor()
        self.test_domain = "test.example.com"
        self.test_url = f"https://{self.test_domain}"
    
    def test_monitor_initialization(self):
        """Test monitor initialization."""
        assert self.monitor is not None
        assert hasattr(self.monitor, 'domain')
        assert hasattr(self.monitor, 'public_url')
        assert hasattr(self.monitor, 'timeout')
    
    @patch.dict('os.environ', {'PUBLIC_DOMAIN': 'test.example.com'})
    def test_monitor_configuration(self):
        """Test monitor configuration with environment variables."""
        monitor = PublicUrlMonitor()
        assert monitor.domain == 'test.example.com'
        assert monitor.public_url == 'https://test.example.com'
        assert monitor.is_configured() is True
    
    def test_monitor_not_configured(self):
        """Test monitor when not configured."""
        with patch.dict('os.environ', {}, clear=True):
            monitor = PublicUrlMonitor()
            assert monitor.domain is None
            assert monitor.public_url is None
            assert monitor.is_configured() is False
    
    @patch('socket.gethostbyname')
    def test_dns_resolution_success(self, mock_gethostbyname):
        """Test successful DNS resolution."""
        mock_gethostbyname.return_value = '192.168.1.100'
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.check_dns_resolution()
            
        assert result == '192.168.1.100'
        mock_gethostbyname.assert_called_once_with(self.test_domain)
    
    @patch('socket.gethostbyname')
    def test_dns_resolution_failure(self, mock_gethostbyname):
        """Test DNS resolution failure."""
        mock_gethostbyname.side_effect = socket.gaierror("Name resolution failed")
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.check_dns_resolution()
            
        assert result is None
    
    def test_dns_resolution_no_domain(self):
        """Test DNS resolution with no domain configured."""
        result = self.monitor.check_dns_resolution()
        assert result is None
    
    @patch('socket.create_connection')
    @patch('ssl.create_default_context')
    def test_ssl_certificate_check_success(self, mock_ssl_context, mock_connection):
        """Test successful SSL certificate check."""
        # Mock SSL certificate data
        mock_cert = {
            'notAfter': 'Dec 31 23:59:59 2025 GMT',
            'issuer': [['organizationName', 'Let\'s Encrypt']],
            'subject': [['commonName', self.test_domain]]
        }
        
        # Mock SSL socket
        mock_ssl_socket = MagicMock()
        mock_ssl_socket.getpeercert.return_value = mock_cert
        
        # Mock context and connection
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssl_socket
        
        mock_socket = MagicMock()
        mock_connection.return_value.__enter__.return_value = mock_socket
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.check_ssl_certificate()
        
        assert result.valid is True
        assert result.issuer == 'Let\'s Encrypt'
        assert result.subject == self.test_domain
        assert result.expires_at is not None
        assert result.days_until_expiry is not None
    
    @patch('socket.create_connection')
    def test_ssl_certificate_check_ssl_error(self, mock_connection):
        """Test SSL certificate check with SSL error."""
        mock_connection.side_effect = ssl.SSLError("Certificate verification failed")
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.check_ssl_certificate()
        
        assert result.valid is False
        assert "SSL Error" in result.error
    
    def test_ssl_certificate_check_no_domain(self):
        """Test SSL certificate check with no domain configured."""
        result = self.monitor.check_ssl_certificate()
        
        assert result.valid is False
        assert result.error == "Domain not configured"
    
    @patch('requests.get')
    @patch.object(PublicUrlMonitor, 'check_dns_resolution')
    @patch.object(PublicUrlMonitor, 'check_ssl_certificate')
    def test_public_url_accessibility_success(self, mock_ssl_check, mock_dns_check, mock_requests):
        """Test successful public URL accessibility check."""
        # Mock DNS resolution
        mock_dns_check.return_value = '192.168.1.100'
        
        # Mock SSL certificate
        mock_ssl_info = SSLCertificateInfo(
            valid=True,
            expires_at=datetime.now() + timedelta(days=30),
            days_until_expiry=30,
            issuer="Let's Encrypt",
            subject=self.test_domain
        )
        mock_ssl_check.return_value = mock_ssl_info
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.return_value = mock_response
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            with patch.object(self.monitor, 'health_endpoint', f'{self.test_url}/health'):
                result = self.monitor.check_public_url_accessibility()
        
        assert result.status == PublicUrlStatus.ONLINE
        assert result.dns_resolved_ip == '192.168.1.100'
        assert result.ssl_info == mock_ssl_info
        assert result.response_time_ms is not None
        assert result.error_message is None
    
    @patch.object(PublicUrlMonitor, 'check_dns_resolution')
    def test_public_url_accessibility_dns_failure(self, mock_dns_check):
        """Test public URL accessibility check with DNS failure."""
        mock_dns_check.return_value = None
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.check_public_url_accessibility()
        
        assert result.status == PublicUrlStatus.DNS_ERROR
        assert result.dns_resolved_ip is None
        assert "DNS resolution failed" in result.error_message
    
    @patch('requests.get')
    @patch.object(PublicUrlMonitor, 'check_dns_resolution')
    @patch.object(PublicUrlMonitor, 'check_ssl_certificate')
    def test_public_url_accessibility_ssl_error(self, mock_ssl_check, mock_dns_check, mock_requests):
        """Test public URL accessibility check with SSL error."""
        mock_dns_check.return_value = '192.168.1.100'
        mock_ssl_check.return_value = Mock()
        mock_requests.side_effect = requests.exceptions.SSLError("SSL verification failed")
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            with patch.object(self.monitor, 'health_endpoint', f'{self.test_url}/health'):
                result = self.monitor.check_public_url_accessibility()
        
        assert result.status == PublicUrlStatus.SSL_ERROR
        assert "SSL Error" in result.error_message
    
    @patch('requests.get')
    @patch.object(PublicUrlMonitor, 'check_dns_resolution')
    @patch.object(PublicUrlMonitor, 'check_ssl_certificate')
    def test_public_url_accessibility_timeout(self, mock_ssl_check, mock_dns_check, mock_requests):
        """Test public URL accessibility check with timeout."""
        mock_dns_check.return_value = '192.168.1.100'
        mock_ssl_check.return_value = Mock()
        mock_requests.side_effect = requests.exceptions.Timeout()
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            with patch.object(self.monitor, 'health_endpoint', f'{self.test_url}/health'):
                result = self.monitor.check_public_url_accessibility()
        
        assert result.status == PublicUrlStatus.TIMEOUT
        assert "timeout" in result.error_message.lower()
    
    def test_public_url_accessibility_not_configured(self):
        """Test public URL accessibility check when not configured."""
        result = self.monitor.check_public_url_accessibility()
        
        assert result.status == PublicUrlStatus.UNKNOWN
        assert "not configured" in result.error_message
    
    def test_ssl_certificate_alerts_critical(self):
        """Test SSL certificate alerts for critical expiration."""
        ssl_info = SSLCertificateInfo(
            valid=True,
            expires_at=datetime.now() + timedelta(days=3),
            days_until_expiry=3,
            issuer="Let's Encrypt",
            subject=self.test_domain
        )
        
        alerts = self.monitor.get_ssl_certificate_alerts(ssl_info)
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "critical"
        assert "expires in 3 days" in alerts[0]["message"]
    
    def test_ssl_certificate_alerts_warning(self):
        """Test SSL certificate alerts for warning expiration."""
        ssl_info = SSLCertificateInfo(
            valid=True,
            expires_at=datetime.now() + timedelta(days=15),
            days_until_expiry=15,
            issuer="Let's Encrypt",
            subject=self.test_domain
        )
        
        alerts = self.monitor.get_ssl_certificate_alerts(ssl_info)
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "warning"
        assert "expires in 15 days" in alerts[0]["message"]
    
    def test_ssl_certificate_alerts_invalid(self):
        """Test SSL certificate alerts for invalid certificate."""
        ssl_info = SSLCertificateInfo(
            valid=False,
            expires_at=None,
            days_until_expiry=None,
            issuer=None,
            subject=None,
            error="Certificate verification failed"
        )
        
        alerts = self.monitor.get_ssl_certificate_alerts(ssl_info)
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "critical"
        assert "invalid" in alerts[0]["message"]
    
    @patch.object(PublicUrlMonitor, 'check_public_url_accessibility')
    def test_get_health_metrics_configured(self, mock_check):
        """Test health metrics when monitor is configured."""
        # Mock health check result
        mock_health = PublicUrlHealth(
            status=PublicUrlStatus.ONLINE,
            response_time_ms=150.0,
            ssl_info=SSLCertificateInfo(
                valid=True,
                expires_at=datetime.now() + timedelta(days=30),
                days_until_expiry=30,
                issuer="Let's Encrypt",
                subject=self.test_domain
            ),
            dns_resolved_ip='192.168.1.100',
            last_check=datetime.now(),
            error_message=None
        )
        mock_check.return_value = mock_health
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            with patch.object(self.monitor, 'public_url', self.test_url):
                metrics = self.monitor.get_health_metrics()
        
        assert metrics["public_url_configured"] is True
        assert metrics["domain"] == self.test_domain
        assert metrics["status"] == "online"
        assert metrics["response_time_ms"] == 150.0
        assert metrics["ssl_certificate"]["valid"] is True
        assert metrics["ssl_certificate"]["days_until_expiry"] == 30
    
    def test_get_health_metrics_not_configured(self):
        """Test health metrics when monitor is not configured."""
        metrics = self.monitor.get_health_metrics()
        
        assert metrics["public_url_configured"] is False
        assert metrics["status"] == "not_configured"
    
    @patch.object(PublicUrlMonitor, 'check_public_url_accessibility')
    def test_is_healthy_success(self, mock_check):
        """Test is_healthy method with successful check."""
        mock_check.return_value = Mock(status=PublicUrlStatus.ONLINE)
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.is_healthy()
        
        assert result is True
    
    @patch.object(PublicUrlMonitor, 'check_public_url_accessibility')
    def test_is_healthy_failure(self, mock_check):
        """Test is_healthy method with failed check."""
        mock_check.return_value = Mock(status=PublicUrlStatus.OFFLINE)
        
        with patch.object(self.monitor, 'domain', self.test_domain):
            result = self.monitor.is_healthy()
        
        assert result is False
    
    def test_is_healthy_not_configured(self):
        """Test is_healthy method when not configured."""
        result = self.monitor.is_healthy()
        assert result is True  # Not configured is not an error
    
    @patch.object(PublicUrlMonitor, 'is_healthy')
    def test_get_failure_rate_healthy(self, mock_is_healthy):
        """Test failure rate calculation when healthy."""
        mock_is_healthy.return_value = True
        
        result = self.monitor.get_failure_rate()
        assert result == 0.0
    
    @patch.object(PublicUrlMonitor, 'is_healthy')
    def test_get_failure_rate_unhealthy(self, mock_is_healthy):
        """Test failure rate calculation when unhealthy."""
        mock_is_healthy.return_value = False
        
        result = self.monitor.get_failure_rate()
        assert result == 100.0


class TestGlobalMonitorInstance:
    """Test global monitor instance management."""
    
    def test_get_public_url_monitor_singleton(self):
        """Test that get_public_url_monitor returns singleton instance."""
        monitor1 = get_public_url_monitor()
        monitor2 = get_public_url_monitor()
        
        assert monitor1 is monitor2
        assert isinstance(monitor1, PublicUrlMonitor)


# Test fixtures and utilities
@pytest.fixture
def mock_ssl_certificate():
    """Fixture for mock SSL certificate."""
    return {
        'notAfter': 'Dec 31 23:59:59 2025 GMT',
        'issuer': [['organizationName', 'Let\'s Encrypt']],
        'subject': [['commonName', 'test.example.com']]
    }


@pytest.fixture
def mock_public_url_health():
    """Fixture for mock public URL health status."""
    return PublicUrlHealth(
        status=PublicUrlStatus.ONLINE,
        response_time_ms=100.0,
        ssl_info=SSLCertificateInfo(
            valid=True,
            expires_at=datetime.now() + timedelta(days=30),
            days_until_expiry=30,
            issuer="Let's Encrypt",
            subject="test.example.com"
        ),
        dns_resolved_ip='192.168.1.100',
        last_check=datetime.now(),
        error_message=None
    )


def create_test_ssl_info(days_until_expiry: int, valid: bool = True) -> SSLCertificateInfo:
    """Create test SSL certificate info."""
    return SSLCertificateInfo(
        valid=valid,
        expires_at=datetime.now() + timedelta(days=days_until_expiry) if valid else None,
        days_until_expiry=days_until_expiry if valid else None,
        issuer="Let's Encrypt" if valid else None,
        subject="test.example.com" if valid else None,
        error=None if valid else "Certificate invalid"
    )
