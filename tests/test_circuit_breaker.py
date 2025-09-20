"""
Unit tests for circuit breaker.
Tests circuit breaker states, failure detection, and recovery patterns.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from wix_printer_service.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerManager,
    CircuitState, FailureType, CircuitBreakerOpenException,
    get_circuit_breaker, circuit_breaker,
    printer_circuit_breaker, wix_api_circuit_breaker, smtp_circuit_breaker
)


class TestCircuitBreakerConfig:
    """Test cases for CircuitBreakerConfig class."""
    
    def test_default_config(self):
        """Test default circuit breaker configuration."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout_duration == 60.0
        assert config.call_timeout == 30.0
        assert config.expected_exception is None
    
    def test_custom_config(self):
        """Test custom circuit breaker configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_duration=30.0,
            call_timeout=10.0
        )
        
        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.timeout_duration == 30.0
        assert config.call_timeout == 10.0
    
    def test_invalid_config_validation(self):
        """Test validation of invalid configurations."""
        with pytest.raises(ValueError, match="failure_threshold must be positive"):
            CircuitBreakerConfig(failure_threshold=0)
        
        with pytest.raises(ValueError, match="success_threshold must be positive"):
            CircuitBreakerConfig(success_threshold=0)
        
        with pytest.raises(ValueError, match="timeout_duration must be positive"):
            CircuitBreakerConfig(timeout_duration=0)


class TestCircuitBreaker:
    """Test cases for CircuitBreaker class."""
    
    @pytest.fixture
    def circuit_breaker_config(self):
        """Create a test circuit breaker configuration."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_duration=1.0,  # Short timeout for testing
            call_timeout=0.5
        )
    
    @pytest.fixture
    def circuit_breaker(self, circuit_breaker_config):
        """Create a circuit breaker for testing."""
        return CircuitBreaker("test_circuit", circuit_breaker_config)
    
    def test_initialization(self, circuit_breaker):
        """Test circuit breaker initialization."""
        assert circuit_breaker.name == "test_circuit"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.is_closed
        assert not circuit_breaker.is_open
        assert not circuit_breaker.is_half_open
    
    def test_successful_call(self, circuit_breaker):
        """Test successful function call through circuit breaker."""
        def successful_function():
            return "success"
        
        result = circuit_breaker.call(successful_function)
        
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        
        # Check statistics
        stats = circuit_breaker.get_statistics()
        assert stats["statistics"]["total_calls"] == 1
        assert stats["statistics"]["successful_calls"] == 1
        assert stats["statistics"]["failed_calls"] == 0
    
    def test_failed_call(self, circuit_breaker):
        """Test failed function call through circuit breaker."""
        def failing_function():
            raise Exception("Test failure")
        
        with pytest.raises(Exception, match="Test failure"):
            circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.CLOSED  # Still closed after 1 failure
        assert circuit_breaker.failure_count == 1
        
        # Check statistics
        stats = circuit_breaker.get_statistics()
        assert stats["statistics"]["total_calls"] == 1
        assert stats["statistics"]["successful_calls"] == 0
        assert stats["statistics"]["failed_calls"] == 1
    
    def test_circuit_opens_after_threshold(self, circuit_breaker):
        """Test circuit opens after failure threshold is reached."""
        def failing_function():
            raise Exception("Test failure")
        
        # Make failures up to threshold
        for i in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception, match="Test failure"):
                circuit_breaker.call(failing_function)
        
        # Circuit should now be open
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.is_open
        
        # Next call should fail fast
        with pytest.raises(CircuitBreakerOpenException):
            circuit_breaker.call(failing_function)
        
        # Check statistics
        stats = circuit_breaker.get_statistics()
        assert stats["statistics"]["circuit_opens"] == 1
        assert stats["statistics"]["total_failures_prevented"] == 1
    
    def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test circuit transitions from open to half-open after timeout."""
        def failing_function():
            raise Exception("Test failure")
        
        # Open the circuit
        for i in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(circuit_breaker.config.timeout_duration + 0.1)
        
        # Next call should transition to half-open (but still fail)
        with pytest.raises(Exception, match="Test failure"):
            circuit_breaker.call(failing_function)
        
        # Should be back to open after failure in half-open
        assert circuit_breaker.state == CircuitState.OPEN
    
    def test_circuit_closes_after_success_in_half_open(self, circuit_breaker):
        """Test circuit closes after successful calls in half-open state."""
        def failing_function():
            raise Exception("Test failure")
        
        def successful_function():
            return "success"
        
        # Open the circuit
        for i in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(circuit_breaker.config.timeout_duration + 0.1)
        
        # Make successful calls to close the circuit
        for i in range(circuit_breaker.config.success_threshold):
            result = circuit_breaker.call(successful_function)
            assert result == "success"
        
        # Circuit should now be closed
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        
        # Check statistics
        stats = circuit_breaker.get_statistics()
        assert stats["statistics"]["circuit_closes"] == 1
    
    @pytest.mark.asyncio
    async def test_async_call_success(self, circuit_breaker):
        """Test successful async function call through circuit breaker."""
        async def async_successful_function():
            return "async success"
        
        result = await circuit_breaker.async_call(async_successful_function)
        
        assert result == "async success"
        assert circuit_breaker.state == CircuitState.CLOSED
        
        # Check statistics
        stats = circuit_breaker.get_statistics()
        assert stats["statistics"]["successful_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_async_call_failure(self, circuit_breaker):
        """Test failed async function call through circuit breaker."""
        async def async_failing_function():
            raise Exception("Async test failure")
        
        with pytest.raises(Exception, match="Async test failure"):
            await circuit_breaker.async_call(async_failing_function)
        
        assert circuit_breaker.failure_count == 1
        
        # Check statistics
        stats = circuit_breaker.get_statistics()
        assert stats["statistics"]["failed_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_async_call_timeout(self, circuit_breaker):
        """Test async call timeout through circuit breaker."""
        async def slow_function():
            await asyncio.sleep(1.0)  # Longer than call_timeout (0.5s)
            return "slow result"
        
        with pytest.raises(asyncio.TimeoutError):
            await circuit_breaker.async_call(slow_function)
        
        assert circuit_breaker.failure_count == 1
    
    def test_failure_classification(self, circuit_breaker):
        """Test classification of different failure types."""
        # Test timeout error
        timeout_error = asyncio.TimeoutError("Timeout")
        failure_type = circuit_breaker._classify_failure(timeout_error)
        assert failure_type == FailureType.TIMEOUT
        
        # Test connection error
        connection_error = ConnectionError("Connection failed")
        failure_type = circuit_breaker._classify_failure(connection_error)
        assert failure_type == FailureType.CONNECTION_ERROR
        
        # Test authentication error
        auth_error = Exception("Authentication failed")
        failure_type = circuit_breaker._classify_failure(auth_error)
        assert failure_type == FailureType.AUTHENTICATION_ERROR
        
        # Test rate limit error
        rate_error = Exception("Rate limit exceeded")
        failure_type = circuit_breaker._classify_failure(rate_error)
        assert failure_type == FailureType.RATE_LIMIT_ERROR
        
        # Test unknown error
        unknown_error = Exception("Unknown error")
        failure_type = circuit_breaker._classify_failure(unknown_error)
        assert failure_type == FailureType.UNKNOWN_ERROR
    
    def test_reset_circuit(self, circuit_breaker):
        """Test resetting circuit breaker."""
        def failing_function():
            raise Exception("Test failure")
        
        # Open the circuit
        for i in range(circuit_breaker.config.failure_threshold):
            with pytest.raises(Exception):
                circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == circuit_breaker.config.failure_threshold
        
        # Reset the circuit
        circuit_breaker.reset()
        
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    def test_force_open_circuit(self, circuit_breaker):
        """Test forcing circuit breaker to open state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        
        # Force open
        circuit_breaker.force_open()
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Should fail fast
        def dummy_function():
            return "dummy"
        
        with pytest.raises(CircuitBreakerOpenException):
            circuit_breaker.call(dummy_function)
    
    def test_get_call_history(self, circuit_breaker):
        """Test getting call history."""
        def successful_function():
            return "success"
        
        def failing_function():
            raise Exception("Test failure")
        
        # Make some calls
        circuit_breaker.call(successful_function)
        
        try:
            circuit_breaker.call(failing_function)
        except Exception:
            pass
        
        circuit_breaker.call(successful_function)
        
        # Get call history
        history = circuit_breaker.get_call_history()
        
        assert len(history) == 3
        
        # Check history structure (newest first)
        assert history[0]["success"] is True
        assert history[1]["success"] is False
        assert history[2]["success"] is True
        
        # Check that all required fields are present
        for call in history:
            assert "timestamp" in call
            assert "success" in call
            assert "duration" in call
            assert "failure_type" in call or call["success"]
            assert "error" in call
    
    def test_statistics_tracking(self, circuit_breaker):
        """Test comprehensive statistics tracking."""
        def successful_function():
            return "success"
        
        def failing_function():
            raise Exception("Test failure")
        
        # Make various calls
        circuit_breaker.call(successful_function)
        circuit_breaker.call(successful_function)
        
        try:
            circuit_breaker.call(failing_function)
        except Exception:
            pass
        
        stats = circuit_breaker.get_statistics()
        
        # Check basic statistics
        assert stats["name"] == "test_circuit"
        assert stats["state"] == CircuitState.CLOSED.value
        assert stats["failure_count"] == 1
        
        # Check detailed statistics
        detailed_stats = stats["statistics"]
        assert detailed_stats["total_calls"] == 3
        assert detailed_stats["successful_calls"] == 2
        assert detailed_stats["failed_calls"] == 1
        assert detailed_stats["success_rate"] == (2/3) * 100
        assert detailed_stats["average_call_duration"] > 0
        
        # Check configuration
        config = stats["config"]
        assert config["failure_threshold"] == circuit_breaker.config.failure_threshold
        assert config["success_threshold"] == circuit_breaker.config.success_threshold


