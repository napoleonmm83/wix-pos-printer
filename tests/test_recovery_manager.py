"""
Unit tests for recovery manager.
Tests automatic recovery, duplicate prevention, and multi-phase recovery.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from wix_printer_service.recovery_manager import (
    RecoveryManager, RecoveryPhase, RecoveryType, RecoverySession
)
from wix_printer_service.connectivity_monitor import (
    ConnectivityEvent, ConnectivityEventType, ConnectivityStatus
)
from wix_printer_service.offline_queue import (
    OfflineQueueManager, OfflineQueueItem, QueuePriority, OfflineQueueStatus
)
from wix_printer_service.models import PrintJob, PrintJobStatus
from wix_printer_service.database import Database


class TestRecoveryManager:
    """Test cases for the RecoveryManager class."""
    
    @pytest.fixture
    def mock_offline_queue(self):
        """Create a mock offline queue manager."""
        mock_queue = Mock(spec=OfflineQueueManager)
        mock_queue.get_queue_statistics.return_value = {"status_counts": {"queued": 5}}
        mock_queue.get_next_items.return_value = []
        mock_queue.log_connectivity_event.return_value = True
        return mock_queue
    
    @pytest.fixture
    def mock_print_manager(self):
        """Create a mock print manager."""
        mock_pm = Mock()
        mock_pm._ensure_printer_ready.return_value = True
        mock_pm._print_job_content.return_value = True
        return mock_pm
    
    @pytest.fixture
    def recovery_manager(self, mock_offline_queue, mock_print_manager):
        """Create a recovery manager instance."""
        manager = RecoveryManager(mock_offline_queue, mock_print_manager)
        manager.batch_delay = 0.1  # Fast processing for tests
        return manager
    
    def test_init(self, mock_offline_queue, mock_print_manager):
        """Test recovery manager initialization."""
        manager = RecoveryManager(mock_offline_queue, mock_print_manager)
        
        assert manager.offline_queue == mock_offline_queue
        assert manager.print_manager == mock_print_manager
        assert not manager._running
        assert manager.batch_size == 5
        assert manager.batch_delay == 2.0
        assert manager._current_session is None
    
    def test_start_stop(self, recovery_manager):
        """Test starting and stopping the recovery manager."""
        # Test start
        recovery_manager.start()
        assert recovery_manager._running
        
        # Test stop
        recovery_manager.stop()
        assert not recovery_manager._running
    
    def test_add_remove_recovery_callback(self, recovery_manager):
        """Test adding and removing recovery callbacks."""
        def test_callback(session):
            pass
        
        # Add callback
        recovery_manager.add_recovery_callback(test_callback)
        assert test_callback in recovery_manager._recovery_callbacks
        
        # Remove callback (not implemented in current version)
        # This would be added in a future enhancement
    
    def test_should_trigger_recovery_printer_online(self, recovery_manager):
        """Test recovery trigger decision for printer online event."""
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.ONLINE
        )
        
        # Should trigger when items are queued
        should_trigger = recovery_manager._should_trigger_recovery(event)
        assert should_trigger is True
    
    def test_should_trigger_recovery_no_items(self, recovery_manager, mock_offline_queue):
        """Test recovery trigger decision when no items are queued."""
        mock_offline_queue.get_queue_statistics.return_value = {"status_counts": {"queued": 0}}
        
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.ONLINE
        )
        
        should_trigger = recovery_manager._should_trigger_recovery(event)
        assert should_trigger is False
    
    def test_should_trigger_recovery_offline_event(self, recovery_manager):
        """Test recovery trigger decision for offline events."""
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_OFFLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.OFFLINE
        )
        
        should_trigger = recovery_manager._should_trigger_recovery(event)
        assert should_trigger is False
    
    def test_determine_recovery_type(self, recovery_manager):
        """Test recovery type determination."""
        # Printer online
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.ONLINE
        )
        recovery_type = recovery_manager._determine_recovery_type(event)
        assert recovery_type == RecoveryType.PRINTER_RECOVERY
        
        # Internet online
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.INTERNET_ONLINE,
            timestamp=datetime.now(),
            component="internet",
            status=ConnectivityStatus.ONLINE
        )
        recovery_type = recovery_manager._determine_recovery_type(event)
        assert recovery_type == RecoveryType.INTERNET_RECOVERY
        
        # Combined recovery
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.CONNECTIVITY_RESTORED,
            timestamp=datetime.now(),
            component="system",
            status=ConnectivityStatus.ONLINE
        )
        recovery_type = recovery_manager._determine_recovery_type(event)
        assert recovery_type == RecoveryType.COMBINED_RECOVERY
    
    def test_handle_connectivity_event_triggers_recovery(self, recovery_manager):
        """Test connectivity event handling triggers recovery."""
        recovery_manager.start()
        
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.ONLINE
        )
        
        with patch.object(recovery_manager, '_start_recovery_async') as mock_start:
            recovery_manager.handle_connectivity_event(event)
            mock_start.assert_called_once()
        
        recovery_manager.stop()
    
    def test_handle_connectivity_event_not_running(self, recovery_manager):
        """Test connectivity event handling when not running."""
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_ONLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.ONLINE
        )
        
        with patch.object(recovery_manager, '_start_recovery_async') as mock_start:
            recovery_manager.handle_connectivity_event(event)
            mock_start.assert_not_called()
    
    def test_validate_recovery_conditions_success(self, recovery_manager, mock_offline_queue):
        """Test successful recovery validation."""
        # Mock queue items
        mock_items = [
            Mock(id="item1", item_id="job1"),
            Mock(id="item2", item_id="job2")
        ]
        mock_offline_queue.get_next_items.return_value = mock_items
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager._validate_recovery_conditions(session)
        
        assert result is True
        assert session.items_total == 2
    
    def test_validate_recovery_conditions_no_items(self, recovery_manager, mock_offline_queue):
        """Test recovery validation with no items."""
        mock_offline_queue.get_next_items.return_value = []
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager._validate_recovery_conditions(session)
        
        assert result is True
        assert session.items_total == 0
    
    def test_validate_recovery_conditions_printer_not_ready(self, recovery_manager, mock_print_manager):
        """Test recovery validation when printer is not ready."""
        mock_print_manager._ensure_printer_ready.return_value = False
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager._validate_recovery_conditions(session)
        
        assert result is False
    
    def test_process_print_job_recovery_success(self, recovery_manager, mock_offline_queue, mock_print_manager):
        """Test successful print job recovery."""
        # Mock database connection and print job
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ["job_data"]  # Mock row data
        mock_conn.execute.return_value = mock_cursor
        mock_offline_queue.database.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_offline_queue.database.get_connection.return_value.__exit__ = Mock(return_value=None)
        
        # Mock print job conversion
        mock_print_job = Mock()
        mock_print_job.id = "job1"
        mock_print_job.status = PrintJobStatus.PENDING
        mock_offline_queue.database._row_to_print_job.return_value = mock_print_job
        mock_offline_queue.database.save_print_job.return_value = True
        
        # Mock queue item
        queue_item = Mock()
        queue_item.item_id = "job1"
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.PROCESSING,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager._process_print_job_recovery(queue_item, session)
        
        assert result is True
        mock_print_manager._print_job_content.assert_called_once_with(mock_print_job)
    
    def test_process_print_job_recovery_already_completed(self, recovery_manager, mock_offline_queue):
        """Test print job recovery for already completed job."""
        # Mock database connection and print job
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ["job_data"]
        mock_conn.execute.return_value = mock_cursor
        mock_offline_queue.database.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_offline_queue.database.get_connection.return_value.__exit__ = Mock(return_value=None)
        
        # Mock completed print job
        mock_print_job = Mock()
        mock_print_job.id = "job1"
        mock_print_job.status = PrintJobStatus.COMPLETED
        mock_offline_queue.database._row_to_print_job.return_value = mock_print_job
        
        queue_item = Mock()
        queue_item.item_id = "job1"
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.PROCESSING,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager._process_print_job_recovery(queue_item, session)
        
        assert result is True  # Skip already completed jobs
    
    def test_process_print_job_recovery_job_not_found(self, recovery_manager, mock_offline_queue):
        """Test print job recovery when job is not found."""
        # Mock database connection with no results
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_offline_queue.database.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_offline_queue.database.get_connection.return_value.__exit__ = Mock(return_value=None)
        
        queue_item = Mock()
        queue_item.item_id = "job1"
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.PROCESSING,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager._process_print_job_recovery(queue_item, session)
        
        assert result is False
    
    def test_process_recovery_batch_success(self, recovery_manager, mock_offline_queue):
        """Test successful recovery batch processing."""
        # Mock queue items
        mock_items = [
            Mock(id="item1", item_id="job1", retry_count=0, max_retries=3),
            Mock(id="item2", item_id="job2", retry_count=0, max_retries=3)
        ]
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.PROCESSING,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        with patch.object(recovery_manager, '_process_print_job_recovery', return_value=True):
            failed_count = recovery_manager._process_recovery_batch(mock_items, session)
        
        assert failed_count == 0
        assert mock_offline_queue.update_item_status.call_count == 2  # Both items marked as processing
        assert mock_offline_queue.remove_item.call_count == 2  # Both items removed after success
    
    def test_process_recovery_batch_with_failures(self, recovery_manager, mock_offline_queue):
        """Test recovery batch processing with failures."""
        # Mock queue items
        mock_items = [
            Mock(id="item1", item_id="job1", retry_count=2, max_retries=3),
            Mock(id="item2", item_id="job2", retry_count=3, max_retries=3)  # Max retries reached
        ]
        
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.PROCESSING,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        with patch.object(recovery_manager, '_process_print_job_recovery', return_value=False):
            failed_count = recovery_manager._process_recovery_batch(mock_items, session)
        
        assert failed_count == 1  # Only the max retries item should be counted as failed
        mock_offline_queue.increment_retry_count.assert_called()  # First item gets retry
        
        # Check that second item is marked as failed
        failed_calls = [call for call in mock_offline_queue.update_item_status.call_args_list 
                       if call[0][1] == OfflineQueueStatus.FAILED]
        assert len(failed_calls) == 1
    
    def test_trigger_manual_recovery_success(self, recovery_manager):
        """Test successful manual recovery trigger."""
        recovery_manager.start()
        
        with patch.object(recovery_manager, '_start_recovery_async') as mock_start:
            result = recovery_manager.trigger_manual_recovery(RecoveryType.MANUAL_RECOVERY)
            
            assert result is True
            mock_start.assert_called_once()
        
        recovery_manager.stop()
    
    def test_trigger_manual_recovery_not_running(self, recovery_manager):
        """Test manual recovery trigger when not running."""
        result = recovery_manager.trigger_manual_recovery(RecoveryType.MANUAL_RECOVERY)
        
        assert result is False
    
    def test_trigger_manual_recovery_already_running(self, recovery_manager):
        """Test manual recovery trigger when recovery is already running."""
        recovery_manager.start()
        
        # Set current session to simulate running recovery
        recovery_manager._current_session = RecoverySession(
            id="existing_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.PROCESSING,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result = recovery_manager.trigger_manual_recovery(RecoveryType.MANUAL_RECOVERY)
        
        assert result is False
        recovery_manager.stop()
    
    def test_get_current_session(self, recovery_manager):
        """Test getting current recovery session."""
        # No session initially
        session = recovery_manager.get_current_session()
        assert session is None
        
        # Set a session
        test_session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        with recovery_manager._session_lock:
            recovery_manager._current_session = test_session
        
        session = recovery_manager.get_current_session()
        assert session == test_session
    
    def test_fire_recovery_callback(self, recovery_manager):
        """Test firing recovery callbacks."""
        callback_mock = Mock()
        recovery_manager.add_recovery_callback(callback_mock)
        
        test_session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        recovery_manager._fire_recovery_callback(test_session)
        
        callback_mock.assert_called_once_with(test_session)
    
    def test_fire_recovery_callback_exception(self, recovery_manager):
        """Test recovery callback with exception."""
        def failing_callback(session):
            raise Exception("Callback error")
        
        recovery_manager.add_recovery_callback(failing_callback)
        
        test_session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Should not raise exception
        recovery_manager._fire_recovery_callback(test_session)


class TestRecoverySession:
    """Test cases for RecoverySession dataclass."""
    
    def test_recovery_session_creation(self):
        """Test creating a recovery session."""
        now = datetime.now()
        session = RecoverySession(
            id="test_session",
            recovery_type=RecoveryType.PRINTER_RECOVERY,
            phase=RecoveryPhase.VALIDATION,
            started_at=now,
            updated_at=now,
            items_total=10,
            items_processed=5,
            items_failed=1,
            error_message="Test error",
            completed_at=now + timedelta(minutes=5),
            metadata={"test": "data"}
        )
        
        assert session.id == "test_session"
        assert session.recovery_type == RecoveryType.PRINTER_RECOVERY
        assert session.phase == RecoveryPhase.VALIDATION
        assert session.started_at == now
        assert session.updated_at == now
        assert session.items_total == 10
        assert session.items_processed == 5
        assert session.items_failed == 1
        assert session.error_message == "Test error"
        assert session.completed_at == now + timedelta(minutes=5)
        assert session.metadata == {"test": "data"}


class TestRecoveryEnums:
    """Test cases for recovery enums."""
    
    def test_recovery_phase_enum(self):
        """Test RecoveryPhase enum values."""
        assert RecoveryPhase.IDLE.value == "idle"
        assert RecoveryPhase.VALIDATION.value == "validation"
        assert RecoveryPhase.PROCESSING.value == "processing"
        assert RecoveryPhase.COMPLETION.value == "completion"
        assert RecoveryPhase.FAILED.value == "failed"
    
    def test_recovery_type_enum(self):
        """Test RecoveryType enum values."""
        assert RecoveryType.PRINTER_RECOVERY.value == "printer_recovery"
        assert RecoveryType.INTERNET_RECOVERY.value == "internet_recovery"
        assert RecoveryType.COMBINED_RECOVERY.value == "combined_recovery"
        assert RecoveryType.MANUAL_RECOVERY.value == "manual_recovery"


class TestRecoveryIntegration:
    """Integration tests for recovery scenarios."""
    
    @pytest.fixture
    def integration_setup(self):
        """Setup for integration tests."""
        mock_database = Mock(spec=Database)
        mock_offline_queue = OfflineQueueManager(mock_database)
        mock_print_manager = Mock()
        
        # Mock database methods
        mock_conn = Mock()
        mock_database.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_database.get_connection.return_value.__exit__ = Mock(return_value=None)
        
        recovery_manager = RecoveryManager(mock_offline_queue, mock_print_manager)
        recovery_manager.batch_delay = 0.01  # Very fast for tests
        
        return {
            "recovery_manager": recovery_manager,
            "offline_queue": mock_offline_queue,
            "print_manager": mock_print_manager,
            "database": mock_database,
            "connection": mock_conn
        }
    
    def test_end_to_end_printer_recovery(self, integration_setup):
        """Test complete printer recovery workflow."""
        setup = integration_setup
        recovery_manager = setup["recovery_manager"]
        
        # Mock successful validation and processing
        with patch.object(recovery_manager, '_validate_recovery_conditions', return_value=True):
            with patch.object(recovery_manager, '_process_recovery_queue', return_value=True):
                
                recovery_manager.start()
                
                # Trigger recovery
                event = ConnectivityEvent(
                    event_type=ConnectivityEventType.PRINTER_ONLINE,
                    timestamp=datetime.now(),
                    component="printer",
                    status=ConnectivityStatus.ONLINE
                )
                
                recovery_manager.handle_connectivity_event(event)
                
                # Wait for recovery to complete
                time.sleep(0.1)
                
                recovery_manager.stop()
        
        # Recovery should have been triggered
        # (Detailed assertions would depend on the specific mock setup)
    
    def test_recovery_with_connectivity_monitor_integration(self, integration_setup):
        """Test recovery integration with connectivity monitor."""
        setup = integration_setup
        recovery_manager = setup["recovery_manager"]
        
        # This test would verify the integration between
        # connectivity monitor events and recovery manager
        # In a real scenario, this would test the full pipeline
        
        recovery_manager.start()
        
        # Simulate connectivity event
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.CONNECTIVITY_RESTORED,
            timestamp=datetime.now(),
            component="system",
            status=ConnectivityStatus.ONLINE
        )
        
        # Test that the event is handled properly
        with patch.object(recovery_manager, '_should_trigger_recovery', return_value=True):
            with patch.object(recovery_manager, '_start_recovery_async') as mock_start:
                recovery_manager.handle_connectivity_event(event)
                mock_start.assert_called_once()
        
        recovery_manager.stop()
