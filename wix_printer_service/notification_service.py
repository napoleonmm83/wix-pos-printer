"""
Email Notification Service for critical system errors and connectivity issues.
Provides intelligent notification throttling and template-based email generation.
"""
import asyncio
import logging
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import os

from .connectivity_monitor import ConnectivityEvent, ConnectivityEventType, ConnectivityStatus

logger = logging.getLogger(__name__)


class NotificationSeverity(Enum):
    """Notification severity levels."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(Enum):
    """Types of notifications."""
    PRINTER_OFFLINE = "printer_offline"
    PRINTER_ONLINE = "printer_online"
    INTERNET_OFFLINE = "internet_offline"
    INTERNET_ONLINE = "internet_online"
    SYSTEM_ERROR = "system_error"
    RECOVERY_FAILED = "recovery_failed"
    RECOVERY_COMPLETED = "recovery_completed"
    QUEUE_OVERFLOW = "queue_overflow"
    SERVICE_RESTART = "service_restart"


@dataclass
class NotificationConfig:
    """Configuration for notification settings."""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool = True
    from_email: str = ""
    to_emails: List[str] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.to_emails is None:
            self.to_emails = []
        if not self.from_email:
            self.from_email = self.smtp_username


@dataclass
class NotificationTemplate:
    """Template for notification emails."""
    notification_type: NotificationType
    severity: NotificationSeverity
    subject_template: str
    body_template: str
    html_template: Optional[str] = None
    throttle_minutes: int = 15
    max_per_hour: int = 4


@dataclass
class NotificationThrottle:
    """Throttling information for notifications."""
    notification_type: NotificationType
    last_sent: datetime
    count_in_hour: int
    count_in_day: int
    cooldown_until: Optional[datetime] = None


class NotificationService:
    """
    Service for sending email notifications about system errors and connectivity issues.
    Implements intelligent throttling to prevent email spam.
    """
    
    def __init__(self, config: NotificationConfig, database=None):
        """
        Initialize the notification service.
        
        Args:
            config: Notification configuration
            database: Optional database instance for logging
        """
        self.config = config
        self.database = database
        self._running = False
        self._notification_queue = asyncio.Queue()
        self._worker_task = None
        
        # Throttling tracking
        self._throttle_data: Dict[NotificationType, NotificationThrottle] = {}
        self._throttle_lock = threading.Lock()
        
        # Templates
        self._templates = self._initialize_templates()
        
        # Statistics
        self._stats = {
            "total_sent": 0,
            "total_throttled": 0,
            "total_failed": 0,
            "last_sent": None,
            "last_error": None
        }
        
        logger.info("Notification Service initialized")
    
    def _initialize_templates(self) -> Dict[NotificationType, NotificationTemplate]:
        """Initialize notification templates."""
        templates = {
            NotificationType.PRINTER_OFFLINE: NotificationTemplate(
                notification_type=NotificationType.PRINTER_OFFLINE,
                severity=NotificationSeverity.HIGH,
                subject_template="🖨️ Drucker Offline - {restaurant_name}",
                body_template="""
Drucker Offline Benachrichtigung

Zeitpunkt: {timestamp}
Restaurant: {restaurant_name}
Drucker Status: OFFLINE

Details:
- Letzte erfolgreiche Verbindung: {last_online}
- Fehlergrund: {error_reason}
- Betroffene Services: Druckaufträge werden in der Warteschlange gepuffert

Handlungsempfehlungen:
1. Überprüfen Sie die Drucker-Stromversorgung
2. Kontrollieren Sie die USB/Netzwerk-Verbindung
3. Starten Sie den Drucker neu falls erforderlich

Das System wird automatisch fortfahren, sobald der Drucker wieder verfügbar ist.

Wix Printer Service
                """.strip(),
                throttle_minutes=15,
                max_per_hour=4
            ),
            
            NotificationType.INTERNET_OFFLINE: NotificationTemplate(
                notification_type=NotificationType.INTERNET_OFFLINE,
                severity=NotificationSeverity.WARNING,
                subject_template="🌐 Internet Verbindung unterbrochen - {restaurant_name}",
                body_template="""
Internet Offline Benachrichtigung

Zeitpunkt: {timestamp}
Restaurant: {restaurant_name}
Internet Status: OFFLINE

Details:
- Letzte erfolgreiche Verbindung: {last_online}
- Betroffene Services: Wix API, Online-Bestellungen
- Offline-Modus: AKTIV (Bestellungen werden lokal gepuffert)

Aktuelle Situation:
- Lokale Bestellungen: {local_orders_count}
- Warteschlangen-Größe: {queue_size} Items
- Drucker Status: {printer_status}

Das System arbeitet im Offline-Modus weiter. Alle Bestellungen werden automatisch synchronisiert, sobald die Internetverbindung wiederhergestellt ist.