class TestCircuitBreakerManager:
    """Test cases for CircuitBreakerManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a circuit breaker manager for testing."""
        return CircuitBreakerManager()
    
    def test_get_circuit_breaker_new(self, manager):
        """Test getting a new circuit breaker."""
        cb = manager.get_circuit_breaker("test_service")
        
        assert cb.name == "test_service"
        assert cb.state == CircuitState.CLOSED
        
        # Should return the same instance on subsequent calls
        cb2 = manager.get_circuit_breaker("test_service")
        assert cb is cb2
    
    def test_get_circuit_breaker_with_config(self, manager):
        """Test getting circuit breaker with custom configuration."""
        config = CircuitBreakerConfig(failure_threshold=2, success_threshold=1)
        cb = manager.get_circuit_breaker("custom_service", config)
        
        assert cb.config.failure_threshold == 2
        assert cb.config.success_threshold == 1
    
    def test_infer_service_type(self, manager):
        """Test service type inference from name."""
        # Test printer service
        assert manager._infer_service_type("printer_service") == "printer"
        assert manager._infer_service_type("thermal_printer") == "printer"
        
        # Test API service
        assert manager._infer_service_type("wix_api") == "wix_api"
        assert manager._infer_service_type("external_api") == "wix_api"
        
        # Test SMTP service
        assert manager._infer_service_type("smtp_service") == "smtp"
        assert manager._infer_service_type("email_sender") == "smtp"
        assert manager._infer_service_type("mail_service") == "smtp"
        
        # Test database service
        assert manager._infer_service_type("database_connection") == "database"
        assert manager._infer_service_type("db_service") == "database"
        
        # Test unknown service
        assert manager._infer_service_type("unknown_service") == "default"
    
    def test_get_all_circuit_breakers(self, manager):
        """Test getting all circuit breakers."""
        # Initially empty
        all_cbs = manager.get_all_circuit_breakers()
        assert len(all_cbs) == 0
        
        # Add some circuit breakers
        cb1 = manager.get_circuit_breaker("service1")
        cb2 = manager.get_circuit_breaker("service2")
        
        all_cbs = manager.get_all_circuit_breakers()
        assert len(all_cbs) == 2
        assert "service1" in all_cbs
        assert "service2" in all_cbs
        assert all_cbs["service1"] is cb1
        assert all_cbs["service2"] is cb2
    
    def test_get_statistics(self, manager):
        """Test getting statistics for all circuit breakers."""
        # Add some circuit breakers and make calls
        cb1 = manager.get_circuit_breaker("service1")
        cb2 = manager.get_circuit_breaker("service2")
        
        def successful_function():
            return "success"
        
        cb1.call(successful_function)
        cb2.call(successful_function)
        
        stats = manager.get_statistics()
        
        assert len(stats) == 2
        assert "service1" in stats
        assert "service2" in stats
        
        # Check that each has statistics
        assert stats["service1"]["statistics"]["total_calls"] == 1
        assert stats["service2"]["statistics"]["total_calls"] == 1
    
    def test_reset_all(self, manager):
        """Test resetting all circuit breakers."""
        # Create circuit breakers and fail them
        cb1 = manager.get_circuit_breaker("service1")
        cb2 = manager.get_circuit_breaker("service2")
        
        def failing_function():
            raise Exception("Test failure")
        
        # Make some failures
        try:
            cb1.call(failing_function)
        except Exception:
            pass
        
        try:
            cb2.call(failing_function)
        except Exception:
            pass
        
        assert cb1.failure_count == 1
        assert cb2.failure_count == 1
        
        # Reset all
        manager.reset_all()
        
        assert cb1.failure_count == 0
        assert cb2.failure_count == 0
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED
    
    def test_remove_circuit_breaker(self, manager):
        """Test removing circuit breaker."""
        cb = manager.get_circuit_breaker("test_service")
        
        # Should exist
        all_cbs = manager.get_all_circuit_breakers()
        assert "test_service" in all_cbs
        
        # Remove it
        removed = manager.remove_circuit_breaker("test_service")
        assert removed is True
        
        # Should no longer exist
        all_cbs = manager.get_all_circuit_breakers()
        assert "test_service" not in all_cbs
        
        # Try to remove non-existing
        removed = manager.remove_circuit_breaker("non_existing")
        assert removed is False


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_get_circuit_breaker_global(self):
        """Test global get_circuit_breaker function."""
        cb = get_circuit_breaker("global_test")
        
        assert cb.name == "global_test"
        assert cb.state == CircuitState.CLOSED
        
        # Should return same instance
        cb2 = get_circuit_breaker("global_test")
        assert cb is cb2
    
    def test_circuit_breaker_decorator_sync(self):
        """Test circuit breaker decorator with sync function."""
        call_count = 0
        
        @circuit_breaker("decorator_test", CircuitBreakerConfig(failure_threshold=2))
        def decorated_function(should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise Exception("Decorator test failure")
            return f"success_{call_count}"
        
        # Successful call
        result = decorated_function()
        assert result == "success_1"
        
        # Failed calls
        with pytest.raises(Exception, match="Decorator test failure"):
            decorated_function(should_fail=True)
        
        with pytest.raises(Exception, match="Decorator test failure"):
            decorated_function(should_fail=True)
        
        # Circuit should now be open
        with pytest.raises(CircuitBreakerOpenException):
            decorated_function()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator_async(self):
        """Test circuit breaker decorator with async function."""
        call_count = 0
        
        @circuit_breaker("async_decorator_test", CircuitBreakerConfig(failure_threshold=2))
        async def decorated_async_function(should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise Exception("Async decorator test failure")
            return f"async_success_{call_count}"
        
        # Successful call
        result = await decorated_async_function()
        assert result == "async_success_1"
        
        # Failed calls
        with pytest.raises(Exception, match="Async decorator test failure"):
            await decorated_async_function(should_fail=True)
        
        with pytest.raises(Exception, match="Async decorator test failure"):
            await decorated_async_function(should_fail=True)
        
        # Circuit should now be open
        with pytest.raises(CircuitBreakerOpenException):
            await decorated_async_function()
    
    def test_specialized_circuit_breakers(self):
        """Test specialized circuit breaker functions."""
        # Test printer circuit breaker
        printer_cb = printer_circuit_breaker()
        assert printer_cb.name == "printer"
        assert printer_cb.config.failure_threshold == 5
        
        # Test Wix API circuit breaker
        wix_cb = wix_api_circuit_breaker()
        assert wix_cb.name == "wix_api"
        assert wix_cb.config.failure_threshold == 3
        
        # Test SMTP circuit breaker
        smtp_cb = smtp_circuit_breaker()
        assert smtp_cb.name == "smtp"
        assert smtp_cb.config.failure_threshold == 2
        
        # Test with custom names
        printer_cb2 = printer_circuit_breaker("thermal_printer")
        assert printer_cb2.name == "thermal_printer"
        assert printer_cb2 is not printer_cb


class TestIntegrationScenarios:
    """Integration test scenarios."""
    
    def test_circuit_breaker_with_retry_pattern(self):
        """Test circuit breaker combined with retry pattern."""
        call_count = 0
        
        @circuit_breaker("integration_test", CircuitBreakerConfig(failure_threshold=3))
        def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception(f"Failure {call_count}")
            return "success"
        
        # First two calls fail
        with pytest.raises(Exception, match="Failure 1"):
            flaky_service()
        
        with pytest.raises(Exception, match="Failure 2"):
            flaky_service()
        
        # Third call succeeds
        result = flaky_service()
        assert result == "success"
        
        # Circuit should still be closed (didn't reach failure threshold)
        cb = get_circuit_breaker("integration_test")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0  # Reset after success
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls(self):
        """Test multiple concurrent calls through circuit breaker."""
        cb = CircuitBreaker("concurrent_test", CircuitBreakerConfig(failure_threshold=5))
        
        call_results = []
        
        async def test_call(call_id: int, should_fail: bool = False):
            try:
                async def service_call():
                    if should_fail:
                        raise Exception(f"Call {call_id} failed")
                    return f"Call {call_id} success"
                
                result = await cb.async_call(service_call)
                call_results.append((call_id, "success", result))
            except Exception as e:
                call_results.append((call_id, "failed", str(e)))
        
        # Start multiple concurrent calls
        tasks = []
        for i in range(10):
            should_fail = i % 3 == 0  # Every 3rd call fails
            task = asyncio.create_task(test_call(i, should_fail))
            tasks.append(task)
        
        # Wait for all calls to complete
        await asyncio.gather(*tasks)
        
        # Analyze results
        successful_calls = [r for r in call_results if r[1] == "success"]
        failed_calls = [r for r in call_results if r[1] == "failed"]
        
        assert len(successful_calls) == 7  # 10 - 3 failures
        assert len(failed_calls) == 3
        
        # Circuit should still be closed (3 failures < 5 threshold)
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_breaker_recovery_cycle(self):
        """Test complete circuit breaker recovery cycle."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_duration=0.1  # Very short for testing
        )
        cb = CircuitBreaker("recovery_test", config)
        
        def failing_service():
            raise Exception("Service down")
        
        def recovering_service():
            return "service recovered"
        
        # Phase 1: Fail the service to open circuit
        for _ in range(config.failure_threshold):
            with pytest.raises(Exception):
                cb.call(failing_service)
        
        assert cb.state == CircuitState.OPEN
        
        # Phase 2: Verify fail-fast behavior
        with pytest.raises(CircuitBreakerOpenException):
            cb.call(failing_service)
        
        # Phase 3: Wait for timeout and transition to half-open
        time.sleep(config.timeout_duration + 0.05)
        
        # Phase 4: Make successful calls to close circuit
        for _ in range(config.success_threshold):
            result = cb.call(recovering_service)
            assert result == "service recovered"
        
        # Phase 5: Verify circuit is closed and working normally
        assert cb.state == CircuitState.CLOSED
        result = cb.call(recovering_service)
        assert result == "service recovered"
        
        # Check final statistics
        stats = cb.get_statistics()
        assert stats["statistics"]["circuit_opens"] == 1
        assert stats["statistics"]["circuit_closes"] == 1
        assert stats["statistics"]["total_failures_prevented"] == 1
