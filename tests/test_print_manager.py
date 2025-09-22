"""
Unit tests for the print manager.
Tests print job processing, status management, and error handling.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from wix_printer_service.print_manager import PrintManager
from wix_printer_service.models import PrintJob, PrintJobStatus
from wix_printer_service.printer_client import PrinterStatus


class TestPrintManager:
    """Test cases for the PrintManager class."""
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_db.get_connection.return_value = mock_conn
        return mock_db
    
    @pytest.fixture
    def mock_printer_client(self):
        """Create a mock printer client."""
        mock_client = Mock()
        mock_client.is_connected = True
        mock_client.get_status.return_value = PrinterStatus.ONLINE
        mock_client.print_receipt.return_value = True
        mock_client.print_text.return_value = True
        return mock_client
    
    @pytest.fixture
    def print_manager(self, mock_database, mock_printer_client):
        """Create a print manager instance."""
        return PrintManager(mock_database, mock_printer_client)
    
    def test_init(self, mock_database, mock_printer_client):
        """Test print manager initialization."""
        manager = PrintManager(mock_database, mock_printer_client)
        
        assert manager.database == mock_database
        assert manager.printer_client == mock_printer_client
        assert not manager._running
        assert manager.poll_interval == 5
        assert manager.max_retry_attempts == 3
    
    def test_start_stop(self, print_manager):
        """Test starting and stopping the print manager."""
        # Start the manager
        print_manager.start()
        assert print_manager._running is True
        
        # Give it a moment to start
        time.sleep(0.1)
        
        # Stop the manager
        print_manager.stop()
        assert print_manager._running is False
    
    def test_start_already_running(self, print_manager):
        """Test starting when already running."""
        print_manager.start()
        
        # Try to start again
        print_manager.start()  # Should not raise error
        
        print_manager.stop()
    
    def test_ensure_printer_ready_success(self, print_manager, mock_printer_client):
        """Test ensuring printer is ready when it is."""
        mock_printer_client.is_connected = True
        mock_printer_client.get_status.return_value = PrinterStatus.ONLINE
        
        result = print_manager._ensure_printer_ready()
        
        assert result is True
    
    def test_ensure_printer_ready_not_connected(self, print_manager, mock_printer_client):
        """Test ensuring printer is ready when not connected."""
        mock_printer_client.is_connected = False
        mock_printer_client.connect.return_value = True
        mock_printer_client.get_status.return_value = PrinterStatus.ONLINE
        
        result = print_manager._ensure_printer_ready()
        
        assert result is True
        mock_printer_client.connect.assert_called_once()
    
    def test_ensure_printer_ready_connection_failed(self, print_manager, mock_printer_client):
        """Test ensuring printer is ready when connection fails."""
        mock_printer_client.is_connected = False
        mock_printer_client.connect.return_value = False
        
        result = print_manager._ensure_printer_ready()
        
        assert result is False
    
    def test_ensure_printer_ready_offline(self, print_manager, mock_printer_client):
        """Test ensuring printer is ready when printer is offline."""
        mock_printer_client.is_connected = True
        mock_printer_client.get_status.return_value = PrinterStatus.OFFLINE
        
        result = print_manager._ensure_printer_ready()
        
        assert result is False
    
    def test_print_job_content_kitchen(self, print_manager, mock_printer_client):
        """Test printing kitchen job content."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Kitchen receipt content"
        )
        
        result = print_manager._print_job_content(job)
        
        assert result is True
        mock_printer_client.print_receipt.assert_called_once_with(
            "Kitchen receipt content"
        )
    
    def test_print_job_content_customer(self, print_manager, mock_printer_client):
        """Test printing customer job content."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="customer",
            content="Customer receipt content"
        )
        
        result = print_manager._print_job_content(job)
        
        assert result is True
        mock_printer_client.print_receipt.assert_called_once_with(
            "Customer receipt content"
        )
    
    def test_print_job_content_driver(self, print_manager, mock_printer_client):
        """Test printing driver job content."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="driver",
            content="Driver receipt content"
        )
        
        result = print_manager._print_job_content(job)
        
        assert result is True
        mock_printer_client.print_receipt.assert_called_once_with(
            "Driver receipt content"
        )
    
    def test_print_job_content_other_type(self, print_manager, mock_printer_client):
        """Test printing other job type content."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="other",
            content="Other content"
        )
        
        result = print_manager._print_job_content(job)
        
        assert result is True
        mock_printer_client.print_text.assert_called_once_with("Other content")
    
    def test_print_job_content_error(self, print_manager, mock_printer_client):
        """Test printing job content with error."""
        mock_printer_client.print_receipt.return_value = False
        
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Kitchen receipt content"
        )
        
        result = print_manager._print_job_content(job)
        
        assert result is False
    
    def test_handle_job_failure_max_attempts_reached(self, print_manager, mock_database):
        """Test handling job failure when max attempts reached."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Content",
            attempts=3,
            max_attempts=3
        )
        
        print_manager._handle_job_failure(job, "Test error")
        
        assert job.status == PrintJobStatus.FAILED
        assert job.error_message == "Test error"
    
    def test_handle_job_failure_retry_available(self, print_manager, mock_database):
        """Test handling job failure when retries available."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Content",
            attempts=1,
            max_attempts=3
        )
        
        print_manager._handle_job_failure(job, "Test error")
        
        assert job.status == PrintJobStatus.PENDING
        assert job.error_message == "Test error"
    
    def test_process_single_job_success(self, print_manager, mock_database, mock_printer_client):
        """Test processing a single job successfully."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Kitchen content",
            status=PrintJobStatus.PENDING
        )
        
        mock_printer_client.print_receipt.return_value = True
        
        print_manager._process_single_job(job)
        
        assert job.status == PrintJobStatus.COMPLETED
        assert job.printed_at is not None
        assert job.error_message is None
        assert job.attempts == 1
        
        # Verify database save was called
        assert mock_database.save_print_job.call_count == 2  # Once for printing, once for completion
    
    def test_process_single_job_failure(self, print_manager, mock_database, mock_printer_client):
        """Test processing a single job with failure."""
        job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Kitchen content",
            status=PrintJobStatus.PENDING,
            attempts=0,
            max_attempts=3
        )
        
        mock_printer_client.print_receipt.return_value = False
        
        print_manager._process_single_job(job)
        
        assert job.status == PrintJobStatus.PENDING  # Reset for retry
        assert job.attempts == 1
        assert job.error_message is not None
    
    def test_process_pending_jobs_no_jobs(self, print_manager, mock_database):
        """Test processing when no pending jobs exist."""
        mock_database.get_pending_print_jobs.return_value = []
        
        # Should not raise any errors
        print_manager._process_pending_jobs()
        
        mock_database.get_pending_print_jobs.assert_called_once()
    
    def test_process_pending_jobs_printer_not_ready(self, print_manager, mock_database, mock_printer_client):
        """Test processing when printer is not ready."""
        mock_database.get_pending_print_jobs.return_value = [
            PrintJob(id="1", order_id="order_1", job_type="kitchen", content="Content")
        ]
        mock_printer_client.is_connected = False
        mock_printer_client.connect.return_value = False
        
        print_manager._process_pending_jobs()
        
        # Jobs should not be processed
        assert mock_database.save_print_job.call_count == 0
    
    def test_get_job_statistics_success(self, print_manager, mock_database):
        """Test getting job statistics successfully."""
        # Mock database connection and queries
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_database.get_connection.return_value = mock_conn
        
        # Mock query results
        mock_cursor.fetchall.return_value = [('pending', 5), ('completed', 10), ('failed', 2)]
        mock_cursor.fetchone.side_effect = [(17,), (3,)]  # recent_jobs, recent_failures
        
        stats = print_manager.get_job_statistics()
        
        assert stats['total_jobs'] == 17
        assert stats['pending_jobs'] == 5
        assert stats['completed_jobs'] == 10
        assert stats['failed_jobs'] == 2
        assert stats['recent_jobs_24h'] == 17
        assert stats['recent_failures_24h'] == 3
        assert stats['manager_running'] is False
    
    def test_get_job_statistics_error(self, print_manager, mock_database):
        """Test getting job statistics with database error."""
        mock_database.get_connection.side_effect = Exception("Database error")
        
        stats = print_manager.get_job_statistics()
        
        assert 'error' in stats
        assert stats['manager_running'] is False
    
    def test_retry_failed_jobs_success(self, print_manager, mock_database):
        """Test retrying failed jobs successfully."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 3
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_database.get_connection.return_value = mock_conn
        
        count = print_manager.retry_failed_jobs()
        
        assert count == 3
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    def test_retry_failed_jobs_error(self, print_manager, mock_database):
        """Test retrying failed jobs with database error."""
        mock_database.get_connection.side_effect = Exception("Database error")
        
        count = print_manager.retry_failed_jobs()
        
        assert count == 0
    
    def test_process_job_immediately_success(self, print_manager, mock_database, mock_printer_client):
        """Test processing a job immediately."""
        # Mock database query
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = Mock()
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_database.get_connection.return_value = mock_conn
        
        # Mock row to print job conversion
        mock_job = PrintJob(
            id="1",
            order_id="order_1",
            job_type="kitchen",
            content="Content",
            status=PrintJobStatus.PENDING
        )
        mock_database._row_to_print_job.return_value = mock_job
        
        # Mock successful printing
        mock_printer_client.print_receipt.return_value = True
        
        result = print_manager.process_job_immediately("1")
        
        assert result is True
        assert mock_job.status == PrintJobStatus.COMPLETED
    
    def test_process_job_immediately_job_not_found(self, print_manager, mock_database):
        """Test processing a job immediately when job not found."""
        # Mock database query returning no results
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_database.get_connection.return_value = mock_conn
        
        result = print_manager.process_job_immediately("nonexistent")
        
        assert result is False
