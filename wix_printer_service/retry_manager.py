"""
Intelligent Retry Manager for automatic retry of failed operations.
Implements exponential backoff with jitter and dead letter queue patterns.
"""
import asyncio
import logging
import random
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


class FailureType(Enum):
    """Types of failures that can be retried."""
    PRINTER_OFFLINE = "printer_offline"
    PRINTER_ERROR = "printer_error"
    NETWORK_ERROR = "network_error"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    TEMPORARY_ERROR = "temporary_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    initial_delay: float = 1.0  # seconds
    max_delay: float = 300.0  # 5 minutes
    backoff_factor: float = 2.0
    jitter_factor: float = 0.25  # ±25% randomization
    max_attempts: int = 5
    timeout: Optional[float] = None  # per-attempt timeout
    
    def __post_init__(self):
        """Validate configuration."""
        if self.initial_delay <= 0:
            raise ValueError("initial_delay must be positive")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")
        if self.backoff_factor <= 1.0:
            raise ValueError("backoff_factor must be > 1.0")
        if not 0 <= self.jitter_factor <= 1.0:
            raise ValueError("jitter_factor must be between 0 and 1")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    timestamp: datetime
    delay_before: float
    error: Optional[Exception] = None
    success: bool = False
    duration: Optional[float] = None


@dataclass
class RetryableTask:
    """A task that can be retried."""
    id: str
    operation: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    failure_type: FailureType = FailureType.UNKNOWN_ERROR
    config: Optional[RetryConfig] = None
    created_at: datetime = field(default_factory=datetime.now)
    attempts: List[RetryAttempt] = field(default_factory=list)
    last_error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def attempt_count(self) -> int:
        """Get number of attempts made."""
        return len(self.attempts)
    
    @property
    def is_exhausted(self) -> bool:
        """Check if retry attempts are exhausted."""
        if not self.config:
            return False
        return self.attempt_count >= self.config.max_attempts
    
    @property
    def last_attempt_time(self) -> Optional[datetime]:
        """Get timestamp of last attempt."""
        return self.attempts[-1].timestamp if self.attempts else None


