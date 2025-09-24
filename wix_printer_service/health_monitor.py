"""
Service Health Monitor for system resource monitoring and proactive health management.
Monitors memory, CPU usage, and implements automatic resource cleanup.
"""
import asyncio
import gc
import logging
import os
import psutil
import threading
import time
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ResourceType(Enum):
    """Types of system resources."""
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    THREADS = "threads"
    WEBHOOK = "webhook"
    CONNECTIONS = "connections"
    PUBLIC_URL = "public_url"


@dataclass
class HealthThreshold:
    """Threshold configuration for health monitoring."""
    resource_type: ResourceType
    warning_threshold: float
    critical_threshold: float
    emergency_threshold: float
    check_interval: float = 30.0  # seconds
    enabled: bool = True
    
    def __post_init__(self):
        """Validate thresholds."""
        if not (0 <= self.warning_threshold <= self.critical_threshold <= self.emergency_threshold <= 100):
            raise ValueError("Thresholds must be in ascending order and between 0-100")


@dataclass
class HealthMetric:
    """A health metric measurement."""
    resource_type: ResourceType
    timestamp: datetime
    value: float
    status: HealthStatus
    threshold_config: HealthThreshold
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthEvent:
    """A health-related event."""
    event_type: str
    timestamp: datetime
    resource_type: ResourceType
    old_status: HealthStatus
    new_status: HealthStatus
    metric_value: float
    action_taken: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """
    Monitors system health and takes proactive measures to maintain service stability.
    Tracks memory, CPU, disk usage, and other system resources.
    """
    
    def __init__(self, database=None, notification_service=None):
        """Initialize health monitor."""
        self.database = database
        self.notification_service = notification_service
        self._running = False
        self._monitor_task = None
        self._lock = threading.Lock()
        
        # Current process for monitoring
        self._process = psutil.Process()
        
        # Health thresholds configuration
        self._thresholds = {
            ResourceType.MEMORY: HealthThreshold(
                resource_type=ResourceType.MEMORY,
                warning_threshold=70.0,    # 70% memory usage
                critical_threshold=85.0,   # 85% memory usage
                emergency_threshold=95.0,  # 95% memory usage
                check_interval=30.0
            ),
            ResourceType.CPU: HealthThreshold(
                resource_type=ResourceType.CPU,
                warning_threshold=70.0,    # 70% CPU usage
                critical_threshold=85.0,   # 85% CPU usage
                emergency_threshold=95.0,  # 95% CPU usage
                check_interval=60.0
            ),
            ResourceType.DISK: HealthThreshold(
                resource_type=ResourceType.DISK,
                warning_threshold=80.0,    # 80% disk usage
                critical_threshold=90.0,   # 90% disk usage
                emergency_threshold=95.0,  # 95% disk usage
                check_interval=300.0  # 5 minutes
            ),
            ResourceType.THREADS: HealthThreshold(
                resource_type=ResourceType.THREADS,
                warning_threshold=80.0,    # 80% of max threads
                critical_threshold=90.0,   # 90% of max threads
                emergency_threshold=95.0,  # 95% of max threads
                check_interval=60.0
            ),
            ResourceType.WEBHOOK: HealthThreshold(
                resource_type=ResourceType.WEBHOOK,
                warning_threshold=10.0,    # 10% webhook failure rate
                critical_threshold=25.0,   # 25% webhook failure rate
                emergency_threshold=50.0,  # 50% webhook failure rate
                check_interval=300.0,      # 5 minutes
                enabled=True
            ),
            ResourceType.PUBLIC_URL: HealthThreshold(
                resource_type=ResourceType.PUBLIC_URL,
                warning_threshold=5.0,     # 5% failure rate
                critical_threshold=15.0,   # 15% failure rate
                emergency_threshold=50.0,  # 50% failure rate
                check_interval=300.0,      # 5 minutes
                enabled=True
            )
        }
        
        # Health history
        self._health_history: List[HealthMetric] = []
        self._max_history_size = 1000
        
        # Event callbacks
        self._event_callbacks: List[Callable[[HealthEvent], None]] = []
        
        # Resource cleanup handlers
        self._cleanup_handlers: Dict[ResourceType, List[Callable[[], None]]] = {
            ResourceType.MEMORY: [self._perform_garbage_collection],
            ResourceType.CPU: [],
            ResourceType.DISK: [self._cleanup_temp_files],
            ResourceType.THREADS: [],
            ResourceType.WEBHOOK: [],
            ResourceType.PUBLIC_URL: []
        }
        
        # Webhook statistics tracking
        self._webhook_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "last_reset": datetime.now()
        }
        
        # Public URL statistics tracking
        self._public_url_stats = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "last_reset": datetime.now(),
            "last_ssl_check": None,
            "ssl_expiry_days": None
        }
        
        # Statistics
        self._stats = {
            "total_checks": 0,
            "warning_events": 0,
            "critical_events": 0,
            "emergency_events": 0,
            "cleanup_actions": 0,
            "last_check": None,
            "uptime_start": datetime.now()
        }
        
        logger.info("Health Monitor initialized")
    
    async def start(self):
        """Start health monitoring."""
        if self._running:
            logger.warning("Health monitor is already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitor started")
    
    async def stop(self):
        """Stop health monitoring."""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitor stopped")
    
    def add_event_callback(self, callback: Callable[[HealthEvent], None]):
        """Add callback for health events."""
        self._event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[HealthEvent], None]):
        """Remove event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
    
    def add_cleanup_handler(self, resource_type: ResourceType, handler: Callable[[], None]):
        """Add custom cleanup handler for resource type."""
        if resource_type not in self._cleanup_handlers:
            self._cleanup_handlers[resource_type] = []
        self._cleanup_handlers[resource_type].append(handler)
    
    def get_current_health(self) -> Dict[str, Any]:
        """Get current health status for all monitored resources."""
        health_data = {}
        
        for resource_type in ResourceType:
            if resource_type in self._thresholds and self._thresholds[resource_type].enabled:
                try:
                    metric = self._collect_metric(resource_type)
                    health_data[resource_type.value] = {
                        "value": metric.value,
                        "status": metric.status.value,
                        "timestamp": metric.timestamp.isoformat(),
                        "thresholds": {
                            "warning": metric.threshold_config.warning_threshold,
                            "critical": metric.threshold_config.critical_threshold,
                            "emergency": metric.threshold_config.emergency_threshold
                        },
                        "metadata": metric.metadata
                    }
                except Exception as e:
                    health_data[resource_type.value] = {
                        "error": str(e),
                        "status": "unknown"
                    }
        
        return health_data
    
    def get_health_history(self, resource_type: Optional[ResourceType] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for analysis."""
        with self._lock:
            history = self._health_history.copy()
        
        if resource_type:
            history = [h for h in history if h.resource_type == resource_type]
        
        # Sort by timestamp (newest first) and limit
        history.sort(key=lambda x: x.timestamp, reverse=True)
        history = history[:limit]
        
        return [
            {
                "resource_type": h.resource_type.value,
                "timestamp": h.timestamp.isoformat(),
                "value": h.value,
                "status": h.status.value,
                "metadata": h.metadata
            }
            for h in history
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get health monitor statistics."""
        uptime = datetime.now() - self._stats["uptime_start"]
        
        return {
            "running": self._running,
            "uptime_seconds": uptime.total_seconds(),
            "statistics": self._stats.copy(),
            "thresholds": {
                rt.value: {
                    "warning": th.warning_threshold,
                    "critical": th.critical_threshold,
                    "emergency": th.emergency_threshold,
                    "enabled": th.enabled,
                    "check_interval": th.check_interval
                }
                for rt, th in self._thresholds.items()
            },
            "cleanup_handlers": {
                rt.value: len(handlers)
                for rt, handlers in self._cleanup_handlers.items()
            }
        }
    
    def update_threshold(self, resource_type: ResourceType, threshold: HealthThreshold):
        """Update health threshold for a resource type."""
        self._thresholds[resource_type] = threshold
        logger.info(f"Updated health threshold for {resource_type.value}")
    
    async def force_health_check(self) -> Dict[str, Any]:
        """Force immediate health check for all resources."""
        logger.info("Forcing immediate health check")
        results = {}
        
        for resource_type in ResourceType:
            if resource_type in self._thresholds and self._thresholds[resource_type].enabled:
                try:
                    metric = self._collect_metric(resource_type)
                    await self._process_metric(metric)
                    results[resource_type.value] = {
                        "value": metric.value,
                        "status": metric.status.value
                    }
                except Exception as e:
                    results[resource_type.value] = {"error": str(e)}
        
        return results
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Health monitor loop started")
        
        # Track last check times for each resource
        last_checks = {rt: datetime.now() for rt in self._thresholds.keys()}
        
        while self._running:
            try:
                current_time = datetime.now()
                
                # Check each resource type based on its interval
                for resource_type, threshold in self._thresholds.items():
                    if not threshold.enabled:
                        continue
                    
                    time_since_last = (current_time - last_checks[resource_type]).total_seconds()
                    
                    if time_since_last >= threshold.check_interval:
                        try:
                            metric = self._collect_metric(resource_type)
                            await self._process_metric(metric)
                            last_checks[resource_type] = current_time
                            
                        except Exception as e:
                            logger.error(f"Error checking {resource_type.value} health: {e}")
                
                self._stats["total_checks"] += 1
                self._stats["last_check"] = current_time.isoformat()
                
                # Sleep for a short interval before next check
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                logger.info("Health monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(30)  # Wait longer on error
    
    def _collect_metric(self, resource_type: ResourceType) -> HealthMetric:
        """Collect a single health metric."""
        threshold = self._thresholds[resource_type]
        timestamp = datetime.now()
        
        if resource_type == ResourceType.MEMORY:
            # Memory usage percentage
            memory_info = self._process.memory_info()
            system_memory = psutil.virtual_memory()
            memory_percent = (memory_info.rss / system_memory.total) * 100
            
            metadata = {
                "rss_bytes": memory_info.rss,
                "vms_bytes": memory_info.vms,
                "system_total_bytes": system_memory.total,
                "system_available_bytes": system_memory.available,
                "system_percent": system_memory.percent
            }
            
            value = memory_percent
            
        elif resource_type == ResourceType.CPU:
            # CPU usage percentage (averaged over 1 second)
            cpu_percent = self._process.cpu_percent(interval=1.0)
            system_cpu = psutil.cpu_percent(interval=None)
            
            metadata = {
                "process_cpu_percent": cpu_percent,
                "system_cpu_percent": system_cpu,
                "cpu_count": psutil.cpu_count(),
                "cpu_times": dict(self._process.cpu_times()._asdict())
            }
            
            value = cpu_percent
            
        elif resource_type == ResourceType.DISK:
            # Disk usage percentage
            try:
                disk_usage = psutil.disk_usage('/')
                disk_percent = (disk_usage.used / disk_usage.total) * 100
                
                metadata = {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free
                }
                
                value = disk_percent
            except Exception:
                # Fallback for Windows
                disk_usage = psutil.disk_usage('C:')
                disk_percent = (disk_usage.used / disk_usage.total) * 100
                
                metadata = {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free
                }
                
                value = disk_percent
                
        elif resource_type == ResourceType.THREADS:
            # Thread count percentage of system limit
            thread_count = self._process.num_threads()
            # Estimate max threads (this is system dependent)
            max_threads = 1000  # Conservative estimate
            thread_percent = (thread_count / max_threads) * 100
            
            metadata = {
                "thread_count": thread_count,
                "estimated_max_threads": max_threads
            }
            
            value = thread_percent
            
        elif resource_type == ResourceType.WEBHOOK:
            # Webhook failure rate percentage
            total = self._webhook_stats["total_requests"]
            failed = self._webhook_stats["failed_requests"]
            
            if total > 0:
                failure_rate = (failed / total) * 100
            else:
                failure_rate = 0.0
            
            metadata = {
                "total_requests": total,
                "successful_requests": self._webhook_stats["successful_requests"],
                "failed_requests": failed,
                "success_rate": 100 - failure_rate if total > 0 else 100,
                "last_reset": self._webhook_stats["last_reset"].isoformat()
            }
            
            value = failure_rate
            
        elif resource_type == ResourceType.PUBLIC_URL:
            # Public URL failure rate percentage
            total = self._public_url_stats["total_checks"]
            failed = self._public_url_stats["failed_checks"]
            
            if total > 0:
                failure_rate = (failed / total) * 100
            else:
                failure_rate = 0.0
            
            # Get current public URL status
            try:
                from .public_url_monitor import get_public_url_monitor
                monitor = get_public_url_monitor()
                
                if monitor.is_configured():
                    health_metrics = monitor.get_health_metrics()
                    ssl_info = health_metrics.get("ssl_certificate", {})
                    
                    metadata = {
                        "total_checks": total,
                        "successful_checks": self._public_url_stats["successful_checks"],
                        "failed_checks": failed,
                        "success_rate": 100 - failure_rate if total > 0 else 100,
                        "domain": health_metrics.get("domain"),
                        "status": health_metrics.get("status"),
                        "dns_resolved_ip": health_metrics.get("dns_resolved_ip"),
                        "ssl_valid": ssl_info.get("valid", False),
                        "ssl_days_until_expiry": ssl_info.get("days_until_expiry"),
                        "last_reset": self._public_url_stats["last_reset"].isoformat()
                    }
                else:
                    metadata = {
                        "configured": False,
                        "message": "Public URL monitoring not configured"
                    }
                    failure_rate = 0.0  # Not configured is not a failure
                    
            except ImportError:
                metadata = {
                    "error": "Public URL monitor not available"
                }
                failure_rate = 0.0
            
            value = failure_rate
            
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
        
        # Determine health status
        if value >= threshold.emergency_threshold:
            status = HealthStatus.EMERGENCY
        elif value >= threshold.critical_threshold:
            status = HealthStatus.CRITICAL
        elif value >= threshold.warning_threshold:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.HEALTHY
        
        return HealthMetric(
            resource_type=resource_type,
            timestamp=timestamp,
            value=value,
            status=status,
            threshold_config=threshold,
            metadata=metadata
        )
    
    async def _process_metric(self, metric: HealthMetric):
        """Process a collected metric and take appropriate actions."""
        # Add to history
        with self._lock:
            self._health_history.append(metric)
            # Trim history if too large
            if len(self._health_history) > self._max_history_size:
                self._health_history = self._health_history[-self._max_history_size:]
        
        # Log metric
        self._log_metric(metric)
        
        # Check if status has changed from last metric of same type
        previous_status = self._get_previous_status(metric.resource_type)
        
        if previous_status != metric.status:
            # Status changed, create event
            event = HealthEvent(
                event_type="status_change",
                timestamp=metric.timestamp,
                resource_type=metric.resource_type,
                old_status=previous_status,
                new_status=metric.status,
                metric_value=metric.value
            )
            
            # Take action based on new status
            action_taken = await self._handle_status_change(metric, event)
            event.action_taken = action_taken
            
            # Fire event callbacks
            for callback in self._event_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in health event callback: {e}")
            
            # Update statistics
            if metric.status == HealthStatus.WARNING:
                self._stats["warning_events"] += 1
            elif metric.status == HealthStatus.CRITICAL:
                self._stats["critical_events"] += 1
            elif metric.status == HealthStatus.EMERGENCY:
                self._stats["emergency_events"] += 1
    
    async def _handle_status_change(self, metric: HealthMetric, event: HealthEvent) -> Optional[str]:
        """Handle health status changes and take appropriate actions."""
        actions_taken = []
        
        if metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL, HealthStatus.EMERGENCY]:
            logger.warning(
                f"Health {metric.status.value} for {metric.resource_type.value}: "
                f"{metric.value:.1f}% (threshold: {getattr(metric.threshold_config, f'{metric.status.value}_threshold')}%)"
            )
            
            # Perform resource-specific cleanup
            if metric.resource_type in self._cleanup_handlers:
                for handler in self._cleanup_handlers[metric.resource_type]:
                    try:
                        handler()
                        actions_taken.append(f"cleanup_{metric.resource_type.value}")
                        self._stats["cleanup_actions"] += 1
                    except Exception as e:
                        logger.error(f"Error in cleanup handler for {metric.resource_type.value}: {e}")
            
            # Send notification for critical and emergency statuses
            if metric.status in [HealthStatus.CRITICAL, HealthStatus.EMERGENCY] and self.notification_service:
                try:
                    await self._send_health_notification(metric, event)
                    actions_taken.append("notification_sent")
                except Exception as e:
                    logger.error(f"Error sending health notification: {e}")
        
        elif metric.status == HealthStatus.HEALTHY and event.old_status != HealthStatus.HEALTHY:
            logger.info(f"Health recovered for {metric.resource_type.value}: {metric.value:.1f}%")
            
            # Send recovery notification
            if self.notification_service:
                try:
                    await self._send_recovery_notification(metric, event)
                    actions_taken.append("recovery_notification_sent")
                except Exception as e:
                    logger.error(f"Error sending recovery notification: {e}")
        
        return ", ".join(actions_taken) if actions_taken else None
    
    def _get_previous_status(self, resource_type: ResourceType) -> HealthStatus:
        """Get the previous health status for a resource type."""
        with self._lock:
            # Find the most recent metric for this resource type (excluding the current one)
            for metric in reversed(self._health_history[:-1]):
                if metric.resource_type == resource_type:
                    return metric.status
        
        # Default to healthy if no previous status
        return HealthStatus.HEALTHY
    
    def _perform_garbage_collection(self):
        """Perform garbage collection to free memory."""
        logger.info("Performing garbage collection")
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
    
    def _cleanup_temp_files(self):
        """Clean up temporary files to free disk space."""
        logger.info("Cleaning up temporary files")
        # This is a placeholder - implement actual temp file cleanup
        # Be very careful with file deletion in production
        pass
    
    async def _send_health_notification(self, metric: HealthMetric, event: HealthEvent):
        """Send health alert notification."""
        if not self.notification_service:
            return
        
        from .notification_service import NotificationType
        
        context = {
            "timestamp": metric.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "restaurant_name": os.getenv("RESTAURANT_NAME", "Restaurant"),
            "resource_type": metric.resource_type.value,
            "health_status": metric.status.value,
            "metric_value": f"{metric.value:.1f}%",
            "threshold": f"{getattr(metric.threshold_config, f'{metric.status.value}_threshold')}%",
            "metadata": metric.metadata,
            "action_taken": event.action_taken or "monitoring"
        }
        
        await self.notification_service.send_notification(
            NotificationType.SYSTEM_ERROR,
            context
        )
    
    async def _send_recovery_notification(self, metric: HealthMetric, event: HealthEvent):
        """Send health recovery notification."""
        if not self.notification_service:
            return
        
        from .notification_service import NotificationType
        
        context = {
            "timestamp": metric.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "restaurant_name": os.getenv("RESTAURANT_NAME", "Restaurant"),
            "resource_type": metric.resource_type.value,
            "health_status": "recovered",
            "metric_value": f"{metric.value:.1f}%",
            "previous_status": event.old_status.value
        }
        
        # Send as info-level notification
        await self.notification_service.send_notification(
            NotificationType.RECOVERY_COMPLETED,
            context
        )
    
    def _log_metric(self, metric: HealthMetric):
        """Log health metric to database."""
        if not self.database:
            return
        
        try:
            with self.database.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO health_metrics 
                        (metric_name, timestamp, value, status, tags)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        metric.resource_type.value,
                        metric.timestamp,
                        metric.value,
                        metric.status.value,
                        json.dumps(metric.metadata) if metric.metadata else None
                    ))
        except Exception as e:
            logger.error(f"Failed to log health metric: {e}")
    
    def record_webhook_request(self, success: bool):
        """Record a webhook request for health monitoring."""
        with self._lock:
            self._webhook_stats["total_requests"] += 1
            if success:
                self._webhook_stats["successful_requests"] += 1
            else:
                self._webhook_stats["failed_requests"] += 1
    
    def reset_webhook_stats(self):
        """Reset webhook statistics (useful for periodic resets)."""
        with self._lock:
            self._webhook_stats = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "last_reset": datetime.now()
            }
            logger.info("Webhook statistics reset")
    
    def get_webhook_stats(self) -> Dict[str, Any]:
        """Get current webhook statistics."""
        with self._lock:
            return self._webhook_stats.copy()
    
    def record_public_url_check(self, success: bool):
        """Record a public URL check for health monitoring."""
        with self._lock:
            self._public_url_stats["total_checks"] += 1
            if success:
                self._public_url_stats["successful_checks"] += 1
            else:
                self._public_url_stats["failed_checks"] += 1
    
    def update_ssl_status(self, days_until_expiry: Optional[int]):
        """Update SSL certificate expiry information."""
        with self._lock:
            self._public_url_stats["last_ssl_check"] = datetime.now()
            self._public_url_stats["ssl_expiry_days"] = days_until_expiry
    
    def reset_public_url_stats(self):
        """Reset public URL statistics (useful for periodic resets)."""
        with self._lock:
            self._public_url_stats = {
                "total_checks": 0,
                "successful_checks": 0,
                "failed_checks": 0,
                "last_reset": datetime.now(),
                "last_ssl_check": None,
                "ssl_expiry_days": None
            }
            logger.info("Public URL statistics reset")
    
    def get_public_url_stats(self) -> Dict[str, Any]:
        """Get current public URL statistics."""
        with self._lock:
            return self._public_url_stats.copy()


# Convenience function for getting system health
def get_system_health() -> Dict[str, Any]:
    """Get current system health without starting a full monitor."""
    try:
        process = psutil.Process()
        
        # Memory
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        memory_percent = (memory_info.rss / system_memory.total) * 100
        
        # CPU
        cpu_percent = process.cpu_percent(interval=1.0)
        
        # Disk
        try:
            disk_usage = psutil.disk_usage('/')
        except:
            disk_usage = psutil.disk_usage('C:')
        disk_percent = (disk_usage.used / disk_usage.total) * 100
        
        return {
            "memory_percent": memory_percent,
            "cpu_percent": cpu_percent,
            "disk_percent": disk_percent,
            "thread_count": process.num_threads(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}