Wix Printer Service
                """.strip(),
                throttle_minutes=30,
                max_per_hour=2
            ),
            
            NotificationType.SYSTEM_ERROR: NotificationTemplate(
                notification_type=NotificationType.SYSTEM_ERROR,
                severity=NotificationSeverity.CRITICAL,
                subject_template="🚨 Kritischer Systemfehler - {restaurant_name}",
                body_template="""
Kritischer Systemfehler

Zeitpunkt: {timestamp}
Restaurant: {restaurant_name}
Fehlertyp: {error_type}

Fehlerdetails:
{error_message}

System Status:
- Service Status: {service_status}
- Drucker Status: {printer_status}
- Internet Status: {internet_status}
- Warteschlangen-Größe: {queue_size}

SOFORTIGE AUFMERKSAMKEIT ERFORDERLICH!

Bitte überprüfen Sie das System und kontaktieren Sie den Support falls erforderlich.

Wix Printer Service
                """.strip(),
                throttle_minutes=5,
                max_per_hour=12
            ),
            
            NotificationType.RECOVERY_FAILED: NotificationTemplate(
                notification_type=NotificationType.RECOVERY_FAILED,
                severity=NotificationSeverity.HIGH,
                subject_template="⚠️ Recovery Fehlgeschlagen - {restaurant_name}",
                body_template="""
Recovery Operation Fehlgeschlagen

Zeitpunkt: {timestamp}
Restaurant: {restaurant_name}
Recovery Typ: {recovery_type}

Recovery Details:
- Session ID: {session_id}
- Verarbeitete Items: {items_processed}
- Fehlgeschlagene Items: {items_failed}
- Fehlergrund: {error_message}

Warteschlangen Status:
- Verbleibende Items: {remaining_items}
- Ältester Item: {oldest_item_age}

Das System wird automatisch weitere Recovery-Versuche unternehmen. Überwachen Sie den Status über das Dashboard.

Wix Printer Service
                """.strip(),
                throttle_minutes=10,
                max_per_hour=6
            ),
            
            NotificationType.QUEUE_OVERFLOW: NotificationTemplate(
                notification_type=NotificationType.QUEUE_OVERFLOW,
                severity=NotificationSeverity.HIGH,
                subject_template="📊 Warteschlange Überlauf - {restaurant_name}",
                body_template="""
Warteschlange Überlauf Warnung

Zeitpunkt: {timestamp}
Restaurant: {restaurant_name}
Warteschlangen-Größe: {queue_size} Items

Warteschlangen Details:
- Kritische Items: {critical_items}
- Hohe Priorität: {high_priority_items}
- Normale Priorität: {normal_priority_items}
- Ältester Item: {oldest_item_age}

System Status:
- Drucker Status: {printer_status}
- Internet Status: {internet_status}
- Recovery Status: {recovery_status}

Handlungsempfehlungen:
1. Überprüfen Sie die Konnektivität (Drucker/Internet)
2. Überwachen Sie das Recovery-System
3. Erwägen Sie manuellen Eingriff bei anhaltenden Problemen

