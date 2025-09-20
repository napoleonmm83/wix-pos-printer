"""
Unit tests for retry manager.
Tests intelligent retry logic, exponential backoff, and dead letter queue.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from wix_printer_service.retry_manager import (
    RetryManager, RetryConfig, RetryStrategy, FailureType,
    RetryableTask, RetryAttempt, DeadLetterQueue,
    retry_print_job, retry_network_operation, auto_retry
)


class TestRetryConfig:
    """Test cases for RetryConfig class."""
    
    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.initial_delay == 1.0
        assert config.max_delay == 300.0
        assert config.backoff_factor == 2.0
        assert config.jitter_factor == 0.25
        assert config.max_attempts == 5
        assert config.timeout is None
    
    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            initial_delay=2.0,
            max_delay=60.0,
            backoff_factor=1.5,
            jitter_factor=0.1,
            max_attempts=3,
            timeout=30.0
        )
        
        assert config.strategy == RetryStrategy.LINEAR_BACKOFF
        assert config.initial_delay == 2.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 1.5
        assert config.jitter_factor == 0.1
        assert config.max_attempts == 3
        assert config.timeout == 30.0
    
    def test_invalid_config_validation(self):
        """Test validation of invalid configurations."""
        with pytest.raises(ValueError, match="initial_delay must be positive"):
            RetryConfig(initial_delay=0)
        
        with pytest.raises(ValueError, match="max_delay must be >= initial_delay"):
            RetryConfig(initial_delay=10, max_delay=5)
        
        with pytest.raises(ValueError, match="backoff_factor must be > 1.0"):
            RetryConfig(backoff_factor=1.0)
        
        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=1.5)
        
        with pytest.raises(ValueError, match="max_attempts must be positive"):
            RetryConfig(max_attempts=0)


class TestRetryableTask:
    """Test cases for RetryableTask class."""
    
    def test_task_creation(self):
        """Test retryable task creation."""
        def dummy_operation():
            return "success"
        
        task = RetryableTask(
            id="test_task",
            operation=dummy_operation,
            args=(1, 2),
            kwargs={"key": "value"},
            failure_type=FailureType.PRINTER_ERROR
        )
        
        assert task.id == "test_task"
        assert task.operation == dummy_operation
        assert task.args == (1, 2)
        assert task.kwargs == {"key": "value"}
        assert task.failure_type == FailureType.PRINTER_ERROR
        assert task.attempt_count == 0
        assert not task.is_exhausted
        assert task.last_attempt_time is None
    
    def test_task_attempts_tracking(self):
        """Test tracking of retry attempts."""
        def dummy_operation():
            return "success"
        
        config = RetryConfig(max_attempts=3)
        task = RetryableTask(
            id="test_task",
            operation=dummy_operation,
            config=config
        )
        
        # Add some attempts
        task.attempts.append(RetryAttempt(1, datetime.now(), 0))
        task.attempts.append(RetryAttempt(2, datetime.now(), 1.0))
        
        assert task.attempt_count == 2
        assert not task.is_exhausted
        assert task.last_attempt_time is not None
        
        # Add final attempt
        task.attempts.append(RetryAttempt(3, datetime.now(), 2.0))
        
        assert task.attempt_count == 3
        assert task.is_exhausted


class TestDeadLetterQueue:
    """Test cases for DeadLetterQueue class."""
    
    @pytest.fixture
    def dead_letter_queue(self):
        """Create a dead letter queue for testing."""
        return DeadLetterQueue()
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
        return mock_db
    
    def test_add_and_get_tasks(self, dead_letter_queue):
        """Test adding and retrieving tasks from dead letter queue."""
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="failed_task", operation=dummy_operation)
        
        # Initially empty
        assert len(dead_letter_queue.get_tasks()) == 0
        
        # Add task
        dead_letter_queue.add_task(task)
        tasks = dead_letter_queue.get_tasks()
        
        assert len(tasks) == 1
        assert tasks[0].id == "failed_task"
    
    def test_remove_task(self, dead_letter_queue):
        """Test removing task from dead letter queue."""
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="failed_task", operation=dummy_operation)
        dead_letter_queue.add_task(task)
        
        # Remove existing task
        removed_task = dead_letter_queue.remove_task("failed_task")
        assert removed_task is not None
        assert removed_task.id == "failed_task"
        assert len(dead_letter_queue.get_tasks()) == 0
        
        # Remove non-existing task
        removed_task = dead_letter_queue.remove_task("non_existing")
        assert removed_task is None
    
    def test_requeue_task(self, dead_letter_queue):
        """Test requeuing task from dead letter queue."""
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="failed_task", operation=dummy_operation)
        task.attempts.append(RetryAttempt(1, datetime.now(), 0, Exception("test error")))
        task.last_error = Exception("test error")
        
        dead_letter_queue.add_task(task)
        
        # Requeue task
        requeued_task = dead_letter_queue.requeue_task("failed_task")
        
        assert requeued_task is not None
        assert requeued_task.id == "failed_task"
        assert len(requeued_task.attempts) == 0  # Attempts reset
        assert requeued_task.last_error is None  # Error reset
        assert len(dead_letter_queue.get_tasks()) == 0  # Removed from queue
    
    def test_clear_queue(self, dead_letter_queue):
        """Test clearing all tasks from dead letter queue."""
        def dummy_operation():
            return "success"
        
        # Add multiple tasks
        for i in range(3):
            task = RetryableTask(id=f"task_{i}", operation=dummy_operation)
            dead_letter_queue.add_task(task)
        
        assert len(dead_letter_queue.get_tasks()) == 3
        
        # Clear queue
        dead_letter_queue.clear()
        assert len(dead_letter_queue.get_tasks()) == 0
    
    def test_database_logging(self, mock_database):
        """Test database logging of dead letter tasks."""
        dead_letter_queue = DeadLetterQueue(mock_database)
        
        def dummy_operation():
            return "success"
        
        task = RetryableTask(
            id="failed_task",
            operation=dummy_operation,
            failure_type=FailureType.PRINTER_ERROR
        )
        task.last_error = Exception("test error")
        
        dead_letter_queue.add_task(task)
        
        # Verify database call
        mock_conn = mock_database.get_connection.return_value.__enter__.return_value
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


class TestRetryManager:
    """Test cases for RetryManager class."""
    
    @pytest.fixture
    def retry_manager(self):
        """Create a retry manager for testing."""
        return RetryManager()
    
    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        mock_db = Mock()
        mock_conn = Mock()
        mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
        return mock_db
    
    @pytest.mark.asyncio
    async def test_start_stop(self, retry_manager):
        """Test starting and stopping retry manager."""
        assert not retry_manager._running
        
        await retry_manager.start()
        assert retry_manager._running
        assert retry_manager._worker_task is not None
        
        await retry_manager.stop()
        assert not retry_manager._running
    
    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self, retry_manager):
        """Test successful operation that doesn't need retry."""
        await retry_manager.start()
        
        def successful_operation():
            return "success"
        
        try:
            result = await retry_manager.retry_operation(successful_operation)
            assert result == "success"
            
            # Check statistics
            stats = retry_manager.get_statistics()
            assert stats["statistics"]["total_tasks"] == 1
            assert stats["statistics"]["successful_retries"] == 0  # No retries needed
            
        finally:
            await retry_manager.stop()
    
    @pytest.mark.asyncio
    async def test_retry_with_eventual_success(self, retry_manager):
        """Test operation that fails initially but eventually succeeds."""
        await retry_manager.start()
        
        call_count = 0
        
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Failure {call_count}")
            return "success"
        
        try:
            result = await retry_manager.retry_operation(
                flaky_operation,
                failure_type=FailureType.TEMPORARY_ERROR
            )
            assert result == "success"
            assert call_count == 3
            
        finally:
            await retry_manager.stop()
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion_and_dead_letter(self, retry_manager):
        """Test retry exhaustion and dead letter queue."""
        await retry_manager.start()
        
        def always_failing_operation():
            raise Exception("Always fails")
        
        config = RetryConfig(max_attempts=2, initial_delay=0.1)
        
        try:
            with pytest.raises(Exception, match="Always fails"):
                await retry_manager.retry_operation(
                    always_failing_operation,
                    config=config,
                    task_id="failing_task"
                )
            
            # Check dead letter queue
            dead_tasks = retry_manager.dead_letter_queue.get_tasks()
            assert len(dead_tasks) == 1
            assert dead_tasks[0].id == "failing_task"
            assert dead_tasks[0].attempt_count == 2
            
        finally:
            await retry_manager.stop()
    
    @pytest.mark.asyncio
    async def test_async_operation_retry(self, retry_manager):
        """Test retry of async operations."""
        await retry_manager.start()
        
        call_count = 0
        
        async def async_flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception(f"Async failure {call_count}")
            return "async success"
        
        try:
            result = await retry_manager.retry_operation(async_flaky_operation)
            assert result == "async success"
            assert call_count == 2
            
        finally:
            await retry_manager.stop()
    
    def test_delay_calculation_exponential(self, retry_manager):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter_factor=0.0  # No jitter for predictable testing
        )
        
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="test", operation=dummy_operation, config=config)
        
        # First attempt (no delay)
        delay = retry_manager._calculate_delay(task)
        assert delay == 0.0
        
        # Second attempt
        task.attempts.append(RetryAttempt(1, datetime.now(), 0))
        delay = retry_manager._calculate_delay(task)
        assert delay == 1.0
        
        # Third attempt
        task.attempts.append(RetryAttempt(2, datetime.now(), 1.0))
        delay = retry_manager._calculate_delay(task)
        assert delay == 2.0
        
        # Fourth attempt
        task.attempts.append(RetryAttempt(3, datetime.now(), 2.0))
        delay = retry_manager._calculate_delay(task)
        assert delay == 4.0
    
    def test_delay_calculation_linear(self, retry_manager):
        """Test linear backoff delay calculation."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            initial_delay=2.0,
            jitter_factor=0.0
        )
        
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="test", operation=dummy_operation, config=config)
        
        # Add attempts to simulate progression
        for i in range(1, 4):
            task.attempts.append(RetryAttempt(i, datetime.now(), 0))
            delay = retry_manager._calculate_delay(task)
            expected_delay = 2.0 * i
            assert delay == expected_delay
    
    def test_delay_calculation_with_max_delay(self, retry_manager):
        """Test delay calculation with maximum delay limit."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay=10.0,
            backoff_factor=3.0,
            max_delay=20.0,
            jitter_factor=0.0
        )
        
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="test", operation=dummy_operation, config=config)
        
        # Add attempts to exceed max delay
        task.attempts.append(RetryAttempt(1, datetime.now(), 0))
        task.attempts.append(RetryAttempt(2, datetime.now(), 10.0))
        
        delay = retry_manager._calculate_delay(task)
        assert delay == 20.0  # Capped at max_delay
    
    def test_delay_calculation_with_jitter(self, retry_manager):
        """Test delay calculation with jitter."""
        config = RetryConfig(
            strategy=RetryStrategy.FIXED_DELAY,
            initial_delay=10.0,
            jitter_factor=0.5  # ±50% jitter
        )
        
        def dummy_operation():
            return "success"
        
        task = RetryableTask(id="test", operation=dummy_operation, config=config)
        task.attempts.append(RetryAttempt(1, datetime.now(), 0))
        
        # Test multiple calculations to ensure jitter varies
        delays = [retry_manager._calculate_delay(task) for _ in range(10)]
        
        # All delays should be between 5.0 and 15.0 (10.0 ± 50%)
        assert all(5.0 <= delay <= 15.0 for delay in delays)
        
        # Should have some variation (not all the same)
        assert len(set(delays)) > 1
    
    def test_default_configurations(self, retry_manager):
        """Test default retry configurations for different failure types."""
        configs = retry_manager._default_configs
        
        # Check that all failure types have configurations
        for failure_type in FailureType:
            assert failure_type in configs
            config = configs[failure_type]
            assert isinstance(config, RetryConfig)
            assert config.max_attempts > 0
            assert config.initial_delay > 0
    
    def test_statistics_tracking(self, retry_manager):
        """Test statistics tracking."""
        stats = retry_manager.get_statistics()
        
        assert "running" in stats
        assert "active_retries" in stats
        assert "dead_letter_queue_size" in stats
        assert "statistics" in stats
        assert "default_configs" in stats
        
        # Check statistics structure
        statistics = stats["statistics"]
        expected_keys = [
            "total_tasks", "successful_retries", "failed_retries",
            "dead_letter_tasks", "average_attempts"
        ]
        for key in expected_keys:
            assert key in statistics
    
    def test_database_logging(self, mock_database):
        """Test database logging of retry attempts."""
        retry_manager = RetryManager(mock_database)
        
        def dummy_operation():
            return "success"
        
        task = RetryableTask(
            id="test_task",
            operation=dummy_operation,
            failure_type=FailureType.PRINTER_ERROR
        )
        
        attempt = RetryAttempt(
            attempt_number=1,
            timestamp=datetime.now(),
            delay_before=0,
            success=True,
            duration=0.5
        )
        
        retry_manager._log_retry_attempt(task, attempt)
        
        # Verify database call
        mock_conn = mock_database.get_connection.return_value.__enter__.return_value
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    @pytest.mark.asyncio
    async def test_retry_print_job(self):
        """Test retry_print_job convenience function."""
        call_count = 0
        
        def print_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Print failed")
            return "printed"
        
        result = await retry_print_job(print_operation)
        assert result == "printed"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_network_operation(self):
        """Test retry_network_operation convenience function."""
        call_count = 0
        
        async def network_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Network error")
            return "network success"
        
        result = await retry_network_operation(network_operation)
        assert result == "network success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_auto_retry_decorator_async(self):
        """Test auto_retry decorator with async function."""
        call_count = 0
        
        @auto_retry(failure_type=FailureType.TEMPORARY_ERROR)
        async def decorated_async_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "decorated success"
        
        result = await decorated_async_function()
        assert result == "decorated success"
        assert call_count == 2
    
    def test_auto_retry_decorator_sync(self):
        """Test auto_retry decorator with sync function."""
        call_count = 0
        
        @auto_retry(failure_type=FailureType.TEMPORARY_ERROR)
        def decorated_sync_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "decorated success"
        
        result = decorated_sync_function()
        assert result == "decorated success"
        assert call_count == 2


