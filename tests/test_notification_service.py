"""
Unit tests for notification service.
Tests email notifications, throttling, and template rendering.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from wix_printer_service.notification_service import (
    NotificationService, NotificationConfig, NotificationType, 
    NotificationSeverity, NotificationTemplate, NotificationThrottle
)
from wix_printer_service.connectivity_monitor import (
    ConnectivityEvent, ConnectivityEventType, ConnectivityStatus
)


class TestNotificationService:
    """Test cases for the NotificationService class."""
    
    @pytest.fixture
    def notification_config(self):
        """Create a test notification configuration."""
        return NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="testpass",
            smtp_use_tls=True,
            from_email="test@test.com",
            to_emails=["manager@restaurant.com", "owner@restaurant.com"],
            enabled=True
        )
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
        return mock_db
    
    @pytest.fixture
    def notification_service(self, notification_config, mock_database):
        """Create a notification service instance."""
        return NotificationService(notification_config, mock_database)
    
    def test_init(self, notification_config, mock_database):
        """Test notification service initialization."""
        service = NotificationService(notification_config, mock_database)
        
        assert service.config == notification_config
        assert service.database == mock_database
        assert not service._running
        assert len(service._templates) > 0
        assert NotificationType.PRINTER_OFFLINE in service._templates
        assert NotificationType.SYSTEM_ERROR in service._templates
    
    def test_init_disabled_config(self, mock_database):
        """Test initialization with disabled configuration."""
        config = NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="testpass",
            enabled=False
        )
        
        service = NotificationService(config, mock_database)
        assert service.config.enabled is False
    
    @pytest.mark.asyncio
    async def test_start_stop(self, notification_service):
        """Test starting and stopping the notification service."""
        # Test start
        await notification_service.start()
        assert notification_service._running
        assert notification_service._worker_task is not None
        
        # Test stop
        await notification_service.stop()
        assert not notification_service._running
    
    @pytest.mark.asyncio
    async def test_start_disabled_service(self, mock_database):
        """Test starting a disabled notification service."""
        config = NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="testpass",
            enabled=False
        )
        
        service = NotificationService(config, mock_database)
        await service.start()
        
        assert not service._running
    
    def test_template_initialization(self, notification_service):
        """Test notification template initialization."""
        templates = notification_service._templates
        
        # Check that all required templates exist
        required_types = [
            NotificationType.PRINTER_OFFLINE,
            NotificationType.INTERNET_OFFLINE,
            NotificationType.SYSTEM_ERROR,
            NotificationType.RECOVERY_FAILED,
            NotificationType.QUEUE_OVERFLOW
        ]
        
        for notification_type in required_types:
            assert notification_type in templates
            template = templates[notification_type]
            assert isinstance(template, NotificationTemplate)
            assert template.subject_template
            assert template.body_template
            assert template.throttle_minutes > 0
            assert template.max_per_hour > 0
    
    def test_throttling_first_notification(self, notification_service):
        """Test throttling for first notification of a type."""
        notification_type = NotificationType.PRINTER_OFFLINE
        
        # First notification should not be throttled
        is_throttled = notification_service._is_throttled(notification_type)
        assert not is_throttled
        
        # Should create throttle data
        assert notification_type in notification_service._throttle_data
    
    def test_throttling_time_based(self, notification_service):
        """Test time-based throttling."""
        notification_type = NotificationType.PRINTER_OFFLINE
        template = notification_service._templates[notification_type]
        
        # First notification
        assert not notification_service._is_throttled(notification_type)
        notification_service._update_throttle(notification_type)
        
        # Second notification immediately should be throttled
        assert notification_service._is_throttled(notification_type)
        
        # Simulate time passing
        throttle = notification_service._throttle_data[notification_type]
        throttle.last_sent = datetime.now() - timedelta(minutes=template.throttle_minutes + 1)
        
        # Should not be throttled after time passes
        assert not notification_service._is_throttled(notification_type)
    
    def test_throttling_hourly_limit(self, notification_service):
        """Test hourly limit throttling."""
        notification_type = NotificationType.SYSTEM_ERROR
        template = notification_service._templates[notification_type]
        
        # Simulate reaching hourly limit
        throttle = NotificationThrottle(
            notification_type=notification_type,
            last_sent=datetime.now() - timedelta(minutes=template.throttle_minutes + 1),
            count_in_hour=template.max_per_hour,
            count_in_day=template.max_per_hour
        )
        notification_service._throttle_data[notification_type] = throttle
        
        # Should be throttled due to hourly limit
        assert notification_service._is_throttled(notification_type)
        
        # Simulate hour passing
        throttle.last_sent = datetime.now() - timedelta(hours=1, minutes=1)
        
        # Should not be throttled after hour passes
        assert not notification_service._is_throttled(notification_type)
    
    def test_update_throttle(self, notification_service):
        """Test throttle data update."""
        notification_type = NotificationType.PRINTER_OFFLINE
        
        # Initialize throttle
        notification_service._is_throttled(notification_type)
        initial_throttle = notification_service._throttle_data[notification_type]
        initial_count = initial_throttle.count_in_hour
        
        # Update throttle
        notification_service._update_throttle(notification_type)
        
        updated_throttle = notification_service._throttle_data[notification_type]
        assert updated_throttle.count_in_hour == initial_count + 1
        assert updated_throttle.count_in_day == initial_count + 1
        assert updated_throttle.cooldown_until is None
    
    def test_handle_connectivity_event_printer_offline(self, notification_service):
        """Test handling printer offline connectivity event."""
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_OFFLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.OFFLINE,
            details={"error": "Connection timeout"}
        )
        
        with patch.object(notification_service, 'send_notification') as mock_send:
            # Mock asyncio.create_task
            with patch('asyncio.create_task') as mock_create_task:
                notification_service._running = True
                notification_service.handle_connectivity_event(event)
                
                mock_create_task.assert_called_once()
    
    def test_handle_connectivity_event_internet_offline(self, notification_service):
        """Test handling internet offline connectivity event."""
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.INTERNET_OFFLINE,
            timestamp=datetime.now(),
            component="internet",
            status=ConnectivityStatus.OFFLINE
        )
        
        with patch.object(notification_service, 'send_notification') as mock_send:
            with patch('asyncio.create_task') as mock_create_task:
                notification_service._running = True
                notification_service.handle_connectivity_event(event)
                
                mock_create_task.assert_called_once()
    
    def test_handle_connectivity_event_not_running(self, notification_service):
        """Test handling connectivity event when service is not running."""
        event = ConnectivityEvent(
            event_type=ConnectivityEventType.PRINTER_OFFLINE,
            timestamp=datetime.now(),
            component="printer",
            status=ConnectivityStatus.OFFLINE
        )
        
        with patch.object(notification_service, 'send_notification') as mock_send:
            notification_service._running = False
            notification_service.handle_connectivity_event(event)
            
            mock_send.assert_not_called()
    
    def test_handle_connectivity_event_online_events(self, notification_service):
        """Test that online events don't trigger notifications."""
        online_events = [
            ConnectivityEventType.PRINTER_ONLINE,
            ConnectivityEventType.INTERNET_ONLINE,
            ConnectivityEventType.CONNECTIVITY_RESTORED
        ]
        
        for event_type in online_events:
            event = ConnectivityEvent(
                event_type=event_type,
                timestamp=datetime.now(),
                component="test",
                status=ConnectivityStatus.ONLINE
            )
            
            with patch.object(notification_service, 'send_notification') as mock_send:
                notification_service._running = True
                notification_service.handle_connectivity_event(event)
                
                # Online events should not trigger notifications in current implementation
                # (They could be added as info notifications in the future)
    
    @pytest.mark.asyncio
    async def test_send_notification_disabled(self, mock_database):
        """Test sending notification when service is disabled."""
        config = NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="testpass",
            enabled=False
        )
        
        service = NotificationService(config, mock_database)
        
        context = {"test": "data"}
        await service.send_notification(NotificationType.SYSTEM_ERROR, context)
        
        # Should not add to queue when disabled
        assert service._notification_queue.empty()
    
    @pytest.mark.asyncio
    async def test_send_notification_throttled(self, notification_service):
        """Test sending notification when throttled."""
        notification_type = NotificationType.PRINTER_OFFLINE
        
        # Set up throttling
        notification_service._is_throttled(notification_type)
        notification_service._update_throttle(notification_type)
        
        context = {"test": "data"}
        await notification_service.send_notification(notification_type, context)
        
        # Should not add to queue when throttled
        assert notification_service._notification_queue.empty()
        assert notification_service._stats["total_throttled"] == 1
    
    @pytest.mark.asyncio
    async def test_send_system_error_notification(self, notification_service):
        """Test sending system error notification."""
        with patch.dict('os.environ', {'RESTAURANT_NAME': 'Test Restaurant'}):
            with patch.object(notification_service, 'send_notification') as mock_send:
                await notification_service.send_system_error_notification(
                    "Database Error",
                    "Connection failed",
                    {"additional": "context"}
                )
                
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert call_args[0][0] == NotificationType.SYSTEM_ERROR
                
                context = call_args[0][1]
                assert context["error_type"] == "Database Error"
                assert context["error_message"] == "Connection failed"
                assert context["additional"] == "context"
                assert context["restaurant_name"] == "Test Restaurant"
    
    @pytest.mark.asyncio
    async def test_send_recovery_notification_success(self, notification_service):
        """Test sending successful recovery notification."""
        session_data = {
            "session_id": "test_session",
            "items_processed": 10,
            "items_failed": 1,
            "duration": 120
        }
        
        with patch.object(notification_service, 'send_notification') as mock_send:
            await notification_service.send_recovery_notification(
                "printer_recovery",
                True,  # Success
                session_data
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == NotificationType.RECOVERY_COMPLETED
    
    @pytest.mark.asyncio
    async def test_send_recovery_notification_failed(self, notification_service):
        """Test sending failed recovery notification."""
        session_data = {
            "session_id": "test_session",
            "items_processed": 5,
            "items_failed": 3,
            "error_message": "Printer connection lost"
        }
        
        with patch.object(notification_service, 'send_notification') as mock_send:
            await notification_service.send_recovery_notification(
                "printer_recovery",
                False,  # Failed
                session_data
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == NotificationType.RECOVERY_FAILED
            
            context = call_args[0][1]
            assert context["error_message"] == "Printer connection lost"
    
    @pytest.mark.asyncio
    async def test_send_queue_overflow_notification(self, notification_service):
        """Test sending queue overflow notification."""
        queue_stats = {
            "critical_items": 5,
            "high_priority_items": 15,
            "normal_priority_items": 80
        }
        
        with patch.object(notification_service, 'send_notification') as mock_send:
            await notification_service.send_queue_overflow_notification(100, queue_stats)
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == NotificationType.QUEUE_OVERFLOW
            
            context = call_args[0][1]
            assert context["queue_size"] == 100
            assert context["critical_items"] == 5
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, notification_service):
        """Test successful email sending."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=None)
            
            result = await notification_service._send_email(
                "Test Subject",
                "Test Body"
            )
            
            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once()
            mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_email_failure(self, notification_service):
        """Test email sending failure."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP connection failed")
            
            result = await notification_service._send_email(
                "Test Subject",
                "Test Body"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_email_with_html(self, notification_service):
        """Test sending email with HTML body."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=None)
            
            result = await notification_service._send_email(
                "Test Subject",
                "Test Body",
                "<html><body>Test HTML</body></html>"
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_test_email_connection_success(self, notification_service):
        """Test successful email connection test."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=None)
            
            result = await notification_service.test_email_connection()
            
            assert result["success"] is True
            assert "SMTP connection successful" in result["message"]
    
    @pytest.mark.asyncio
    async def test_test_email_connection_failure(self, notification_service):
        """Test failed email connection test."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("Connection refused")
            
            result = await notification_service.test_email_connection()
            
            assert result["success"] is False
            assert "Connection refused" in result["error"]
    
    def test_get_statistics(self, notification_service):
        """Test getting notification service statistics."""
        # Update some stats
        notification_service._stats["total_sent"] = 5
        notification_service._stats["total_throttled"] = 2
        notification_service._stats["total_failed"] = 1
        
        # Add some throttle data
        throttle = NotificationThrottle(
            notification_type=NotificationType.PRINTER_OFFLINE,
            last_sent=datetime.now(),
            count_in_hour=2,
            count_in_day=5
        )
        notification_service._throttle_data[NotificationType.PRINTER_OFFLINE] = throttle
        
        stats = notification_service.get_statistics()
        
        assert stats["enabled"] is True
        assert stats["running"] is False
        assert stats["statistics"]["total_sent"] == 5
        assert stats["statistics"]["total_throttled"] == 2
        assert stats["statistics"]["total_failed"] == 1
        
        assert "throttle_status" in stats
        assert NotificationType.PRINTER_OFFLINE.value in stats["throttle_status"]
        
        throttle_status = stats["throttle_status"][NotificationType.PRINTER_OFFLINE.value]
        assert throttle_status["count_in_hour"] == 2
        assert throttle_status["count_in_day"] == 5
    
    def test_log_notification_success(self, notification_service, mock_database):
        """Test logging successful notification."""
        context = {"test": "data"}
        
        notification_service._log_notification(
            NotificationType.SYSTEM_ERROR,
            context,
            success=True
        )
        
        # Verify database call
        mock_conn = mock_database.get_connection.return_value.__enter__.return_value
        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()
    
    def test_log_notification_no_database(self, notification_config):
        """Test logging notification without database."""
        service = NotificationService(notification_config, None)
        
        # Should not raise exception
        service._log_notification(
            NotificationType.SYSTEM_ERROR,
            {"test": "data"},
            success=True
        )
    
    def test_helper_methods(self, notification_service):
        """Test helper methods for getting system status."""
        # These methods return default values in the base implementation
        assert notification_service._get_last_online_time("printer") == "Unbekannt"
        assert notification_service._get_local_orders_count() == 0
        assert notification_service._get_queue_size() == 0
        assert notification_service._get_printer_status() == "unknown"
        assert notification_service._get_internet_status() == "unknown"
        assert notification_service._get_recovery_status() == "idle"
        assert notification_service._get_oldest_item_age() == "Unbekannt"


class TestNotificationTemplates:
    """Test cases for notification templates."""
    
    def test_template_rendering(self):
        """Test template rendering with context data."""
        template = NotificationTemplate(
            notification_type=NotificationType.PRINTER_OFFLINE,
            severity=NotificationSeverity.HIGH,
            subject_template="Printer Offline - {restaurant_name}",
            body_template="Printer went offline at {timestamp}",
            throttle_minutes=15,
            max_per_hour=4
        )
        
        context = {
            "restaurant_name": "Test Restaurant",
            "timestamp": "2025-09-19 20:00:00"
        }
        
        subject = template.subject_template.format(**context)
        body = template.body_template.format(**context)
        
        assert subject == "Printer Offline - Test Restaurant"
        assert body == "Printer went offline at 2025-09-19 20:00:00"
    
    def test_template_missing_context(self):
        """Test template rendering with missing context."""
        template = NotificationTemplate(
            notification_type=NotificationType.PRINTER_OFFLINE,
            severity=NotificationSeverity.HIGH,
            subject_template="Printer Offline - {restaurant_name}",
            body_template="Error: {error_message}",
            throttle_minutes=15,
            max_per_hour=4
        )
        
        context = {"restaurant_name": "Test Restaurant"}
        
        # Should raise KeyError for missing context
        with pytest.raises(KeyError):
            template.body_template.format(**context)


class TestNotificationConfig:
    """Test cases for notification configuration."""
    
    def test_config_creation(self):
        """Test notification configuration creation."""
        config = NotificationConfig(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@gmail.com",
            smtp_password="password",
            smtp_use_tls=True,
            from_email="sender@gmail.com",
            to_emails=["recipient@gmail.com"],
            enabled=True
        )
        
        assert config.smtp_server == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.smtp_username == "test@gmail.com"
        assert config.smtp_password == "password"
        assert config.smtp_use_tls is True
        assert config.from_email == "sender@gmail.com"
        assert config.to_emails == ["recipient@gmail.com"]
        assert config.enabled is True
    
    def test_config_defaults(self):
        """Test notification configuration defaults."""
        config = NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="password"
        )
        
        assert config.smtp_use_tls is True
        assert config.from_email == "test@test.com"  # Should default to username
        assert config.to_emails == []
        assert config.enabled is True
    
    def test_config_post_init(self):
        """Test notification configuration post-initialization."""
        config = NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="password",
            to_emails=None  # Should be converted to empty list
        )
        
        assert config.to_emails == []


class TestNotificationIntegration:
    """Integration tests for notification scenarios."""
    
    @pytest.fixture
    def integration_setup(self):
        """Setup for integration tests."""
        config = NotificationConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="testpass",
            from_email="test@test.com",
            to_emails=["manager@restaurant.com"],
            enabled=True
        )
        
        mock_database = Mock()
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_database.get_connection.return_value = mock_conn
        service = NotificationService(config, mock_database)
        
        return {
            "service": service,
            "config": config,
            "database": mock_database
        }
    
    @pytest.mark.asyncio
    async def test_end_to_end_notification_flow(self, integration_setup):
        """Test complete notification flow from event to email."""
        setup = integration_setup
        service = setup["service"]
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=None)
            
            # Start service
            await service.start()
            
            # Send notification
            context = {
                "timestamp": "2025-09-19 20:00:00",
                "restaurant_name": "Test Restaurant",
                "error_type": "Test Error",
                "error_message": "Integration test error"
            }
            
            await service.send_notification(NotificationType.SYSTEM_ERROR, context)
            
            # Wait for processing
            await asyncio.sleep(0.1)
            
            # Stop service
            await service.stop()
            
            # Verify email was sent
            mock_server.send_message.assert_called()
    
    def test_connectivity_event_to_notification_mapping(self, integration_setup):
        """Test mapping connectivity events to notifications."""
        setup = integration_setup
        service = setup["service"]
        service._running = True
        
        test_cases = [
            (ConnectivityEventType.PRINTER_OFFLINE, NotificationType.PRINTER_OFFLINE),
            (ConnectivityEventType.INTERNET_OFFLINE, NotificationType.INTERNET_OFFLINE)
        ]
        
        for event_type, expected_notification_type in test_cases:
            event = ConnectivityEvent(
                event_type=event_type,
                timestamp=datetime.now(),
                component="test",
                status=ConnectivityStatus.OFFLINE
            )
            
            with patch.object(service, 'send_notification') as mock_send:
                with patch('asyncio.create_task') as mock_create_task:
                    service.handle_connectivity_event(event)
                    
                    # Verify correct notification type would be sent
                    mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_throttling_integration(self, integration_setup):
        """Test throttling in integrated scenario."""
        setup = integration_setup
        service = setup["service"]
        
        # Send multiple notifications rapidly
        context = {"test": "data"}
        
        # First notification should go through
        await service.send_notification(NotificationType.PRINTER_OFFLINE, context)
        assert not service._notification_queue.empty()
        
        # Clear queue
        await service._notification_queue.get()
        
        # Update throttle to simulate sent notification
        service._update_throttle(NotificationType.PRINTER_OFFLINE)
        
        # Second notification should be throttled
        await service.send_notification(NotificationType.PRINTER_OFFLINE, context)
        assert service._notification_queue.empty()
        assert service._stats["total_throttled"] == 1