class DeadLetterQueue:
    """Queue for permanently failed tasks."""
    
    def __init__(self, database=None):
        """Initialize dead letter queue."""
        self.database = database
        self._items: Dict[str, RetryableTask] = {}
        self._lock = threading.Lock()
    
    def add_task(self, task: RetryableTask):
        """Add a permanently failed task to dead letter queue."""
        with self._lock:
            self._items[task.id] = task
            logger.warning(f"Task {task.id} moved to dead letter queue after {task.attempt_count} attempts")
            
            # Log to database if available
            if self.database:
                self._log_dead_letter_task(task)
    
    def get_tasks(self) -> List[RetryableTask]:
        """Get all tasks in dead letter queue."""
        with self._lock:
            return list(self._items.values())
    
    def remove_task(self, task_id: str) -> Optional[RetryableTask]:
        """Remove task from dead letter queue."""
        with self._lock:
            return self._items.pop(task_id, None)
    
    def requeue_task(self, task_id: str) -> Optional[RetryableTask]:
        """Remove task from dead letter queue for requeuing."""
        task = self.remove_task(task_id)
        if task:
            # Reset attempts for requeuing
            task.attempts = []
            task.last_error = None
            logger.info(f"Task {task_id} requeued from dead letter queue")
        return task
    
    def clear(self):
        """Clear all tasks from dead letter queue."""
        with self._lock:
            count = len(self._items)
            self._items.clear()
            logger.info(f"Cleared {count} tasks from dead letter queue")
    
    def _log_dead_letter_task(self, task: RetryableTask):
        """Log dead letter task to database."""
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO retry_attempts 
                    (task_id, failure_type, attempts, last_error, created_at, dead_letter_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    task.id,
                    task.failure_type.value,
                    task.attempt_count,
                    str(task.last_error) if task.last_error else None,
                    task.created_at.isoformat(),
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log dead letter task: {e}")


class RetryManager:
    """
    Manages intelligent retry logic for failed operations.
    Implements exponential backoff with jitter and dead letter queue.
    """
    
    def __init__(self, database=None):
        """Initialize retry manager."""
        self.database = database
        self._running = False
        self._worker_task = None
        self._retry_queue = asyncio.Queue()
        self._active_retries: Dict[str, RetryableTask] = {}
        self._lock = threading.Lock()
        
        # Default configurations for different failure types
        self._default_configs = {
            FailureType.PRINTER_OFFLINE: RetryConfig(
                initial_delay=2.0,
                max_delay=60.0,
                backoff_factor=1.5,
                max_attempts=5
            ),
            FailureType.PRINTER_ERROR: RetryConfig(
                initial_delay=1.0,
                max_delay=30.0,
                backoff_factor=2.0,
                max_attempts=3
            ),
            FailureType.NETWORK_ERROR: RetryConfig(
                initial_delay=0.5,
                max_delay=60.0,
                backoff_factor=2.0,
                max_attempts=4
            ),
            FailureType.RESOURCE_UNAVAILABLE: RetryConfig(
                initial_delay=5.0,
                max_delay=300.0,
                backoff_factor=1.8,
                max_attempts=3
            ),
            FailureType.TEMPORARY_ERROR: RetryConfig(
                initial_delay=1.0,
                max_delay=120.0,
                backoff_factor=2.0,
                max_attempts=4
            ),
            FailureType.UNKNOWN_ERROR: RetryConfig(
                initial_delay=2.0,
                max_delay=60.0,
                backoff_factor=2.0,
                max_attempts=3
            )
        }
        
        # Dead letter queue
        self.dead_letter_queue = DeadLetterQueue(database)
        
        # Statistics
        self._stats = {
            "total_tasks": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "dead_letter_tasks": 0,
            "average_attempts": 0.0
        }
        
        logger.info("Retry Manager initialized")
    
    async def start(self):
        """Start the retry manager."""
        if self._running:
            logger.warning("Retry manager is already running")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Retry manager started")
    
    async def stop(self):
        """Stop the retry manager."""
        if not self._running:
            return

        self._running = False

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, RuntimeError):
                # Task was cancelled, timed out, or event loop is closed
                pass

        logger.info("Retry manager stopped")
    
    async def retry_operation(
        self,
        operation: Callable,
        *args,
        task_id: Optional[str] = None,
        failure_type: FailureType = FailureType.UNKNOWN_ERROR,
        config: Optional[RetryConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Retry an operation with intelligent backoff.
        
        Args:
            operation: Function to retry
            *args: Positional arguments for operation
            task_id: Optional task identifier
            failure_type: Type of failure for retry strategy
            config: Optional custom retry configuration
            metadata: Optional metadata for the task
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of successful operation
            
        Raises:
            Exception: If all retry attempts fail
        """
        if not task_id:
            task_id = f"retry_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Get or create retry configuration
        if not config:
            config = self._default_configs.get(failure_type, self._default_configs[FailureType.UNKNOWN_ERROR])
        
        # Create retryable task
        task = RetryableTask(
            id=task_id,
            operation=operation,
            args=args,
            kwargs=kwargs,
            failure_type=failure_type,
            config=config,
            metadata=metadata or {}
        )
        
        # Add to active retries
        with self._lock:
            self._active_retries[task_id] = task
        
        try:
            return await self._execute_with_retry(task)
        finally:
            # Remove from active retries
            with self._lock:
                self._active_retries.pop(task_id, None)
    
    async def queue_retry(self, task: RetryableTask):
        """Queue a task for retry."""
        await self._retry_queue.put(task)
    
    def get_active_retries(self) -> List[RetryableTask]:
        """Get list of currently active retry tasks."""
        with self._lock:
            return list(self._active_retries.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get retry manager statistics."""
        dead_letter_count = len(self.dead_letter_queue.get_tasks())
        
        return {
            "running": self._running,
            "active_retries": len(self._active_retries),
            "dead_letter_queue_size": dead_letter_count,
            "statistics": self._stats.copy(),
            "default_configs": {
                ft.value: {
                    "initial_delay": config.initial_delay,
                    "max_delay": config.max_delay,
                    "max_attempts": config.max_attempts,
                    "backoff_factor": config.backoff_factor
                }
                for ft, config in self._default_configs.items()
            }
        }
    
    async def _worker_loop(self):
        """Main worker loop for processing retry queue."""
        logger.info("Retry manager worker loop started")

        while self._running:
            try:
                # Wait for retry task with timeout
                task = await asyncio.wait_for(self._retry_queue.get(), timeout=1.0)
                await self._process_retry_task(task)

            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except asyncio.CancelledError:
                logger.info("Retry manager worker loop cancelled")
                break
            except (RuntimeError, GeneratorExit) as e:
                # Event loop is closed or task is being destroyed
                logger.info(f"Retry manager worker loop shutting down: {e}")
                break
            except Exception as e:
                logger.error(f"Error in retry manager worker loop: {e}")
                try:
                    await asyncio.sleep(1)
                except (RuntimeError, asyncio.CancelledError):
                    # Event loop closed during sleep, break out
                    break
    
    async def _process_retry_task(self, task: RetryableTask):
        """Process a single retry task."""
        try:
            result = await self._execute_with_retry(task)
            logger.info(f"Retry task {task.id} completed successfully after {task.attempt_count} attempts")
            self._stats["successful_retries"] += 1
            return result
            
        except Exception as e:
            logger.error(f"Retry task {task.id} failed permanently: {e}")
            self._stats["failed_retries"] += 1
            self.dead_letter_queue.add_task(task)
            self._stats["dead_letter_tasks"] += 1
    
    async def _execute_with_retry(self, task: RetryableTask) -> Any:
        """Execute a task with retry logic."""
        self._stats["total_tasks"] += 1
        
        while not task.is_exhausted:
            # Calculate delay for this attempt
            delay = self._calculate_delay(task)
            
            # Wait if this is not the first attempt
            if task.attempt_count > 0:
                logger.debug(f"Waiting {delay:.2f}s before retry attempt {task.attempt_count + 1} for task {task.id}")
                await asyncio.sleep(delay)
            
            # Create attempt record
            attempt = RetryAttempt(
                attempt_number=task.attempt_count + 1,
                timestamp=datetime.now(),
                delay_before=delay if task.attempt_count > 0 else 0
            )
            
            try:
                # Execute the operation
                start_time = time.time()
                
                if asyncio.iscoroutinefunction(task.operation):
                    result = await task.operation(*task.args, **task.kwargs)
                else:
                    result = task.operation(*task.args, **task.kwargs)
                
                # Success!
                attempt.success = True
                attempt.duration = time.time() - start_time
                task.attempts.append(attempt)
                
                logger.info(f"Task {task.id} succeeded on attempt {attempt.attempt_number}")
                self._log_retry_attempt(task, attempt)
                
                # Update statistics
                total_attempts = sum(len(t.attempts) for t in [task])
                self._stats["average_attempts"] = total_attempts / max(1, self._stats["total_tasks"])
                
                return result
                
            except Exception as e:
                # Failure
                attempt.error = e
                attempt.duration = time.time() - start_time
                task.attempts.append(attempt)
                task.last_error = e
                
                logger.warning(f"Task {task.id} failed on attempt {attempt.attempt_number}: {e}")
                self._log_retry_attempt(task, attempt)
                
                # Check if we should continue retrying
                if task.is_exhausted:
                    logger.error(f"Task {task.id} exhausted all {task.config.max_attempts} retry attempts")
                    raise e
        
        # This should not be reached, but just in case
        raise task.last_error or Exception("Retry attempts exhausted")
    
    def _calculate_delay(self, task: RetryableTask) -> float:
        """Calculate delay before next retry attempt."""
        if task.attempt_count == 0:
            return 0.0
        
        config = task.config
        attempt_number = task.attempt_count  # This will be the attempt we're about to make
        
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.initial_delay * (config.backoff_factor ** (attempt_number - 1))
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.initial_delay * attempt_number
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.initial_delay
        else:  # IMMEDIATE
            delay = 0.0
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Apply jitter
        if config.jitter_factor > 0:
            jitter_range = delay * config.jitter_factor
            jitter = random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay + jitter)
        
        return delay
    
    def _log_retry_attempt(self, task: RetryableTask, attempt: RetryAttempt):
        """Log retry attempt to database."""
        if not self.database:
            return
        
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO retry_attempts 
                    (task_id, attempt_number, timestamp, delay_before, success, duration, error_message, failure_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.id,
                    attempt.attempt_number,
                    attempt.timestamp.isoformat(),
                    attempt.delay_before,
                    attempt.success,
                    attempt.duration,
                    str(attempt.error) if attempt.error else None,
                    task.failure_type.value
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log retry attempt: {e}")


# Convenience functions for common retry patterns
async def retry_print_job(operation: Callable, *args, **kwargs) -> Any:
    """Retry a print job operation with printer-specific configuration."""
    manager = RetryManager()
    await manager.start()
    try:
        return await manager.retry_operation(
            operation,
            *args,
            failure_type=FailureType.PRINTER_ERROR,
            **kwargs
        )
    finally:
        await manager.stop()


async def retry_network_operation(operation: Callable, *args, **kwargs) -> Any:
    """Retry a network operation with network-specific configuration."""
    manager = RetryManager()
    await manager.start()
    try:
        return await manager.retry_operation(
            operation,
            *args,
            failure_type=FailureType.NETWORK_ERROR,
            **kwargs
        )
    finally:
        await manager.stop()


# Decorator for automatic retry
def auto_retry(
    failure_type: FailureType = FailureType.UNKNOWN_ERROR,
    config: Optional[RetryConfig] = None
):
    """Decorator to automatically retry function calls."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            manager = RetryManager()
            await manager.start()
            try:
                return await manager.retry_operation(
                    func,
                    *args,
                    failure_type=failure_type,
                    config=config,
                    **kwargs
                )
            finally:
                await manager.stop()
        
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
