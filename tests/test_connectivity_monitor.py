"""
Unit tests for connectivity monitor.
Tests connectivity monitoring, event handling, and status tracking.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from wix_printer_service.connectivity_monitor import (
    ConnectivityMonitor, ConnectivityStatus, ConnectivityEventType, ConnectivityEvent
)
from wix_printer_service.printer_client import PrinterStatus


class TestConnectivityMonitor:
    """Test cases for the ConnectivityMonitor class."""
    
    @pytest.fixture
    def mock_printer_client(self):
        """Create a mock printer client."""
        mock_client = Mock()
        mock_client.get_status.return_value = PrinterStatus.ONLINE
        mock_client.is_connected = True
        return mock_client
    
    @pytest.fixture
    def connectivity_monitor(self, mock_printer_client):
        """Create a connectivity monitor instance."""
        monitor = ConnectivityMonitor(mock_printer_client)
        monitor.check_interval = 0.1  # Fast checking for tests
        return monitor
    
    def test_init(self, mock_printer_client):
        """Test connectivity monitor initialization."""
        monitor = ConnectivityMonitor(mock_printer_client)
        
        assert monitor.printer_client == mock_printer_client
        assert not monitor._running
        assert monitor._printer_status == ConnectivityStatus.UNKNOWN
        assert monitor._internet_status == ConnectivityStatus.UNKNOWN
        assert monitor.check_interval == 30
        assert len(monitor.internet_hosts) == 3
    
    def test_start_stop(self, connectivity_monitor):
        """Test starting and stopping the monitor."""
        # Test start
        connectivity_monitor.start()
        assert connectivity_monitor._running
        assert connectivity_monitor._monitor_thread is not None
        
        # Test stop
        connectivity_monitor.stop()
        assert not connectivity_monitor._running
    
    def test_start_already_running(self, connectivity_monitor):
        """Test starting monitor when already running."""
        connectivity_monitor.start()
        
        # Try to start again
        connectivity_monitor.start()  # Should not raise error
        assert connectivity_monitor._running
        
        connectivity_monitor.stop()
    
    def test_add_remove_event_callback(self, connectivity_monitor):
        """Test adding and removing event callbacks."""
        def test_callback(event):
            pass
        
        # Add callback
        connectivity_monitor.add_event_callback(test_callback)
        assert test_callback in connectivity_monitor._event_callbacks
        
        # Remove callback
        connectivity_monitor.remove_event_callback(test_callback)
        assert test_callback not in connectivity_monitor._event_callbacks
    
    def test_printer_connectivity_online(self, connectivity_monitor, mock_printer_client):
        """Test printer connectivity check when online."""
        mock_printer_client.get_status.return_value = PrinterStatus.ONLINE
        mock_printer_client.is_connected = True
        
        connectivity_monitor._check_printer_connectivity()
        
        assert connectivity_monitor._printer_status == ConnectivityStatus.ONLINE
        assert connectivity_monitor._last_printer_online is not None
    
    def test_printer_connectivity_offline(self, connectivity_monitor, mock_printer_client):
        """Test printer connectivity check when offline."""
        mock_printer_client.get_status.return_value = PrinterStatus.OFFLINE
        mock_printer_client.is_connected = False
        
        connectivity_monitor._check_printer_connectivity()
        
        assert connectivity_monitor._printer_status == ConnectivityStatus.OFFLINE
    
    def test_printer_connectivity_degraded(self, connectivity_monitor, mock_printer_client):
        """Test printer connectivity check when degraded."""
        mock_printer_client.get_status.return_value = PrinterStatus.PAPER_OUT
        mock_printer_client.is_connected = True
        
        connectivity_monitor._check_printer_connectivity()
        
        assert connectivity_monitor._printer_status == ConnectivityStatus.DEGRADED
    
    def test_printer_connectivity_no_client(self):
        """Test printer connectivity check without printer client."""
        monitor = ConnectivityMonitor(None)
        
        monitor._check_printer_connectivity()
        
        assert monitor._printer_status == ConnectivityStatus.OFFLINE
    
    def test_printer_connectivity_exception(self, connectivity_monitor, mock_printer_client):
        """Test printer connectivity check with exception."""
        mock_printer_client.get_status.side_effect = Exception("Connection error")
        
        connectivity_monitor._check_printer_connectivity()
        
        assert connectivity_monitor._printer_status == ConnectivityStatus.OFFLINE
    
    @patch('wix_printer_service.connectivity_monitor.socket.socket')
    def test_ping_host_success(self, mock_socket, connectivity_monitor):
        """Test successful host ping."""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        result = connectivity_monitor._ping_host("8.8.8.8")
        
        assert result is True
        mock_sock.close.assert_called_once()
    
    @patch('wix_printer_service.connectivity_monitor.socket.socket')
    def test_ping_host_failure(self, mock_socket, connectivity_monitor):
        """Test failed host ping."""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # Connection failed
        mock_socket.return_value = mock_sock
        
        result = connectivity_monitor._ping_host("8.8.8.8")
        
        assert result is False
        mock_sock.close.assert_called_once()
    
    @patch('wix_printer_service.connectivity_monitor.socket.socket')
    def test_ping_host_exception(self, mock_socket, connectivity_monitor):
        """Test host ping with exception."""
        mock_socket.side_effect = Exception("Network error")
        
        result = connectivity_monitor._ping_host("8.8.8.8")
        
        assert result is False
    
    @patch.object(ConnectivityMonitor, '_ping_host')
    def test_internet_connectivity_online(self, mock_ping, connectivity_monitor):
        """Test internet connectivity check when online."""
        mock_ping.return_value = True
        
        connectivity_monitor._check_internet_connectivity()
        
        assert connectivity_monitor._internet_status == ConnectivityStatus.ONLINE
        assert connectivity_monitor._last_internet_online is not None
    
    @patch.object(ConnectivityMonitor, '_ping_host')
    def test_internet_connectivity_offline(self, mock_ping, connectivity_monitor):
        """Test internet connectivity check when offline."""
        mock_ping.return_value = False
        
        connectivity_monitor._check_internet_connectivity()
        
        assert connectivity_monitor._internet_status == ConnectivityStatus.OFFLINE
    
    @patch.object(ConnectivityMonitor, '_ping_host')
    def test_internet_connectivity_degraded(self, mock_ping, connectivity_monitor):
        """Test internet connectivity check when degraded."""
        # Some hosts reachable, some not
        mock_ping.side_effect = [True, False, False]
        
        connectivity_monitor._check_internet_connectivity()
        
        assert connectivity_monitor._internet_status == ConnectivityStatus.DEGRADED
    
    def test_handle_printer_status_change(self, connectivity_monitor):
        """Test handling printer status changes."""
        callback = Mock()
        connectivity_monitor.add_event_callback(callback)
        
        # Simulate status change
        connectivity_monitor._handle_printer_status_change(ConnectivityStatus.ONLINE)
        
        assert connectivity_monitor._printer_status == ConnectivityStatus.ONLINE
        callback.assert_called_once()
        
        # Check event details
        event = callback.call_args[0][0]
        assert isinstance(event, ConnectivityEvent)
        assert event.event_type == ConnectivityEventType.PRINTER_ONLINE
        assert event.component == "printer"
        assert event.status == ConnectivityStatus.ONLINE
    
    def test_handle_internet_status_change(self, connectivity_monitor):
        """Test handling internet status changes."""
        callback = Mock()
        connectivity_monitor.add_event_callback(callback)
        
        # Simulate status change
        connectivity_monitor._handle_internet_status_change(ConnectivityStatus.ONLINE)
        
        assert connectivity_monitor._internet_status == ConnectivityStatus.ONLINE
        callback.assert_called_once()
        
        # Check event details
        event = callback.call_args[0][0]
        assert isinstance(event, ConnectivityEvent)
        assert event.event_type == ConnectivityEventType.INTERNET_ONLINE
        assert event.component == "internet"
        assert event.status == ConnectivityStatus.ONLINE
    
    def test_fire_event_exception(self, connectivity_monitor):
        """Test event firing with callback exception."""
        def bad_callback(event):
            raise Exception("Callback error")
        
        def good_callback(event):
            pass
        
        good_callback_mock = Mock(side_effect=good_callback)
        
        connectivity_monitor.add_event_callback(bad_callback)
        connectivity_monitor.add_event_callback(good_callback_mock)
        
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.ONLINE
        )
        
        # Should not raise exception
        connectivity_monitor._fire_event(event)
        
        # Good callback should still be called
        good_callback_mock.assert_called_once_with(event)
    
    def test_get_status(self, connectivity_monitor):
        """Test getting connectivity status."""
        # Set some status
        connectivity_monitor._printer_status = ConnectivityStatus.ONLINE
        connectivity_monitor._internet_status = ConnectivityStatus.DEGRADED
        connectivity_monitor._last_printer_online = datetime.now()
        connectivity_monitor._last_internet_online = datetime.now()
        
        status = connectivity_monitor.get_status()
        
        assert status["printer"]["status"] == "online"
        assert status["internet"]["status"] == "degraded"
        assert status["overall"]["status"] == "online"
        assert status["overall"]["monitoring"] is False
    
    def test_get_overall_status_combinations(self, connectivity_monitor):
        """Test overall status with different combinations."""
        # Both online
        connectivity_monitor._printer_status = ConnectivityStatus.ONLINE
        connectivity_monitor._internet_status = ConnectivityStatus.ONLINE
        assert connectivity_monitor._get_overall_status() == ConnectivityStatus.ONLINE
        
        # Printer online, internet degraded
        connectivity_monitor._printer_status = ConnectivityStatus.ONLINE
        connectivity_monitor._internet_status = ConnectivityStatus.DEGRADED
        assert connectivity_monitor._get_overall_status() == ConnectivityStatus.ONLINE
        
        # Both offline
        connectivity_monitor._printer_status = ConnectivityStatus.OFFLINE
        connectivity_monitor._internet_status = ConnectivityStatus.OFFLINE
        assert connectivity_monitor._get_overall_status() == ConnectivityStatus.OFFLINE
        
        # Mixed states
        connectivity_monitor._printer_status = ConnectivityStatus.OFFLINE
        connectivity_monitor._internet_status = ConnectivityStatus.ONLINE
        assert connectivity_monitor._get_overall_status() == ConnectivityStatus.DEGRADED
    
    def test_is_printer_online(self, connectivity_monitor):
        """Test printer online check."""
        connectivity_monitor._printer_status = ConnectivityStatus.ONLINE
        assert connectivity_monitor.is_printer_online() is True
        
        connectivity_monitor._printer_status = ConnectivityStatus.OFFLINE
        assert connectivity_monitor.is_printer_online() is False
    
    def test_is_internet_online(self, connectivity_monitor):
        """Test internet online check."""
        connectivity_monitor._internet_status = ConnectivityStatus.ONLINE
        assert connectivity_monitor.is_internet_online() is True
        
        connectivity_monitor._internet_status = ConnectivityStatus.DEGRADED
        assert connectivity_monitor.is_internet_online() is True
        
        connectivity_monitor._internet_status = ConnectivityStatus.OFFLINE
        assert connectivity_monitor.is_internet_online() is False
    
    def test_is_fully_online(self, connectivity_monitor):
        """Test full online check."""
        connectivity_monitor._printer_status = ConnectivityStatus.ONLINE
        connectivity_monitor._internet_status = ConnectivityStatus.ONLINE
        assert connectivity_monitor.is_fully_online() is True
        
        connectivity_monitor._printer_status = ConnectivityStatus.OFFLINE
        connectivity_monitor._internet_status = ConnectivityStatus.ONLINE
        assert connectivity_monitor.is_fully_online() is False
        
        connectivity_monitor._printer_status = ConnectivityStatus.ONLINE
        connectivity_monitor._internet_status = ConnectivityStatus.OFFLINE
        assert connectivity_monitor.is_fully_online() is False
    
    def test_force_check_running(self, connectivity_monitor):
        """Test force check when monitor is running."""
        connectivity_monitor._running = True
        
        with patch.object(connectivity_monitor, '_check_connectivity') as mock_check:
            connectivity_monitor.force_check()
            mock_check.assert_called_once()
    
    def test_force_check_not_running(self, connectivity_monitor):
        """Test force check when monitor is not running."""
        connectivity_monitor._running = False
        
        with patch.object(connectivity_monitor, '_check_connectivity') as mock_check:
            connectivity_monitor.force_check()
            mock_check.assert_not_called()
    
    def test_monitor_loop_integration(self, connectivity_monitor, mock_printer_client):
        """Test the monitoring loop integration."""
        def test_callback(event):
            pass
        
        connectivity_monitor.add_event_callback(test_callback)
        
        # Mock ping to return success
        with patch.object(connectivity_monitor, '_ping_host', return_value=True):
            connectivity_monitor.start()
            
            # Wait a bit for monitoring to occur
            time.sleep(0.2)
            
            connectivity_monitor.stop()
        
        # Should have detected status changes
        assert connectivity_monitor._printer_status == ConnectivityStatus.ONLINE
        assert connectivity_monitor._internet_status == ConnectivityStatus.ONLINE


class TestConnectivityEvent:
    """Test cases for ConnectivityEvent dataclass."""
    
    def test_connectivity_event_creation(self):
        """Test creating a connectivity event."""
        timestamp = datetime.now()
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=timestamp,
            component="printer",
            status=ConnectivityStatus.ONLINE,
            details={"test": "data"},
            duration_offline=timedelta(minutes=5)
        )
        
        assert event.event_type == ConnectivityEventType.PRINTER_ONLINE
        assert event.timestamp == timestamp
        assert event.component == "printer"
        assert event.status == ConnectivityStatus.ONLINE
        assert event.details == {"test": "data"}
        assert event.duration_offline == timedelta(minutes=5)


class TestConnectivityEnums:
    """Test cases for connectivity enums."""
    
    def test_connectivity_status_enum(self):
        """Test ConnectivityStatus enum values."""
        assert ConnectivityStatus.ONLINE.value == "online"
        assert ConnectivityStatus.OFFLINE.value == "offline"
        assert ConnectivityStatus.DEGRADED.value == "degraded"
        assert ConnectivityStatus.UNKNOWN.value == "unknown"
    
    def test_connectivity_event_type_enum(self):
        """Test ConnectivityEventType enum values."""
        assert ConnectivityEventType.PRINTER_ONLINE.value == "printer_online"
        assert ConnectivityEventType.PRINTER_OFFLINE.value == "printer_offline"
        assert ConnectivityEventType.INTERNET_ONLINE.value == "internet_online"
        assert ConnectivityEventType.INTERNET_OFFLINE.value == "internet_offline"
        assert ConnectivityEventType.CONNECTIVITY_RESTORED.value == "connectivity_restored"
        assert ConnectivityEventType.CONNECTIVITY_LOST.value == "connectivity_lost"
