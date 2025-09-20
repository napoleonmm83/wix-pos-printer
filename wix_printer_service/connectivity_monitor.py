"""
Connectivity Monitor for tracking printer and internet connectivity status.
Provides real-time monitoring and event notifications for offline scenarios.
"""
import asyncio
import logging
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ConnectivityStatus(Enum):
    """Connectivity status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ConnectivityEventType(Enum):
    """Connectivity event types."""
    PRINTER_ONLINE = "printer_online"
    PRINTER_OFFLINE = "printer_offline"
    INTERNET_ONLINE = "internet_online"
    INTERNET_OFFLINE = "internet_offline"
    CONNECTIVITY_RESTORED = "connectivity_restored"
    CONNECTIVITY_LOST = "connectivity_lost"


@dataclass
class ConnectivityEvent:
    """Represents a connectivity event."""
    event_type: ConnectivityEventType
    timestamp: datetime
    component: str
    status: ConnectivityStatus
    details: Optional[Dict[str, Any]] = None
    duration_offline: Optional[timedelta] = None


class ConnectivityMonitor:
    """
    Monitor for tracking printer and internet connectivity.
    Provides real-time status updates and event notifications.
    """
    
    def __init__(self, printer_client=None):
        """
        Initialize the connectivity monitor.
        
        Args:
            printer_client: Optional printer client for status checking
        """
        self.printer_client = printer_client
        self._running = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        
        # Status tracking
        self._printer_status = ConnectivityStatus.UNKNOWN
        self._internet_status = ConnectivityStatus.UNKNOWN
        self._last_printer_online = None
        self._last_internet_online = None
        
        # Event callbacks
        self._event_callbacks: List[Callable[[ConnectivityEvent], None]] = []
        
        # Configuration
        self.check_interval = 30  # seconds between checks
        self.printer_timeout = 5  # seconds for printer checks
        self.internet_timeout = 3  # seconds for internet checks
        self.internet_hosts = [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "208.67.222.222"  # OpenDNS
        ]
        
        logger.info("Connectivity Monitor initialized")
    
    def start(self):
        """Start the connectivity monitoring."""
        if self._running:
            logger.warning("Connectivity Monitor is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Connectivity Monitor started")
    
    def stop(self):
        """Stop the connectivity monitoring."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10)
        
        logger.info("Connectivity Monitor stopped")
    
    def add_event_callback(self, callback: Callable[[ConnectivityEvent], None]):
        """
        Add a callback function for connectivity events.
        
        Args:
            callback: Function to call when connectivity events occur
        """
        self._event_callbacks.append(callback)
        logger.debug(f"Added connectivity event callback: {callback.__name__}")
    
    def remove_event_callback(self, callback: Callable[[ConnectivityEvent], None]):
        """
        Remove a callback function.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
            logger.debug(f"Removed connectivity event callback: {callback.__name__}")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Connectivity monitoring loop started")
        
        while self._running and not self._stop_event.is_set():
            try:
                self._check_connectivity()
            except Exception as e:
                logger.error(f"Error in connectivity monitoring loop: {e}")
            
            # Wait for next iteration or stop signal
            self._stop_event.wait(timeout=self.check_interval)
        
        logger.info("Connectivity monitoring loop stopped")
    
    def _check_connectivity(self):
        """Check all connectivity components."""
        # Check printer connectivity
        self._check_printer_connectivity()
        
        # Check internet connectivity
        self._check_internet_connectivity()
    
    def _check_printer_connectivity(self):
        """Check printer connectivity status."""
        try:
            if not self.printer_client:
                # No printer client available, assume offline
                new_status = ConnectivityStatus.OFFLINE
            else:
                # Use printer client to check status
                printer_status = self.printer_client.get_status()
                
                if hasattr(self.printer_client, 'is_connected') and self.printer_client.is_connected:
                    if printer_status.value in ['online']:
                        new_status = ConnectivityStatus.ONLINE
                    elif printer_status.value in ['error', 'paper_out']:
                        new_status = ConnectivityStatus.DEGRADED
                    else:
                        new_status = ConnectivityStatus.OFFLINE
                else:
                    new_status = ConnectivityStatus.OFFLINE
            
            # Check for status change
            if new_status != self._printer_status:
                self._handle_printer_status_change(new_status)
            
            # Update last online timestamp
            if new_status == ConnectivityStatus.ONLINE:
                self._last_printer_online = datetime.now()
                
        except Exception as e:
            logger.error(f"Error checking printer connectivity: {e}")
            if self._printer_status != ConnectivityStatus.OFFLINE:
                self._handle_printer_status_change(ConnectivityStatus.OFFLINE)
    
    def _check_internet_connectivity(self):
        """Check internet connectivity status."""
        try:
            online_hosts = 0
            total_hosts = len(self.internet_hosts)
            
            for host in self.internet_hosts:
                if self._ping_host(host):
                    online_hosts += 1
            
            # Determine status based on reachable hosts
            if online_hosts == total_hosts:
                new_status = ConnectivityStatus.ONLINE
            elif online_hosts > 0:
                new_status = ConnectivityStatus.DEGRADED
            else:
                new_status = ConnectivityStatus.OFFLINE
            
            # Check for status change
            if new_status != self._internet_status:
                self._handle_internet_status_change(new_status)
            
            # Update last online timestamp
            if new_status in [ConnectivityStatus.ONLINE, ConnectivityStatus.DEGRADED]:
                self._last_internet_online = datetime.now()
                
        except Exception as e:
            logger.error(f"Error checking internet connectivity: {e}")
            if self._internet_status != ConnectivityStatus.OFFLINE:
                self._handle_internet_status_change(ConnectivityStatus.OFFLINE)
    
    def _ping_host(self, host: str) -> bool:
        """
        Ping a host to check connectivity.
        
        Args:
            host: Host to ping
            
        Returns:
            True if host is reachable, False otherwise
        """
        try:
            # Try socket connection first (faster)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.internet_timeout)
            result = sock.connect_ex((host, 53))  # DNS port
            sock.close()
            
            if result == 0:
                return True
            
            # Fallback to ping command
            if hasattr(subprocess, 'run'):
                result = subprocess.run(
                    ['ping', '-n', '1', '-w', str(self.internet_timeout * 1000), host],
                    capture_output=True,
                    timeout=self.internet_timeout + 1
                )
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            logger.debug(f"Failed to ping {host}: {e}")
            return False
    
    def _handle_printer_status_change(self, new_status: ConnectivityStatus):
        """
        Handle printer status change.
        
        Args:
            new_status: New printer status
        """
        old_status = self._printer_status
        self._printer_status = new_status
        
        # Calculate offline duration
        duration_offline = None
        if new_status == ConnectivityStatus.ONLINE and self._last_printer_online:
            duration_offline = datetime.now() - self._last_printer_online
        
        # Determine event type
        if new_status == ConnectivityStatus.ONLINE:
            event_type = ConnectivityEventType.PRINTER_ONLINE
        else:
            event_type = ConnectivityEventType.PRINTER_OFFLINE
        
        # Create and fire event
        event = ConnectivityEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            component="printer",
            status=new_status,
            details={
                "old_status": old_status.value,
                "new_status": new_status.value
            },
            duration_offline=duration_offline
        )
        
        self._fire_event(event)
        
        logger.info(f"Printer status changed: {old_status.value} -> {new_status.value}")
    
    def _handle_internet_status_change(self, new_status: ConnectivityStatus):
        """
        Handle internet status change.
        
        Args:
            new_status: New internet status
        """
        old_status = self._internet_status
        self._internet_status = new_status
        
        # Calculate offline duration
        duration_offline = None
        if new_status in [ConnectivityStatus.ONLINE, ConnectivityStatus.DEGRADED] and self._last_internet_online:
            duration_offline = datetime.now() - self._last_internet_online
        
        # Determine event type
        if new_status in [ConnectivityStatus.ONLINE, ConnectivityStatus.DEGRADED]:
            event_type = ConnectivityEventType.INTERNET_ONLINE
        else:
            event_type = ConnectivityEventType.INTERNET_OFFLINE
        
        # Create and fire event
        event = ConnectivityEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            component="internet",
            status=new_status,
            details={
                "old_status": old_status.value,
                "new_status": new_status.value
            },
            duration_offline=duration_offline
        )
        
        self._fire_event(event)
        
        logger.info(f"Internet status changed: {old_status.value} -> {new_status.value}")
    
    def _fire_event(self, event: ConnectivityEvent):
        """
        Fire a connectivity event to all registered callbacks.
        
        Args:
            event: Connectivity event to fire
        """
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in connectivity event callback {callback.__name__}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current connectivity status.
        
        Returns:
            Dictionary with current status information
        """
        now = datetime.now()
        
        return {
            "printer": {
                "status": self._printer_status.value,
                "last_online": self._last_printer_online.isoformat() if self._last_printer_online else None,
                "offline_duration": str(now - self._last_printer_online) if self._last_printer_online and self._printer_status == ConnectivityStatus.OFFLINE else None
            },
            "internet": {
                "status": self._internet_status.value,
                "last_online": self._last_internet_online.isoformat() if self._last_internet_online else None,
                "offline_duration": str(now - self._last_internet_online) if self._last_internet_online and self._internet_status == ConnectivityStatus.OFFLINE else None
            },
            "overall": {
                "status": self._get_overall_status().value,
                "monitoring": self._running
            }
        }
    
    def _get_overall_status(self) -> ConnectivityStatus:
        """Get overall connectivity status."""
        if self._printer_status == ConnectivityStatus.ONLINE and self._internet_status in [ConnectivityStatus.ONLINE, ConnectivityStatus.DEGRADED]:
            return ConnectivityStatus.ONLINE
        elif self._printer_status == ConnectivityStatus.OFFLINE and self._internet_status == ConnectivityStatus.OFFLINE:
            return ConnectivityStatus.OFFLINE
        else:
            return ConnectivityStatus.DEGRADED
    
    def is_printer_online(self) -> bool:
        """Check if printer is online."""
        return self._printer_status == ConnectivityStatus.ONLINE
    
    def is_internet_online(self) -> bool:
        """Check if internet is online or degraded."""
        return self._internet_status in [ConnectivityStatus.ONLINE, ConnectivityStatus.DEGRADED]
    
    def is_fully_online(self) -> bool:
        """Check if both printer and internet are online."""
        return self.is_printer_online() and self.is_internet_online()
    
    def force_check(self):
        """Force an immediate connectivity check."""
        if self._running:
            self._check_connectivity()
        else:
            logger.warning("Cannot force check - monitor is not running")