Wix Printer Service
                """.strip(),
                throttle_minutes=20,
                max_per_hour=3
            )
        }
        
        return templates
    
    async def start(self):
        """Start the notification service."""
        if self._running:
            logger.warning("Notification service is already running")
            return
        
        if not self.config.enabled:
            logger.info("Notification service is disabled")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Notification service started")
    
    async def stop(self):
        """Stop the notification service."""
        if not self._running:
            return
        
        self._running = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Notification service stopped")
    
    async def send_notification(self, notification_type: NotificationType, context: Dict[str, Any]):
        """
        Queue a notification for sending.
        
        Args:
            notification_type: Type of notification to send
            context: Context data for template rendering
        """
        if not self.config.enabled:
            logger.debug(f"Notification service disabled, skipping {notification_type.value}")
            return
        
        # Check throttling
        if self._is_throttled(notification_type):
            logger.info(f"Notification {notification_type.value} is throttled, skipping")
            self._stats["total_throttled"] += 1
            return
        
        # Add to queue
        notification_data = {
            "type": notification_type,
            "context": context,
            "timestamp": datetime.now()
        }
        
        await self._notification_queue.put(notification_data)
        logger.debug(f"Queued notification: {notification_type.value}")
    
    def handle_connectivity_event(self, event: ConnectivityEvent):
        """
        Handle connectivity events and send appropriate notifications.
        
        Args:
            event: Connectivity event from monitor
        """
        if not self._running:
            return
        
        try:
            notification_type = None
            context = {
                "timestamp": event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "restaurant_name": os.getenv("RESTAURANT_NAME", "Restaurant"),
                "component": event.component,
                "status": event.status.value
            }
            
            # Map connectivity events to notifications
            if event.event_type == ConnectivityEventType.PRINTER_OFFLINE:
                notification_type = NotificationType.PRINTER_OFFLINE
                context.update({
                    "last_online": self._get_last_online_time("printer"),
                    "error_reason": event.details.get("error", "Unbekannt") if event.details else "Unbekannt"
                })
            
            elif event.event_type == ConnectivityEventType.INTERNET_OFFLINE:
                notification_type = NotificationType.INTERNET_OFFLINE
                context.update({
                    "last_online": self._get_last_online_time("internet"),
                    "local_orders_count": self._get_local_orders_count(),
                    "queue_size": self._get_queue_size(),
                    "printer_status": self._get_printer_status()
                })
            
            if notification_type:
                # Use asyncio.create_task to avoid blocking
                asyncio.create_task(self.send_notification(notification_type, context))
        
        except Exception as e:
            logger.error(f"Error handling connectivity event: {e}")
    
    async def send_system_error_notification(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """
        Send a system error notification.
        
        Args:
            error_type: Type of system error
            error_message: Error message details
            context: Additional context information
        """
        notification_context = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "restaurant_name": os.getenv("RESTAURANT_NAME", "Restaurant"),
            "error_type": error_type,
            "error_message": error_message,
            "service_status": "ERROR",
            "printer_status": self._get_printer_status(),
            "internet_status": self._get_internet_status(),
            "queue_size": self._get_queue_size()
        }
        
        if context:
            notification_context.update(context)
        
        await self.send_notification(NotificationType.SYSTEM_ERROR, notification_context)
    
    async def send_recovery_notification(self, recovery_type: str, success: bool, session_data: Dict[str, Any]):
        """
        Send a recovery operation notification.
        
        Args:
            recovery_type: Type of recovery operation
            success: Whether recovery was successful
            session_data: Recovery session data
        """
        notification_type = NotificationType.RECOVERY_COMPLETED if success else NotificationType.RECOVERY_FAILED
        
        context = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "restaurant_name": os.getenv("RESTAURANT_NAME", "Restaurant"),
            "recovery_type": recovery_type,
            "session_id": session_data.get("session_id", "Unknown"),
            "items_processed": session_data.get("items_processed", 0),
            "items_failed": session_data.get("items_failed", 0),
            "remaining_items": self._get_queue_size(),
            "oldest_item_age": self._get_oldest_item_age()
        }
        
        if not success:
            context["error_message"] = session_data.get("error_message", "Unbekannter Fehler")
        
        await self.send_notification(notification_type, context)
    
    async def send_queue_overflow_notification(self, queue_size: int, queue_stats: Dict[str, Any]):
        """
        Send a queue overflow notification.
        
        Args:
            queue_size: Current queue size
            queue_stats: Queue statistics
        """
        context = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "restaurant_name": os.getenv("RESTAURANT_NAME", "Restaurant"),
            "queue_size": queue_size,
            "critical_items": queue_stats.get("critical_items", 0),
            "high_priority_items": queue_stats.get("high_priority_items", 0),
            "normal_priority_items": queue_stats.get("normal_priority_items", 0),
            "oldest_item_age": self._get_oldest_item_age(),
            "printer_status": self._get_printer_status(),
            "internet_status": self._get_internet_status(),
            "recovery_status": self._get_recovery_status()
        }
        
        await self.send_notification(NotificationType.QUEUE_OVERFLOW, context)
    
    def _is_throttled(self, notification_type: NotificationType) -> bool:
        """
        Check if a notification type is currently throttled.
        
        Args:
            notification_type: Type of notification to check
            
        Returns:
            True if throttled, False otherwise
        """
        with self._throttle_lock:
            now = datetime.now()
            template = self._templates.get(notification_type)
            
            if not template:
                return False
            
            throttle = self._throttle_data.get(notification_type)
            
            if not throttle:
                # First notification of this type
                self._throttle_data[notification_type] = NotificationThrottle(
                    notification_type=notification_type,
                    last_sent=now,
                    count_in_hour=0,
                    count_in_day=0
                )
                return False
            
            # Check cooldown
            if throttle.cooldown_until and now < throttle.cooldown_until:
                return True
            
            # Check time-based throttling
            time_since_last = now - throttle.last_sent
            if time_since_last < timedelta(minutes=template.throttle_minutes):
                return True
            
            # Check hourly limit
            hour_ago = now - timedelta(hours=1)
            if throttle.last_sent > hour_ago and throttle.count_in_hour >= template.max_per_hour:
                # Set cooldown until next hour
                throttle.cooldown_until = throttle.last_sent + timedelta(hours=1)
                return True
            
            # Reset hourly counter if more than an hour has passed
            if throttle.last_sent <= hour_ago:
                throttle.count_in_hour = 0
            
            # Reset daily counter if more than a day has passed
            day_ago = now - timedelta(days=1)
            if throttle.last_sent <= day_ago:
                throttle.count_in_day = 0
            
            return False
    
    def _update_throttle(self, notification_type: NotificationType):
        """Update throttling data after sending a notification."""
        with self._throttle_lock:
            now = datetime.now()
            throttle = self._throttle_data.get(notification_type)
            
            if throttle:
                throttle.last_sent = now
                throttle.count_in_hour += 1
                throttle.count_in_day += 1
                throttle.cooldown_until = None
    
    async def _worker_loop(self):
        """Main worker loop for processing notification queue."""
        logger.info("Notification worker loop started")
        
        while self._running:
            try:
                # Wait for notification with timeout
                notification_data = await asyncio.wait_for(
                    self._notification_queue.get(), timeout=1.0
                )
                
                await self._process_notification(notification_data)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except asyncio.CancelledError:
                logger.info("Notification worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in notification worker loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_notification(self, notification_data: Dict[str, Any]):
        """
        Process and send a single notification.
        
        Args:
            notification_data: Notification data from queue
        """
        try:
            notification_type = notification_data["type"]
            context = notification_data["context"]
            
            template = self._templates.get(notification_type)
            if not template:
                logger.error(f"No template found for notification type: {notification_type.value}")
                return
            
            # Render email content
            subject = template.subject_template.format(**context)
            body = template.body_template.format(**context)
            
            # Send email
            success = await self._send_email(subject, body, template.html_template)
            
            if success:
                self._update_throttle(notification_type)
                self._stats["total_sent"] += 1
                self._stats["last_sent"] = datetime.now()
                logger.info(f"Sent notification: {notification_type.value}")
                
                # Log to database if available
                if self.database:
                    self._log_notification(notification_type, context, success=True)
            else:
                self._stats["total_failed"] += 1
                logger.error(f"Failed to send notification: {notification_type.value}")
                
                if self.database:
                    self._log_notification(notification_type, context, success=False)
        
        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            self._stats["total_failed"] += 1
            self._stats["last_error"] = str(e)
    
    async def _send_email(self, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """
        Send an email using SMTP.
        
        Args:
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.from_email
            msg['To'] = ', '.join(self.config.to_emails)
            
            # Add plain text part
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False
    
    def _log_notification(self, notification_type: NotificationType, context: Dict[str, Any], success: bool):
        """Log notification to database."""
        try:
            if not self.database:
                return
            
            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT INTO notification_history 
                    (notification_type, context, success, sent_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    notification_type.value,
                    json.dumps(context),
                    success,
                    datetime.now().isoformat()
                ))
                conn.commit()
        
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
    
    def _get_last_online_time(self, component: str) -> str:
        """Get last online time for a component."""
        # This would query the connectivity events table
        return "Unbekannt"
    
    def _get_local_orders_count(self) -> int:
        """Get count of local orders."""
        # This would query the orders table for local orders
        return 0
    
    def _get_queue_size(self) -> int:
        """Get current queue size."""
        # This would query the offline queue
        return 0
    
    def _get_printer_status(self) -> str:
        """Get current printer status."""
        return "unknown"
    
    def _get_internet_status(self) -> str:
        """Get current internet status."""
        return "unknown"
    
    def _get_recovery_status(self) -> str:
        """Get current recovery status."""
        return "idle"
    
    def _get_oldest_item_age(self) -> str:
        """Get age of oldest queue item."""
        return "Unbekannt"
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get notification service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "statistics": self._stats.copy(),
            "throttle_status": {
                nt.value: {
                    "last_sent": throttle.last_sent.isoformat() if throttle.last_sent else None,
                    "count_in_hour": throttle.count_in_hour,
                    "count_in_day": throttle.count_in_day,
                    "cooldown_until": throttle.cooldown_until.isoformat() if throttle.cooldown_until else None
                }
                for nt, throttle in self._throttle_data.items()
            },
            "configuration": {
                "smtp_server": self.config.smtp_server,
                "smtp_port": self.config.smtp_port,
                "from_email": self.config.from_email,
                "to_emails_count": len(self.config.to_emails),
                "smtp_use_tls": self.config.smtp_use_tls
            }
        }
    
    async def test_email_connection(self) -> Dict[str, Any]:
        """
        Test email connection and configuration.
        
        Returns:
            Dictionary with test results
        """
        try:
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                
                return {
                    "success": True,
                    "message": "SMTP connection successful",
                    "server": f"{self.config.smtp_server}:{self.config.smtp_port}",
                    "tls": self.config.smtp_use_tls
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"SMTP connection failed: {str(e)}",
                "server": f"{self.config.smtp_server}:{self.config.smtp_port}",
                "error": str(e)
            }
