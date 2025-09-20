"""
Unit tests for health monitor.
Tests system resource monitoring, health thresholds, and proactive cleanup.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from wix_printer_service.health_monitor import (
    HealthMonitor, HealthThreshold, HealthMetric, HealthEvent,
    HealthStatus, ResourceType, get_system_health
)


class TestHealthThreshold:
    """Test cases for HealthThreshold class."""
    
    def test_valid_threshold(self):
        """Test valid health threshold creation."""
        threshold = HealthThreshold(
            resource_type=ResourceType.MEMORY,
            warning_threshold=70.0,
            critical_threshold=85.0,
            emergency_threshold=95.0
        )
        
        assert threshold.resource_type == ResourceType.MEMORY
        assert threshold.warning_threshold == 70.0
        assert threshold.critical_threshold == 85.0
        assert threshold.emergency_threshold == 95.0
        assert threshold.check_interval == 30.0
        assert threshold.enabled is True
    
    def test_invalid_threshold_order(self):
        """Test invalid threshold order validation."""
        with pytest.raises(ValueError, match="Thresholds must be in ascending order"):
            HealthThreshold(
                resource_type=ResourceType.MEMORY,
                warning_threshold=90.0,  # Higher than critical
                critical_threshold=85.0,
                emergency_threshold=95.0
            )
    
    def test_invalid_threshold_range(self):
        """Test invalid threshold range validation."""
        with pytest.raises(ValueError, match="Thresholds must be in ascending order"):
            HealthThreshold(
                resource_type=ResourceType.MEMORY,
                warning_threshold=-10.0,  # Below 0
                critical_threshold=85.0,
                emergency_threshold=95.0
            )
        
        with pytest.raises(ValueError, match="Thresholds must be in ascending order"):
            HealthThreshold(
                resource_type=ResourceType.MEMORY,
                warning_threshold=70.0,
                critical_threshold=85.0,
                emergency_threshold=110.0  # Above 100
            )


class TestHealthMetric:
    """Test cases for HealthMetric class."""
    
    def test_metric_creation(self):
        """Test health metric creation."""
        threshold = HealthThreshold(
            resource_type=ResourceType.MEMORY,
            warning_threshold=70.0,
            critical_threshold=85.0,
            emergency_threshold=95.0
        )
        
        timestamp = datetime.now()
        metric = HealthMetric(
            resource_type=ResourceType.MEMORY,
            timestamp=timestamp,
            value=75.5,
            status=HealthStatus.WARNING,
            threshold_config=threshold,
            metadata={"test": "data"}
        )
        
        assert metric.resource_type == ResourceType.MEMORY
        assert metric.timestamp == timestamp
        assert metric.value == 75.5
        assert metric.status == HealthStatus.WARNING
        assert metric.threshold_config == threshold
        assert metric.metadata == {"test": "data"}


class TestHealthEvent:
    """Test cases for HealthEvent class."""
    
    def test_event_creation(self):
        """Test health event creation."""
        timestamp = datetime.now()
        event = HealthEvent(
            event_type="status_change",
            timestamp=timestamp,
            resource_type=ResourceType.MEMORY,
            old_status=HealthStatus.HEALTHY,
            new_status=HealthStatus.WARNING,
            metric_value=75.0,
            action_taken="cleanup_memory",
            metadata={"cleanup": "gc"}
        )
        
        assert event.event_type == "status_change"
        assert event.timestamp == timestamp
        assert event.resource_type == ResourceType.MEMORY
        assert event.old_status == HealthStatus.HEALTHY
        assert event.new_status == HealthStatus.WARNING
        assert event.metric_value == 75.0
        assert event.action_taken == "cleanup_memory"
        assert event.metadata == {"cleanup": "gc"}


class TestHealthMonitor:
    """Test cases for HealthMonitor class."""
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
        return mock_db
    
    @pytest.fixture
    def mock_notification_service(self):
        """Create a mock notification service."""
        mock_service = Mock()
        mock_service.send_notification = Mock(return_value=asyncio.Future())
        mock_service.send_notification.return_value.set_result(None)
        return mock_service
    
    @pytest.fixture
    def health_monitor(self, mock_database, mock_notification_service):
        """Create a health monitor for testing."""
        return HealthMonitor(mock_database, mock_notification_service)
    
    def test_initialization(self, health_monitor):
        """Test health monitor initialization."""
        assert not health_monitor._running
        assert health_monitor._monitor_task is None
        assert len(health_monitor._thresholds) == 4  # Memory, CPU, Disk, Threads
        assert ResourceType.MEMORY in health_monitor._thresholds
        assert ResourceType.CPU in health_monitor._thresholds
        assert ResourceType.DISK in health_monitor._thresholds
        assert ResourceType.THREADS in health_monitor._thresholds
    
    @pytest.mark.asyncio
    async def test_start_stop(self, health_monitor):
        """Test starting and stopping health monitor."""
        assert not health_monitor._running
        
        await health_monitor.start()
        assert health_monitor._running
        assert health_monitor._monitor_task is not None
        
        await health_monitor.stop()
        assert not health_monitor._running
    
    def test_add_remove_event_callback(self, health_monitor):
        """Test adding and removing event callbacks."""
        def test_callback(event):
            pass
        
        # Initially no callbacks
        assert len(health_monitor._event_callbacks) == 0
        
        # Add callback
        health_monitor.add_event_callback(test_callback)
        assert len(health_monitor._event_callbacks) == 1
        assert test_callback in health_monitor._event_callbacks
        
        # Remove callback
        health_monitor.remove_event_callback(test_callback)
        assert len(health_monitor._event_callbacks) == 0
    
    def test_add_cleanup_handler(self, health_monitor):
        """Test adding custom cleanup handlers."""
        def custom_cleanup():
            pass
        
        # Add custom cleanup handler
        health_monitor.add_cleanup_handler(ResourceType.MEMORY, custom_cleanup)
        
        # Verify handler was added
        assert custom_cleanup in health_monitor._cleanup_handlers[ResourceType.MEMORY]
    
    def test_update_threshold(self, health_monitor):
        """Test updating health thresholds."""
        new_threshold = HealthThreshold(
            resource_type=ResourceType.MEMORY,
            warning_threshold=60.0,
            critical_threshold=80.0,
            emergency_threshold=90.0,
            check_interval=60.0
        )
        
        health_monitor.update_threshold(ResourceType.MEMORY, new_threshold)
        
        updated_threshold = health_monitor._thresholds[ResourceType.MEMORY]
        assert updated_threshold.warning_threshold == 60.0
        assert updated_threshold.critical_threshold == 80.0
        assert updated_threshold.emergency_threshold == 90.0
        assert updated_threshold.check_interval == 60.0
    
    @patch('wix_printer_service.health_monitor.psutil.Process')
    @patch('wix_printer_service.health_monitor.psutil.virtual_memory')
    def test_collect_memory_metric(self, mock_virtual_memory, mock_process_class, health_monitor):
        """Test collecting memory metrics."""
        # Mock process and system memory
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        health_monitor._process = mock_process
        
        mock_memory_info = Mock()
        mock_memory_info.rss = 1024 * 1024 * 1024  # 1GB
        mock_memory_info.vms = 2048 * 1024 * 1024  # 2GB
        mock_process.memory_info.return_value = mock_memory_info
        
        mock_system_memory = Mock()
        mock_system_memory.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_system_memory.available = 6 * 1024 * 1024 * 1024  # 6GB
        mock_system_memory.percent = 25.0
        mock_virtual_memory.return_value = mock_system_memory
        
        # Collect memory metric
        metric = health_monitor._collect_metric(ResourceType.MEMORY)
        
        assert metric.resource_type == ResourceType.MEMORY
        assert metric.value == 12.5  # 1GB / 8GB * 100
        assert metric.status == HealthStatus.HEALTHY  # Below 70% warning threshold
        assert "rss_bytes" in metric.metadata
        assert "system_total_bytes" in metric.metadata
    
    @patch('wix_printer_service.health_monitor.psutil.Process')
    @patch('wix_printer_service.health_monitor.psutil.cpu_percent')
    def test_collect_cpu_metric(self, mock_cpu_percent, mock_process_class, health_monitor):
        """Test collecting CPU metrics."""
        # Mock process CPU usage
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        health_monitor._process = mock_process
        
        mock_process.cpu_percent.return_value = 45.0
        mock_cpu_times = Mock()
        mock_cpu_times._asdict.return_value = {"user": 10.0, "system": 5.0}
        mock_process.cpu_times.return_value = mock_cpu_times
        
        mock_cpu_percent.return_value = 30.0
        
        with patch('wix_printer_service.health_monitor.psutil.cpu_count', return_value=4):
            # Collect CPU metric
            metric = health_monitor._collect_metric(ResourceType.CPU)
        
        assert metric.resource_type == ResourceType.CPU
        assert metric.value == 45.0
        assert metric.status == HealthStatus.HEALTHY  # Below 70% warning threshold
        assert "process_cpu_percent" in metric.metadata
        assert "system_cpu_percent" in metric.metadata
        assert "cpu_count" in metric.metadata
    
    @patch('wix_printer_service.health_monitor.psutil.disk_usage')
    def test_collect_disk_metric(self, mock_disk_usage, health_monitor):
        """Test collecting disk metrics."""
        # Mock disk usage
        mock_usage = Mock()
        mock_usage.total = 1000 * 1024 * 1024 * 1024  # 1TB
        mock_usage.used = 500 * 1024 * 1024 * 1024    # 500GB
        mock_usage.free = 500 * 1024 * 1024 * 1024    # 500GB
        mock_disk_usage.return_value = mock_usage
        
        # Collect disk metric
        metric = health_monitor._collect_metric(ResourceType.DISK)
        
        assert metric.resource_type == ResourceType.DISK
        assert metric.value == 50.0  # 500GB / 1TB * 100
        assert metric.status == HealthStatus.HEALTHY  # Below 80% warning threshold
        assert "total_bytes" in metric.metadata
        assert "used_bytes" in metric.metadata
        assert "free_bytes" in metric.metadata
    
    @patch('wix_printer_service.health_monitor.psutil.Process')
    def test_collect_threads_metric(self, mock_process_class, health_monitor):
        """Test collecting thread metrics."""
        # Mock process thread count
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        health_monitor._process = mock_process
        
        mock_process.num_threads.return_value = 50
        
        # Collect threads metric
        metric = health_monitor._collect_metric(ResourceType.THREADS)
        
        assert metric.resource_type == ResourceType.THREADS
        assert metric.value == 5.0  # 50 / 1000 * 100
        assert metric.status == HealthStatus.HEALTHY  # Below 80% warning threshold
        assert "thread_count" in metric.metadata
        assert "estimated_max_threads" in metric.metadata
    
    def test_status_determination(self, health_monitor):
        """Test health status determination based on thresholds."""
        threshold = HealthThreshold(
            resource_type=ResourceType.MEMORY,
            warning_threshold=70.0,
            critical_threshold=85.0,
            emergency_threshold=95.0
        )
        
        # Test different values
        test_cases = [
            (50.0, HealthStatus.HEALTHY),
            (75.0, HealthStatus.WARNING),
            (90.0, HealthStatus.CRITICAL),
            (98.0, HealthStatus.EMERGENCY)
        ]
        
        for value, expected_status in test_cases:
            with patch.object(health_monitor, '_collect_metric') as mock_collect:
                metric = HealthMetric(
                    resource_type=ResourceType.MEMORY,
                    timestamp=datetime.now(),
                    value=value,
                    status=expected_status,
                    threshold_config=threshold
                )
                mock_collect.return_value = metric
                
                collected_metric = health_monitor._collect_metric(ResourceType.MEMORY)
                assert collected_metric.status == expected_status
    
    @pytest.mark.asyncio
    async def test_process_metric_status_change(self, health_monitor):
        """Test processing metric with status change."""
        threshold = HealthThreshold(
            resource_type=ResourceType.MEMORY,
            warning_threshold=70.0,
            critical_threshold=85.0,
            emergency_threshold=95.0
        )
        
        # Create a warning metric
        metric = HealthMetric(
            resource_type=ResourceType.MEMORY,
            timestamp=datetime.now(),
            value=75.0,
            status=HealthStatus.WARNING,
            threshold_config=threshold
        )
        
        # Mock cleanup handler
        cleanup_called = False
        def mock_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
        
        health_monitor._cleanup_handlers[ResourceType.MEMORY] = [mock_cleanup]
        
        # Process metric
        await health_monitor._process_metric(metric)
        
        # Verify metric was added to history
        assert len(health_monitor._health_history) == 1
        assert health_monitor._health_history[0] == metric
        
        # Verify cleanup was called
        assert cleanup_called
        assert health_monitor._stats["cleanup_actions"] == 1
        assert health_monitor._stats["warning_events"] == 1
    
    def test_get_current_health(self, health_monitor):
        """Test getting current health status."""
        with patch.object(health_monitor, '_collect_metric') as mock_collect:
            # Mock metrics for different resources
            memory_metric = HealthMetric(
                resource_type=ResourceType.MEMORY,
                timestamp=datetime.now(),
                value=65.0,
                status=HealthStatus.HEALTHY,
                threshold_config=health_monitor._thresholds[ResourceType.MEMORY],
                metadata={"test": "memory"}
            )
            
            cpu_metric = HealthMetric(
                resource_type=ResourceType.CPU,
                timestamp=datetime.now(),
                value=80.0,
                status=HealthStatus.WARNING,
                threshold_config=health_monitor._thresholds[ResourceType.CPU],
                metadata={"test": "cpu"}
            )
            
            mock_collect.side_effect = [memory_metric, cpu_metric, Exception("Disk error"), Exception("Thread error")]
            
            health_data = health_monitor.get_current_health()
            
            # Verify successful metrics
            assert "memory" in health_data
            assert health_data["memory"]["value"] == 65.0
            assert health_data["memory"]["status"] == "healthy"
            
            assert "cpu" in health_data
            assert health_data["cpu"]["value"] == 80.0
            assert health_data["cpu"]["status"] == "warning"
            
            # Verify error handling
            assert "disk" in health_data
            assert "error" in health_data["disk"]
            
            assert "threads" in health_data
            assert "error" in health_data["threads"]
    
    def test_get_health_history(self, health_monitor):
        """Test getting health history."""
        # Add some test metrics to history
        timestamp1 = datetime.now() - timedelta(minutes=5)
        timestamp2 = datetime.now() - timedelta(minutes=3)
        timestamp3 = datetime.now() - timedelta(minutes=1)
        
        metrics = [
            HealthMetric(ResourceType.MEMORY, timestamp1, 60.0, HealthStatus.HEALTHY, health_monitor._thresholds[ResourceType.MEMORY]),
            HealthMetric(ResourceType.CPU, timestamp2, 75.0, HealthStatus.WARNING, health_monitor._thresholds[ResourceType.CPU]),
            HealthMetric(ResourceType.MEMORY, timestamp3, 80.0, HealthStatus.WARNING, health_monitor._thresholds[ResourceType.MEMORY])
        ]
        
        health_monitor._health_history = metrics
        
        # Get all history
        all_history = health_monitor.get_health_history()
        assert len(all_history) == 3
        
        # Verify ordering (newest first)
        assert all_history[0]["timestamp"] == timestamp3.isoformat()
        assert all_history[1]["timestamp"] == timestamp2.isoformat()
        assert all_history[2]["timestamp"] == timestamp1.isoformat()
        
        # Get memory-only history
        memory_history = health_monitor.get_health_history(ResourceType.MEMORY)
        assert len(memory_history) == 2
        assert all(h["resource_type"] == "memory" for h in memory_history)
        
        # Get limited history
        limited_history = health_monitor.get_health_history(limit=1)
        assert len(limited_history) == 1
        assert limited_history[0]["timestamp"] == timestamp3.isoformat()
    
    def test_get_statistics(self, health_monitor):
        """Test getting health monitor statistics."""
        stats = health_monitor.get_statistics()
        
        assert "running" in stats
        assert "uptime_seconds" in stats
        assert "statistics" in stats
        assert "thresholds" in stats
        assert "cleanup_handlers" in stats
        
        # Verify statistics structure
        statistics = stats["statistics"]
        expected_keys = [
            "total_checks", "warning_events", "critical_events",
            "emergency_events", "cleanup_actions", "last_check", "uptime_start"
        ]
        for key in expected_keys:
            assert key in statistics
        
        # Verify thresholds
        thresholds = stats["thresholds"]
        for resource_type in ResourceType:
            if resource_type in health_monitor._thresholds:
                assert resource_type.value in thresholds
                threshold_data = thresholds[resource_type.value]
                assert "warning" in threshold_data
                assert "critical" in threshold_data
                assert "emergency" in threshold_data
                assert "enabled" in threshold_data
                assert "check_interval" in threshold_data
    
    @pytest.mark.asyncio
    async def test_force_health_check(self, health_monitor):
        """Test forcing immediate health check."""
        with patch.object(health_monitor, '_collect_metric') as mock_collect:
            with patch.object(health_monitor, '_process_metric') as mock_process:
                # Mock successful metric collection
                mock_metric = HealthMetric(
                    resource_type=ResourceType.MEMORY,
                    timestamp=datetime.now(),
                    value=65.0,
                    status=HealthStatus.HEALTHY,
                    threshold_config=health_monitor._thresholds[ResourceType.MEMORY]
                )
                mock_collect.return_value = mock_metric
                mock_process.return_value = None
                
                results = await health_monitor.force_health_check()
                
                # Verify results
                assert len(results) == 4  # All resource types
                for resource_type in ResourceType:
                    if resource_type in health_monitor._thresholds:
                        assert resource_type.value in results
                        result = results[resource_type.value]
                        assert "value" in result
                        assert "status" in result
                
                # Verify methods were called
                assert mock_collect.call_count == 4
                assert mock_process.call_count == 4
    
    def test_database_logging(self, mock_database):
        """Test database logging of health metrics."""
        health_monitor = HealthMonitor(mock_database)
        
        metric = HealthMetric(
            resource_type=ResourceType.MEMORY,
            timestamp=datetime.now(),
            value=75.0,
            status=HealthStatus.WARNING,
            threshold_config=health_monitor._thresholds[ResourceType.MEMORY],
            metadata={"test": "data"}
        )
        
        health_monitor._log_metric(metric)
        
        # Verify database call
        mock_conn = mock_database.get_connection.return_value.__enter__.return_value
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


class TestSystemHealthFunction:
    """Test cases for get_system_health function."""
    
    @patch('wix_printer_service.health_monitor.psutil.Process')
    @patch('wix_printer_service.health_monitor.psutil.virtual_memory')
    @patch('wix_printer_service.health_monitor.psutil.disk_usage')
    def test_get_system_health_success(self, mock_disk_usage, mock_virtual_memory, mock_process_class):
        """Test successful system health retrieval."""
        # Mock process
        mock_process = Mock()
        mock_process_class.return_value = mock_process
        
        # Mock memory
        mock_memory_info = Mock()
        mock_memory_info.rss = 1024 * 1024 * 1024  # 1GB
        mock_process.memory_info.return_value = mock_memory_info
        
        mock_system_memory = Mock()
        mock_system_memory.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_virtual_memory.return_value = mock_system_memory
        
        # Mock CPU
        mock_process.cpu_percent.return_value = 25.0
        
        # Mock disk
        mock_usage = Mock()
        mock_usage.total = 1000 * 1024 * 1024 * 1024  # 1TB
        mock_usage.used = 300 * 1024 * 1024 * 1024    # 300GB
        mock_disk_usage.return_value = mock_usage
        
        # Mock threads
        mock_process.num_threads.return_value = 20
        
        health = get_system_health()
        
        assert "memory_percent" in health
        assert "cpu_percent" in health
        assert "disk_percent" in health
        assert "thread_count" in health
        assert "timestamp" in health
        
        assert health["memory_percent"] == 12.5  # 1GB / 8GB * 100
        assert health["cpu_percent"] == 25.0
        assert health["disk_percent"] == 30.0  # 300GB / 1TB * 100
        assert health["thread_count"] == 20
    
    @patch('wix_printer_service.health_monitor.psutil.Process')
    def test_get_system_health_error(self, mock_process_class):
        """Test system health retrieval with error."""
        mock_process_class.side_effect = Exception("Process error")
        
        health = get_system_health()
        
        assert "error" in health
        assert "Process error" in health["error"]


class TestIntegrationScenarios:
    """Integration test scenarios."""
    
    @pytest.mark.asyncio
    async def test_health_monitor_lifecycle(self):
        """Test complete health monitor lifecycle."""
        health_monitor = HealthMonitor()
        
        # Initially not running
        assert not health_monitor._running
        
        # Start monitor
        await health_monitor.start()
        assert health_monitor._running
        
        # Force health check
        with patch.object(health_monitor, '_collect_metric') as mock_collect:
            mock_metric = HealthMetric(
                resource_type=ResourceType.MEMORY,
                timestamp=datetime.now(),
                value=65.0,
                status=HealthStatus.HEALTHY,
                threshold_config=health_monitor._thresholds[ResourceType.MEMORY]
            )
            mock_collect.return_value = mock_metric
            
            results = await health_monitor.force_health_check()
            assert len(results) > 0
        
        # Stop monitor
        await health_monitor.stop()
        assert not health_monitor._running
    
    @pytest.mark.asyncio
    async def test_health_event_workflow(self):
        """Test complete health event workflow."""
        health_monitor = HealthMonitor()
        
        # Add event callback
        events_received = []
        def event_callback(event):
            events_received.append(event)
        
        health_monitor.add_event_callback(event_callback)
        
        # Create metrics showing status change
        threshold = health_monitor._thresholds[ResourceType.MEMORY]
        
        # First metric - healthy
        healthy_metric = HealthMetric(
            resource_type=ResourceType.MEMORY,
            timestamp=datetime.now(),
            value=65.0,
            status=HealthStatus.HEALTHY,
            threshold_config=threshold
        )
        
        await health_monitor._process_metric(healthy_metric)
        
        # Second metric - warning (status change)
        warning_metric = HealthMetric(
            resource_type=ResourceType.MEMORY,
            timestamp=datetime.now(),
            value=75.0,
            status=HealthStatus.WARNING,
            threshold_config=threshold
        )
        
        await health_monitor._process_metric(warning_metric)
        
        # Verify event was fired
        assert len(events_received) == 1
        event = events_received[0]
        assert event.resource_type == ResourceType.MEMORY
        assert event.old_status == HealthStatus.HEALTHY
        assert event.new_status == HealthStatus.WARNING
        assert event.metric_value == 75.0
        
        # Verify history
        history = health_monitor.get_health_history()
        assert len(history) == 2
        assert history[0]["value"] == 75.0  # Most recent first
        assert history[1]["value"] == 65.0
