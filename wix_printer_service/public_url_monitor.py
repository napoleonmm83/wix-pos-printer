"""
Public URL monitoring integration for Wix Printer Service.
Monitors external accessibility, SSL certificate status, and DNS resolution.
"""
import os
import ssl
import socket
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PublicUrlStatus(Enum):
    """Public URL status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    SSL_ERROR = "ssl_error"
    DNS_ERROR = "dns_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class SSLCertificateInfo:
    """SSL certificate information."""
    valid: bool
    expires_at: Optional[datetime]
    days_until_expiry: Optional[int]
    issuer: Optional[str]
    subject: Optional[str]
    error: Optional[str] = None


@dataclass
class PublicUrlHealth:
    """Public URL health status."""
    status: PublicUrlStatus
    response_time_ms: Optional[float]
    ssl_info: Optional[SSLCertificateInfo]
    dns_resolved_ip: Optional[str]
    last_check: datetime
    error_message: Optional[str] = None


class PublicUrlMonitor:
    """
    Monitors public URL accessibility, SSL certificates, and DNS resolution.
    Integrates with existing health monitoring system.
    """
    
    def __init__(self):
        """Initialize public URL monitor."""
        self.domain = os.getenv('PUBLIC_DOMAIN')
        self.public_url = f"https://{self.domain}" if self.domain else None
        self.health_endpoint = f"{self.public_url}/health" if self.public_url else None
        self.timeout = int(os.getenv('PUBLIC_URL_TIMEOUT', '10'))
        self.check_interval = int(os.getenv('PUBLIC_URL_CHECK_INTERVAL', '300'))  # 5 minutes
        
        if not self.domain:
            logger.warning("PUBLIC_DOMAIN not configured - public URL monitoring disabled")
    
    def is_configured(self) -> bool:
        """Check if public URL monitoring is configured."""
        return self.domain is not None and self.public_url is not None
    
    def check_dns_resolution(self) -> Optional[str]:
        """
        Check DNS resolution for the domain.
        
        Returns:
            str: Resolved IP address or None if resolution fails
        """
        if not self.domain:
            return None
        
        try:
            resolved_ip = socket.gethostbyname(self.domain)
            logger.debug(f"DNS resolution for {self.domain}: {resolved_ip}")
            return resolved_ip
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed for {self.domain}: {e}")
            return None
    
    def check_ssl_certificate(self) -> SSLCertificateInfo:
        """
        Check SSL certificate status and expiration.
        
        Returns:
            SSLCertificateInfo: SSL certificate information
        """
        if not self.domain:
            return SSLCertificateInfo(
                valid=False,
                expires_at=None,
                days_until_expiry=None,
                issuer=None,
                subject=None,
                error="Domain not configured"
            )
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and get certificate
            with socket.create_connection((self.domain, 443), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Parse certificate information
                    not_after = cert.get('notAfter')
                    expires_at = None
                    days_until_expiry = None
                    
                    if not_after:
                        expires_at = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        days_until_expiry = (expires_at - datetime.now()).days
                    
                    issuer = dict(x[0] for x in cert.get('issuer', []))
                    subject = dict(x[0] for x in cert.get('subject', []))
                    
                    return SSLCertificateInfo(
                        valid=True,
                        expires_at=expires_at,
                        days_until_expiry=days_until_expiry,
                        issuer=issuer.get('organizationName', 'Unknown'),
                        subject=subject.get('commonName', 'Unknown')
                    )
                    
        except ssl.SSLError as e:
            logger.error(f"SSL certificate error for {self.domain}: {e}")
            return SSLCertificateInfo(
                valid=False,
                expires_at=None,
                days_until_expiry=None,
                issuer=None,
                subject=None,
                error=f"SSL Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Certificate check failed for {self.domain}: {e}")
            return SSLCertificateInfo(
                valid=False,
                expires_at=None,
                days_until_expiry=None,
                issuer=None,
                subject=None,
                error=f"Connection Error: {str(e)}"
            )
    
    def check_public_url_accessibility(self) -> PublicUrlHealth:
        """
        Check public URL accessibility and health.
        
        Returns:
            PublicUrlHealth: Complete health status
        """
        if not self.is_configured():
            return PublicUrlHealth(
                status=PublicUrlStatus.UNKNOWN,
                response_time_ms=None,
                ssl_info=None,
                dns_resolved_ip=None,
                last_check=datetime.now(),
                error_message="Public URL monitoring not configured"
            )
        
        start_time = datetime.now()
        
        # Check DNS resolution
        dns_ip = self.check_dns_resolution()
        if not dns_ip:
            return PublicUrlHealth(
                status=PublicUrlStatus.DNS_ERROR,
                response_time_ms=None,
                ssl_info=None,
                dns_resolved_ip=None,
                last_check=start_time,
                error_message=f"DNS resolution failed for {self.domain}"
            )
        
        # Check SSL certificate
        ssl_info = self.check_ssl_certificate()
        
        # Check HTTP accessibility
        try:
            response = requests.get(
                self.health_endpoint,
                timeout=self.timeout,
                verify=True,  # Verify SSL certificate
                headers={'User-Agent': 'WixPrinterService/1.0 PublicUrlMonitor'}
            )
            
            end_time = datetime.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                status = PublicUrlStatus.ONLINE
                error_message = None
            else:
                status = PublicUrlStatus.OFFLINE
                error_message = f"HTTP {response.status_code}: {response.reason}"
            
            return PublicUrlHealth(
                status=status,
                response_time_ms=response_time_ms,
                ssl_info=ssl_info,
                dns_resolved_ip=dns_ip,
                last_check=start_time,
                error_message=error_message
            )
            
        except requests.exceptions.SSLError as e:
            return PublicUrlHealth(
                status=PublicUrlStatus.SSL_ERROR,
                response_time_ms=None,
                ssl_info=ssl_info,
                dns_resolved_ip=dns_ip,
                last_check=start_time,
                error_message=f"SSL Error: {str(e)}"
            )
        except requests.exceptions.Timeout:
            return PublicUrlHealth(
                status=PublicUrlStatus.TIMEOUT,
                response_time_ms=None,
                ssl_info=ssl_info,
                dns_resolved_ip=dns_ip,
                last_check=start_time,
                error_message=f"Request timeout after {self.timeout}s"
            )
        except requests.exceptions.RequestException as e:
            return PublicUrlHealth(
                status=PublicUrlStatus.OFFLINE,
                response_time_ms=None,
                ssl_info=ssl_info,
                dns_resolved_ip=dns_ip,
                last_check=start_time,
                error_message=f"Request failed: {str(e)}"
            )
    
    def get_ssl_certificate_alerts(self, ssl_info: SSLCertificateInfo) -> list:
        """
        Get SSL certificate alerts based on expiration.
        
        Args:
            ssl_info: SSL certificate information
            
        Returns:
            list: List of alert messages
        """
        alerts = []
        
        if not ssl_info.valid:
            alerts.append({
                "level": "critical",
                "message": f"SSL certificate is invalid: {ssl_info.error}"
            })
        elif ssl_info.days_until_expiry is not None:
            if ssl_info.days_until_expiry <= 7:
                alerts.append({
                    "level": "critical",
                    "message": f"SSL certificate expires in {ssl_info.days_until_expiry} days"
                })
            elif ssl_info.days_until_expiry <= 30:
                alerts.append({
                    "level": "warning",
                    "message": f"SSL certificate expires in {ssl_info.days_until_expiry} days"
                })
        
        return alerts
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """
        Get public URL health metrics for integration with health monitoring.
        
        Returns:
            dict: Health metrics compatible with existing health system
        """
        if not self.is_configured():
            return {
                "public_url_configured": False,
                "status": "not_configured"
            }
        
        health = self.check_public_url_accessibility()
        ssl_alerts = self.get_ssl_certificate_alerts(health.ssl_info) if health.ssl_info else []
        
        metrics = {
            "public_url_configured": True,
            "domain": self.domain,
            "status": health.status.value,
            "response_time_ms": health.response_time_ms,
            "dns_resolved_ip": health.dns_resolved_ip,
            "last_check": health.last_check.isoformat(),
            "error_message": health.error_message,
            "ssl_certificate": {
                "valid": health.ssl_info.valid if health.ssl_info else False,
                "expires_at": health.ssl_info.expires_at.isoformat() if health.ssl_info and health.ssl_info.expires_at else None,
                "days_until_expiry": health.ssl_info.days_until_expiry if health.ssl_info else None,
                "issuer": health.ssl_info.issuer if health.ssl_info else None,
                "alerts": ssl_alerts
            }
        }
        
        return metrics
    
    def is_healthy(self) -> bool:
        """
        Check if public URL is healthy.
        
        Returns:
            bool: True if public URL is accessible and healthy
        """
        if not self.is_configured():
            return True  # Not configured is not an error
        
        health = self.check_public_url_accessibility()
        return health.status == PublicUrlStatus.ONLINE
    
    def get_failure_rate(self, window_minutes: int = 60) -> float:
        """
        Get failure rate for the specified time window.
        Note: This is a placeholder - actual implementation would require
        storing check history in database.
        
        Args:
            window_minutes: Time window in minutes
            
        Returns:
            float: Failure rate as percentage (0-100)
        """
        # TODO: Implement actual failure rate calculation with database storage
        # For now, return 0 if healthy, 100 if not
        return 0.0 if self.is_healthy() else 100.0


# Global monitor instance
_public_url_monitor = None


def get_public_url_monitor() -> PublicUrlMonitor:
    """Get global public URL monitor instance."""
    global _public_url_monitor
    if _public_url_monitor is None:
        _public_url_monitor = PublicUrlMonitor()
    return _public_url_monitor
