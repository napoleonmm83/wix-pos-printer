"""
Integration tests for public URL setup and monitoring.
Tests end-to-end functionality including API endpoints and health integration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from wix_printer_service.api.main import app
from wix_printer_service.public_url_monitor import PublicUrlStatus, SSLCertificateInfo, PublicUrlHealth


class TestPublicUrlAPIIntegration:
    """Test public URL API endpoints integration."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    @patch('wix_printer_service.api.main.get_public_url_monitor')
    def test_public_url_status_endpoint_configured(self, mock_get_monitor):
        """Test public URL status endpoint when configured."""
        # Mock monitor
        mock_monitor = Mock()
        mock_monitor.is_configured.return_value = True
        mock_monitor.get_health_metrics.return_value = {
            "domain": "test.example.com",
            "status": "online",
            "response_time_ms": 150.0,
            "dns_resolved_ip": "192.168.1.100",
            "last_check": "2025-09-21T19:00:00Z",
            "error_message": None,
            "ssl_certificate": {
                "valid": True,
                "expires_at": "2025-12-31T23:59:59Z",
                "days_until_expiry": 30,
                "issuer": "Let's Encrypt",
                "alerts": []
            }
        }
        mock_monitor.is_healthy.return_value = True
        mock_get_monitor.return_value = mock_monitor
        
        response = self.client.get("/public-url/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["domain"] == "test.example.com"
        assert data["status"] == "online"
        assert data["health_status"] == "healthy"
        assert data["ssl_certificate"]["valid"] is True
    
    @patch('wix_printer_service.api.main.get_public_url_monitor')
    def test_public_url_status_endpoint_not_configured(self, mock_get_monitor):
        """Test public URL status endpoint when not configured."""
        mock_monitor = Mock()
        mock_monitor.is_configured.return_value = False
        mock_get_monitor.return_value = mock_monitor
        
        response = self.client.get("/public-url/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert "not configured" in data["message"]
    
    @patch('wix_printer_service.api.main.get_public_url_monitor')
    def test_public_url_status_endpoint_import_error(self, mock_get_monitor):
        """Test public URL status endpoint with import error."""
        mock_get_monitor.side_effect = ImportError("Module not found")
        
        response = self.client.get("/public-url/status")
        
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]
    
    @patch('wix_printer_service.api.main.get_public_url_monitor')
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_force_public_url_check_success(self, mock_get_print_manager, mock_get_monitor):
        """Test force public URL check endpoint."""
        # Mock monitor
        mock_monitor = Mock()
        mock_monitor.is_configured.return_value = True
        
        # Mock health check result
        mock_health = PublicUrlHealth(
            status=PublicUrlStatus.ONLINE,
            response_time_ms=120.0,
            ssl_info=SSLCertificateInfo(
                valid=True,
                expires_at=datetime.now() + timedelta(days=30),
                days_until_expiry=30,
                issuer="Let's Encrypt",
                subject="test.example.com"
            ),
            dns_resolved_ip="192.168.1.100",
            last_check=datetime.now(),
            error_message=None
        )
        mock_monitor.check_public_url_accessibility.return_value = mock_health
        mock_get_monitor.return_value = mock_monitor
        
        # Mock print manager
        mock_print_manager = Mock()
        mock_health_monitor = Mock()
        mock_print_manager.health_monitor = mock_health_monitor
        mock_get_print_manager.return_value = mock_print_manager
        
        response = self.client.post("/public-url/check")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["check_result"]["status"] == "online"
        assert data["check_result"]["response_time_ms"] == 120.0
        assert data["check_result"]["ssl_valid"] is True
        
        # Verify health monitor was called
        mock_health_monitor.record_public_url_check.assert_called_once_with(True)
        mock_health_monitor.update_ssl_status.assert_called_once_with(30)
    
    @patch('wix_printer_service.api.main.get_public_url_monitor')
    def test_force_public_url_check_not_configured(self, mock_get_monitor):
        """Test force public URL check when not configured."""
        mock_monitor = Mock()
        mock_monitor.is_configured.return_value = False
        mock_get_monitor.return_value = mock_monitor
        
        response = self.client.post("/public-url/check")
        
        assert response.status_code == 400
        assert "not configured" in response.json()["detail"]
    
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_public_url_statistics_endpoint(self, mock_get_print_manager):
        """Test public URL statistics endpoint."""
        # Mock print manager with health monitor
        mock_health_monitor = Mock()
        mock_health_monitor.get_public_url_stats.return_value = {
            "total_checks": 100,
            "successful_checks": 95,
            "failed_checks": 5,
            "last_reset": datetime.now()
        }
        
        mock_print_manager = Mock()
        mock_print_manager.health_monitor = mock_health_monitor
        mock_get_print_manager.return_value = mock_print_manager
        
        # Mock current health metrics
        with patch('wix_printer_service.api.main.get_public_url_monitor') as mock_get_monitor:
            mock_monitor = Mock()
            mock_monitor.is_configured.return_value = True
            mock_monitor.get_health_metrics.return_value = {
                "status": "online",
                "domain": "test.example.com",
                "ssl_certificate": {
                    "valid": True,
                    "days_until_expiry": 30
                }
            }
            mock_get_monitor.return_value = mock_monitor
            
            response = self.client.get("/public-url/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success_rate_percent"] == 95.0
        assert data["failure_rate_percent"] == 5.0
        assert data["health_status"] == "healthy"  # 5% failure rate is healthy
        assert data["current_status"] == "online"
    
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_reset_public_url_statistics_endpoint(self, mock_get_print_manager):
        """Test reset public URL statistics endpoint."""
        mock_health_monitor = Mock()
        mock_print_manager = Mock()
        mock_print_manager.health_monitor = mock_health_monitor
        mock_get_print_manager.return_value = mock_print_manager
        
        response = self.client.post("/public-url/reset-stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "reset_timestamp" in data
        
        # Verify reset was called
        mock_health_monitor.reset_public_url_stats.assert_called_once()
    
    def test_public_url_endpoints_without_health_monitor(self):
        """Test public URL endpoints when health monitor is not available."""
        with patch('wix_printer_service.api.main.get_print_manager') as mock_get_print_manager:
            mock_get_print_manager.return_value = None
            
            # Test statistics endpoint
            response = self.client.get("/public-url/statistics")
            assert response.status_code == 503
            
            # Test reset endpoint
            response = self.client.post("/public-url/reset-stats")
            assert response.status_code == 503
            
            # Test check endpoint
            response = self.client.post("/public-url/check")
            # This should still work but without health monitor integration
            assert response.status_code in [200, 400, 503]


class TestPublicUrlHealthIntegration:
    """Test public URL integration with health monitoring system."""
    
    @patch('wix_printer_service.health_monitor.get_public_url_monitor')
    def test_health_monitor_public_url_integration(self, mock_get_monitor):
        """Test health monitor integration with public URL monitoring."""
        from wix_printer_service.health_monitor import HealthMonitor, ResourceType
        
        # Mock public URL monitor
        mock_monitor = Mock()
        mock_monitor.is_configured.return_value = True
        mock_monitor.get_health_metrics.return_value = {
            "status": "online",
            "domain": "test.example.com",
            "ssl_certificate": {
                "valid": True,
                "days_until_expiry": 30
            }
        }
        mock_get_monitor.return_value = mock_monitor
        
        # Create health monitor
        health_monitor = HealthMonitor()
        
        # Test public URL metric collection
        metric = health_monitor._collect_metric(ResourceType.PUBLIC_URL)
        
        assert metric.resource_type == ResourceType.PUBLIC_URL
        assert metric.value == 0.0  # No failures initially
        assert "domain" in str(metric.metadata)
    
    def test_health_monitor_public_url_stats_tracking(self):
        """Test public URL statistics tracking in health monitor."""
        from wix_printer_service.health_monitor import HealthMonitor
        
        health_monitor = HealthMonitor()
        
        # Test recording successful checks
        health_monitor.record_public_url_check(success=True)
        health_monitor.record_public_url_check(success=True)
        health_monitor.record_public_url_check(success=False)
        
        stats = health_monitor.get_public_url_stats()
        
        assert stats["total_checks"] == 3
        assert stats["successful_checks"] == 2
        assert stats["failed_checks"] == 1
    
    def test_health_monitor_ssl_status_tracking(self):
        """Test SSL status tracking in health monitor."""
        from wix_printer_service.health_monitor import HealthMonitor
        
        health_monitor = HealthMonitor()
        
        # Update SSL status
        health_monitor.update_ssl_status(days_until_expiry=15)
        
        stats = health_monitor.get_public_url_stats()
        
        assert stats["ssl_expiry_days"] == 15
        assert stats["last_ssl_check"] is not None
    
    def test_health_monitor_public_url_reset(self):
        """Test public URL statistics reset in health monitor."""
        from wix_printer_service.health_monitor import HealthMonitor
        
        health_monitor = HealthMonitor()
        
        # Add some statistics
        health_monitor.record_public_url_check(success=True)
        health_monitor.record_public_url_check(success=False)
        
        # Reset statistics
        health_monitor.reset_public_url_stats()
        
        stats = health_monitor.get_public_url_stats()
        
        assert stats["total_checks"] == 0
        assert stats["successful_checks"] == 0
        assert stats["failed_checks"] == 0


class TestPublicUrlEndToEndWorkflow:
    """Test end-to-end public URL workflow."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    @patch.dict('os.environ', {'PUBLIC_DOMAIN': 'test.example.com'})
    @patch('requests.get')
    @patch('socket.gethostbyname')
    @patch('socket.create_connection')
    @patch('ssl.create_default_context')
    def test_complete_public_url_workflow(self, mock_ssl_context, mock_connection, 
                                        mock_gethostbyname, mock_requests):
        """Test complete public URL monitoring workflow."""
        # Mock DNS resolution
        mock_gethostbyname.return_value = '192.168.1.100'
        
        # Mock SSL certificate
        mock_cert = {
            'notAfter': 'Dec 31 23:59:59 2025 GMT',
            'issuer': [['organizationName', 'Let\'s Encrypt']],
            'subject': [['commonName', 'test.example.com']]
        }
        mock_ssl_socket = MagicMock()
        mock_ssl_socket.getpeercert.return_value = mock_cert
        
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssl_socket
        
        mock_socket = MagicMock()
        mock_connection.return_value.__enter__.return_value = mock_socket
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.return_value = mock_response
        
        # Test status endpoint
        response = self.client.get("/public-url/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["configured"] is True
        assert data["domain"] == "test.example.com"
        assert data["health_status"] == "healthy"
    
    def test_public_url_workflow_not_configured(self):
        """Test public URL workflow when not configured."""
        with patch.dict('os.environ', {}, clear=True):
            # Test status endpoint
            response = self.client.get("/public-url/status")
            assert response.status_code == 200
            
            data = response.json()
            assert data["configured"] is False
            
            # Test check endpoint (should fail)
            response = self.client.post("/public-url/check")
            assert response.status_code == 400
    
    @patch('wix_printer_service.api.main.get_print_manager')
    def test_public_url_statistics_workflow(self, mock_get_print_manager):
        """Test public URL statistics workflow."""
        # Mock print manager
        mock_health_monitor = Mock()
        mock_health_monitor.get_public_url_stats.return_value = {
            "total_checks": 50,
            "successful_checks": 48,
            "failed_checks": 2,
            "last_reset": datetime.now()
        }
        
        mock_print_manager = Mock()
        mock_print_manager.health_monitor = mock_health_monitor
        mock_get_print_manager.return_value = mock_print_manager
        
        # Get statistics
        response = self.client.get("/public-url/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success_rate_percent"] == 96.0
        assert data["failure_rate_percent"] == 4.0
        assert data["health_status"] == "healthy"
        
        # Reset statistics
        response = self.client.post("/public-url/reset-stats")
        assert response.status_code == 200
        
        # Verify reset was called
        mock_health_monitor.reset_public_url_stats.assert_called_once()


# Utility functions for integration tests
def create_mock_public_url_health(status: PublicUrlStatus, ssl_days: int = 30) -> PublicUrlHealth:
    """Create mock public URL health for testing."""
    return PublicUrlHealth(
        status=status,
        response_time_ms=100.0 if status == PublicUrlStatus.ONLINE else None,
        ssl_info=SSLCertificateInfo(
            valid=True,
            expires_at=datetime.now() + timedelta(days=ssl_days),
            days_until_expiry=ssl_days,
            issuer="Let's Encrypt",
            subject="test.example.com"
        ) if status == PublicUrlStatus.ONLINE else None,
        dns_resolved_ip="192.168.1.100" if status != PublicUrlStatus.DNS_ERROR else None,
        last_check=datetime.now(),
        error_message=None if status == PublicUrlStatus.ONLINE else "Test error"
    )


def assert_public_url_response_valid(response_data: dict):
    """Assert that public URL response has required fields."""
    required_fields = ["configured"]
    for field in required_fields:
        assert field in response_data, f"Missing required field: {field}"
    
    if response_data["configured"]:
        configured_fields = ["domain", "status", "health_status"]
        for field in configured_fields:
            assert field in response_data, f"Missing configured field: {field}"
