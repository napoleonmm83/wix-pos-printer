"""
Circuit Breaker implementation for protecting against cascading failures.
Implements circuit breaker pattern for external dependencies like printer, Wix API, and SMTP.
"""
import asyncio
import logging
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class FailureType(Enum):
    """Types of failures that can trigger circuit breaker."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    SERVICE_ERROR = "service_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Number of failures before opening
    success_threshold: int = 3  # Number of successes to close from half-open
    timeout_duration: float = 60.0  # Seconds to wait before trying half-open
    call_timeout: Optional[float] = 30.0  # Timeout for individual calls
    expected_exception: Optional[type] = None  # Expected exception type
    
    def __post_init__(self):
        """Validate configuration."""
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if self.success_threshold <= 0:
            raise ValueError("success_threshold must be positive")
        if self.timeout_duration <= 0:
            raise ValueError("timeout_duration must be positive")


@dataclass
class CircuitBreakerCall:
    """Information about a circuit breaker call."""
    timestamp: datetime
    success: bool
    duration: float
    failure_type: Optional[FailureType] = None
    error: Optional[Exception] = None


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_opens: int = 0
    circuit_closes: int = 0
    total_failures_prevented: int = 0
    average_call_duration: float = 0.0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    
    def __init__(self, circuit_name: str, failure_count: int, last_failure_time: datetime):
        self.circuit_name = circuit_name
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
        super().__init__(
            f"Circuit breaker '{circuit_name}' is OPEN. "
            f"Failed {failure_count} times. Last failure: {last_failure_time}"
        )


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, calls are allowed
    - OPEN: Circuit is open, calls fail fast
    - HALF_OPEN: Testing if the service has recovered
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        """Initialize circuit breaker."""
        self.name = name
        self.config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state_changed_time = datetime.now()
        self._lock = threading.Lock()
        
        # Call history for analysis
        self._call_history: List[CircuitBreakerCall] = []
        self._max_history_size = 1000
        
        # Statistics
        self._stats = CircuitBreakerStats()
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state
    
    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._failure_count
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function call through the circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result of function call
            
        Raises:
            CircuitBreakerOpenException: If circuit is open
            Exception: Original exception from function call
        """
        # Check if we can make the call
        self._check_state()
        
        start_time = time.time()
        call_record = CircuitBreakerCall(
            timestamp=datetime.now(),
            success=False,
            duration=0.0
        )
        
        try:
            # Execute the call with timeout if configured
            if self.config.call_timeout:
                if asyncio.iscoroutinefunction(func):
                    result = asyncio.wait_for(func(*args, **kwargs), timeout=self.config.call_timeout)
                else:
                    # For sync functions, we can't easily implement timeout
                    # This would require threading or process-based execution
                    result = func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Call succeeded
            call_record.success = True
            call_record.duration = time.time() - start_time
            
            self._record_success(call_record)
            return result
            
        except Exception as e:
            # Call failed
            call_record.success = False
            call_record.duration = time.time() - start_time
            call_record.error = e
            call_record.failure_type = self._classify_failure(e)
            
            self._record_failure(call_record)
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an async function call through the circuit breaker.
        
        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result of function call
            
        Raises:
            CircuitBreakerOpenException: If circuit is open
            Exception: Original exception from function call
        """
        # Check if we can make the call
        self._check_state()
        
        start_time = time.time()
        call_record = CircuitBreakerCall(
            timestamp=datetime.now(),
            success=False,
            duration=0.0
        )
        
        try:
            # Execute the async call with timeout if configured
            if self.config.call_timeout:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.call_timeout)
            else:
                result = await func(*args, **kwargs)
            
            # Call succeeded
            call_record.success = True
            call_record.duration = time.time() - start_time
            
            self._record_success(call_record)
            return result
            
        except Exception as e:
            # Call failed
            call_record.success = False
            call_record.duration = time.time() - start_time
            call_record.error = e
            call_record.failure_type = self._classify_failure(e)
            
            self._record_failure(call_record)
            raise e
    
    def _check_state(self):
        """Check current state and transition if necessary."""
        with self._lock:
            current_time = datetime.now()
            
            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                time_since_failure = (current_time - self._state_changed_time).total_seconds()
                
                if time_since_failure >= self.config.timeout_duration:
                    logger.info(f"Circuit breaker '{self.name}' transitioning from OPEN to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._state_changed_time = current_time
                    self._success_count = 0
                else:
                    # Still in open state, fail fast
                    self._stats.total_failures_prevented += 1
                    raise CircuitBreakerOpenException(
                        self.name,
                        self._failure_count,
                        self._last_failure_time or current_time
                    )
    
    def _record_success(self, call_record: CircuitBreakerCall):
        """Record a successful call."""
        with self._lock:
            # Add to history
            self._call_history.append(call_record)
            self._trim_history()
            
            # Update statistics
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = call_record.timestamp
            self._update_average_duration(call_record.duration)
            
            current_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(f"Circuit breaker '{self.name}' success in HALF_OPEN: {self._success_count}/{self.config.success_threshold}")
                
                if self._success_count >= self.config.success_threshold:
                    # Transition to closed
                    logger.info(f"Circuit breaker '{self.name}' transitioning from HALF_OPEN to CLOSED")
                    self._state = CircuitState.CLOSED
                    self._state_changed_time = current_time
                    self._failure_count = 0
                    self._success_count = 0
                    self._stats.circuit_closes += 1
            
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    logger.debug(f"Circuit breaker '{self.name}' resetting failure count after success")
                    self._failure_count = 0
    
    def _record_failure(self, call_record: CircuitBreakerCall):
        """Record a failed call."""
        with self._lock:
            # Add to history
            self._call_history.append(call_record)
            self._trim_history()
            
            # Update statistics
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = call_record.timestamp
            self._update_average_duration(call_record.duration)
            
            current_time = datetime.now()
            self._last_failure_time = current_time
            
            if self._state in [CircuitState.CLOSED, CircuitState.HALF_OPEN]:
                self._failure_count += 1
                logger.warning(f"Circuit breaker '{self.name}' failure: {self._failure_count}/{self.config.failure_threshold}")
                
                if self._failure_count >= self.config.failure_threshold:
                    # Transition to open
                    logger.error(f"Circuit breaker '{self.name}' transitioning to OPEN after {self._failure_count} failures")
                    self._state = CircuitState.OPEN
                    self._state_changed_time = current_time
                    self._stats.circuit_opens += 1
    
    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify the type of failure."""
        if isinstance(exception, asyncio.TimeoutError):
            return FailureType.TIMEOUT
        elif isinstance(exception, ConnectionError):
            return FailureType.CONNECTION_ERROR
        elif "authentication" in str(exception).lower() or "auth" in str(exception).lower():
            return FailureType.AUTHENTICATION_ERROR
        elif "rate limit" in str(exception).lower() or "too many requests" in str(exception).lower():
            return FailureType.RATE_LIMIT_ERROR
        elif hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            # HTTP-like error
            status_code = exception.response.status_code
            if 500 <= status_code < 600:
                return FailureType.SERVICE_ERROR
            elif status_code == 429:
                return FailureType.RATE_LIMIT_ERROR
            elif status_code in [401, 403]:
                return FailureType.AUTHENTICATION_ERROR
        
        return FailureType.UNKNOWN_ERROR
    
    def _trim_history(self):
        """Trim call history to maximum size."""
        if len(self._call_history) > self._max_history_size:
            self._call_history = self._call_history[-self._max_history_size:]
    
    def _update_average_duration(self, duration: float):
        """Update average call duration."""
        total_calls = self._stats.total_calls
        if total_calls == 1:
            self._stats.average_call_duration = duration
        else:
            # Running average
            self._stats.average_call_duration = (
                (self._stats.average_call_duration * (total_calls - 1) + duration) / total_calls
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "state_changed_time": self._state_changed_time.isoformat(),
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_duration": self.config.timeout_duration,
                    "call_timeout": self.config.call_timeout
                },
                "statistics": {
                    "total_calls": self._stats.total_calls,
                    "successful_calls": self._stats.successful_calls,
                    "failed_calls": self._stats.failed_calls,
                    "circuit_opens": self._stats.circuit_opens,
                    "circuit_closes": self._stats.circuit_closes,
                    "total_failures_prevented": self._stats.total_failures_prevented,
                    "average_call_duration": self._stats.average_call_duration,
                    "success_rate": (self._stats.successful_calls / max(1, self._stats.total_calls)) * 100,
                    "last_failure_time": self._stats.last_failure_time.isoformat() if self._stats.last_failure_time else None,
                    "last_success_time": self._stats.last_success_time.isoformat() if self._stats.last_success_time else None
                }
            }
    
    def get_call_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent call history."""
        with self._lock:
            history = self._call_history.copy()
        
        # Sort by timestamp (newest first) and limit
        history.sort(key=lambda x: x.timestamp, reverse=True)
        history = history[:limit]
        
        return [
            {
                "timestamp": call.timestamp.isoformat(),
                "success": call.success,
                "duration": call.duration,
                "failure_type": call.failure_type.value if call.failure_type else None,
                "error": str(call.error) if call.error else None
            }
            for call in history
        ]
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        with self._lock:
            logger.info(f"Resetting circuit breaker '{self.name}' to CLOSED state")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._state_changed_time = datetime.now()
    
    def force_open(self):
        """Force circuit breaker to open state."""
        with self._lock:
            logger.warning(f"Forcing circuit breaker '{self.name}' to OPEN state")
            self._state = CircuitState.OPEN
            self._state_changed_time = datetime.now()
            self._stats.circuit_opens += 1


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers for different services.
    """
    
    def __init__(self):
        """Initialize circuit breaker manager."""
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        
        # Default configurations for different service types
        self._default_configs = {
            "printer": CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_duration=30.0,
                call_timeout=10.0
            ),
            "wix_api": CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_duration=60.0,
                call_timeout=30.0
            ),
            "smtp": CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=1,
                timeout_duration=120.0,
                call_timeout=30.0
            ),
            "database": CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_duration=30.0,
                call_timeout=10.0
            )
        }
        
        logger.info("Circuit breaker manager initialized")
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get or create a circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Optional configuration (uses default if not provided)
            
        Returns:
            Circuit breaker instance
        """
        with self._lock:
            if name not in self._circuit_breakers:
                # Determine configuration
                if config is None:
                    # Try to find default config by service type
                    service_type = self._infer_service_type(name)
                    config = self._default_configs.get(service_type, CircuitBreakerConfig())
                
                # Create new circuit breaker
                self._circuit_breakers[name] = CircuitBreaker(name, config)
                logger.info(f"Created new circuit breaker: {name}")
            
            return self._circuit_breakers[name]
    
    def _infer_service_type(self, name: str) -> str:
        """Infer service type from circuit breaker name."""
        name_lower = name.lower()
        
        if "printer" in name_lower:
            return "printer"
        elif "wix" in name_lower or "api" in name_lower:
            return "wix_api"
        elif "smtp" in name_lower or "email" in name_lower or "mail" in name_lower:
            return "smtp"
        elif "database" in name_lower or "db" in name_lower:
            return "database"
        else:
            return "default"
    
    def get_all_circuit_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        with self._lock:
            return self._circuit_breakers.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers."""
        with self._lock:
            return {
                name: cb.get_statistics()
                for name, cb in self._circuit_breakers.items()
            }
    
    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self._circuit_breakers.values():
                cb.reset()
            logger.info("Reset all circuit breakers")
    
    def remove_circuit_breaker(self, name: str) -> bool:
        """Remove a circuit breaker."""
        with self._lock:
            if name in self._circuit_breakers:
                del self._circuit_breakers[name]
                logger.info(f"Removed circuit breaker: {name}")
                return True
            return False


# Global circuit breaker manager instance
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get or create a circuit breaker from the global manager."""
    return _circuit_breaker_manager.get_circuit_breaker(name, config)


def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """Decorator to wrap function calls with circuit breaker protection."""
    def decorator(func):
        cb = get_circuit_breaker(name, config)
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await cb.async_call(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return cb.call(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator


# Convenience functions for common circuit breakers
def printer_circuit_breaker(name: str = "printer") -> CircuitBreaker:
    """Get circuit breaker for printer operations."""
    return get_circuit_breaker(name, _circuit_breaker_manager._default_configs["printer"])


def wix_api_circuit_breaker(name: str = "wix_api") -> CircuitBreaker:
    """Get circuit breaker for Wix API operations."""
    return get_circuit_breaker(name, _circuit_breaker_manager._default_configs["wix_api"])


def smtp_circuit_breaker(name: str = "smtp") -> CircuitBreaker:
    """Get circuit breaker for SMTP operations."""
    return get_circuit_breaker(name, _circuit_breaker_manager._default_configs["smtp"])


def database_circuit_breaker(name: str = "database") -> CircuitBreaker:
    """Get circuit breaker for database operations."""
    return get_circuit_breaker(name, _circuit_breaker_manager._default_configs["database"])