class TestIntegrationScenarios:
    """Integration test scenarios."""
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_retries(self):
        """Test multiple concurrent retry operations."""
        retry_manager = RetryManager()
        await retry_manager.start()
        
        async def flaky_operation(task_id: str):
            # Simulate different failure patterns
            if task_id == "task_1":
                raise Exception("Task 1 always fails")
            elif task_id == "task_2":
                return "Task 2 succeeds immediately"
            else:  # task_3
                # Fail once, then succeed
                if not hasattr(flaky_operation, 'task_3_called'):
                    flaky_operation.task_3_called = True
                    raise Exception("Task 3 fails once")
                return "Task 3 succeeds on retry"
        
        config = RetryConfig(max_attempts=2, initial_delay=0.1)
        
        try:
            # Start multiple concurrent operations
            tasks = []
            for i in range(1, 4):
                task_id = f"task_{i}"
                if i == 1:  # This will fail and go to dead letter
                    task = asyncio.create_task(
                        retry_manager.retry_operation(
                            flaky_operation,
                            task_id,
                            task_id=task_id,
                            config=config
                        )
                    )
                else:
                    task = asyncio.create_task(
                        retry_manager.retry_operation(
                            flaky_operation,
                            task_id,
                            task_id=task_id,
                            config=config
                        )
                    )
                tasks.append((task_id, task))
            
            # Wait for all tasks to complete (some will fail)
            results = []
            for task_id, task in tasks:
                try:
                    result = await task
                    results.append((task_id, result))
                except Exception as e:
                    results.append((task_id, f"Failed: {e}"))
            
            # Verify results
            assert len(results) == 3
            
            # Task 2 should succeed immediately
            task_2_result = next(r for r in results if r[0] == "task_2")
            assert task_2_result[1] == "Task 2 succeeds immediately"
            
            # Task 3 should succeed after retry
            task_3_result = next(r for r in results if r[0] == "task_3")
            assert task_3_result[1] == "Task 3 succeeds on retry"
            
            # Task 1 should fail and be in dead letter queue
            task_1_result = next(r for r in results if r[0] == "task_1")
            assert "Failed:" in task_1_result[1]
            
            # Check dead letter queue
            dead_tasks = retry_manager.dead_letter_queue.get_tasks()
            assert len(dead_tasks) == 1
            assert dead_tasks[0].id == "task_1"
            
        finally:
            await retry_manager.stop()
    
    @pytest.mark.asyncio
    async def test_retry_manager_lifecycle(self):
        """Test complete retry manager lifecycle."""
        retry_manager = RetryManager()
        
        # Initially not running
        assert not retry_manager._running
        
        # Start manager
        await retry_manager.start()
        assert retry_manager._running
        
        # Perform some operations
        def successful_op():
            return "success"
        
        def failing_op():
            raise Exception("Always fails")
        
        # Successful operation
        result = await retry_manager.retry_operation(successful_op)
        assert result == "success"
        
        # Failing operation
        config = RetryConfig(max_attempts=2, initial_delay=0.1)
        with pytest.raises(Exception):
            await retry_manager.retry_operation(failing_op, config=config)
        
        # Check statistics
        stats = retry_manager.get_statistics()
        assert stats["statistics"]["total_tasks"] == 2
        assert stats["dead_letter_queue_size"] == 1
        
        # Stop manager
        await retry_manager.stop()
        assert not retry_manager._running
