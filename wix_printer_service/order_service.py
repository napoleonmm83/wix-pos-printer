"""
Order processing service for handling Wix order data.
Provides validation, transformation, and storage of order data.
"""
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from .models import Order, PrintJob, OrderStatus, PrintJobStatus
from .database import Database
from .receipt_formatter import format_receipt, ReceiptType
from .offline_queue import OfflineQueueManager, QueuePriority

logger = logging.getLogger(__name__)


class OrderValidationError(Exception):
    """Exception raised when order validation fails."""
    pass


class OrderService:
    """
    Service for processing and managing orders from Wix API.
    Handles validation, transformation, and storage of order data.
    """
    
    def __init__(self, database: Database, connectivity_monitor=None):
        """
        Initialize the order service.
        
        Args:
            database: Database instance for data persistence
            connectivity_monitor: Optional connectivity monitor for offline detection
        """
        self.database = database
        self.connectivity_monitor = connectivity_monitor
        self.offline_queue = OfflineQueueManager(database)
        
        # Configuration for enabled receipt types
        self.enabled_receipt_types = self._get_enabled_receipt_types()
        
        # Offline mode configuration
        self.offline_mode = False
        self.local_order_counter = 0
        
        logger.info(f"Order service initialized with receipt types: {[rt.value for rt in self.enabled_receipt_types]}")
    
    def _get_enabled_receipt_types(self) -> List[ReceiptType]:
        """Get list of enabled receipt types from configuration."""
        enabled_types = []
        
        # Check environment variables for enabled receipt types
        if os.getenv('ENABLE_KITCHEN_RECEIPT', 'true').lower() == 'true':
            enabled_types.append(ReceiptType.KITCHEN)
        
        if os.getenv('ENABLE_DRIVER_RECEIPT', 'true').lower() == 'true':
            enabled_types.append(ReceiptType.DRIVER)
        
        if os.getenv('ENABLE_CUSTOMER_RECEIPT', 'true').lower() == 'true':
            enabled_types.append(ReceiptType.CUSTOMER)
        
        # Ensure at least one type is enabled
        if not enabled_types:
            enabled_types = [ReceiptType.KITCHEN]
            logger.warning("No receipt types enabled, defaulting to kitchen receipt")
        
        return enabled_types
    
    def process_webhook_order(self, webhook_data: Dict[str, Any]) -> Optional[Order]:
        """
        Process an order from webhook data.
        
        Args:
            webhook_data: Raw webhook data from Wix
            
        Returns:
            Processed Order instance or None if processing failed
        """
        try:
            # Validate webhook data structure
            self._validate_webhook_data(webhook_data)
            
            # Extract order data from webhook
            order_data = webhook_data.get('data', {})
            if not order_data:
                raise OrderValidationError("No order data found in webhook")
            
            # Validate order data
            self._validate_order(order)
            logger.info("Order validation complete, proceeding to database operations.")
            
            # Save order to database
            if self.database.save_order(order):
                logger.info(f"Order {order.id} saved successfully")
                
                # Create print jobs for all enabled receipt types
                print_jobs = self._create_print_jobs(order)
                jobs_created = 0
                
                for print_job in print_jobs:
                    job_id = self.database.save_print_job(print_job)
                    if job_id:
                        jobs_created += 1
                        logger.info(f"Print job {job_id} ({print_job.job_type}) created for order {order.id}")
                    else:
                        logger.error(f"Failed to save {print_job.job_type} print job for order {order.id}")
                
                logger.info(f"Created {jobs_created}/{len(print_jobs)} print jobs for order {order.id}")
                return order
            else:
                logger.error(f"Failed to save order {order.id}")
                return None
        except (OrderValidationError, ValueError) as e:
            logger.error(f"Order validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing webhook order: {e}")
            return None
    
    def _validate_webhook_data(self, webhook_data: Dict[str, Any]):
        """
        Validate the structure of webhook data.
        
        Args:
            webhook_data: Raw webhook data
            
        Raises:
            OrderValidationError: If validation fails
        """
        required_fields = ['eventType', 'data']
        
        for field in required_fields:
            if field not in webhook_data:
                raise OrderValidationError(f"Missing required webhook field: {field}")
        
        # Check if this is an order-related event
        event_type = webhook_data.get('eventType', '')
        if not event_type.startswith('orders/'):
            raise OrderValidationError(f"Invalid event type for order processing: {event_type}")
    
    def _validate_order(self, order: Order):
        """
        Validate order data for completeness and correctness.
        
        Args:
            order: Order instance to validate
            
        Raises:
            OrderValidationError: If validation fails
        """
        # Check required fields
        if not order.id or not isinstance(order.id, str):
            raise OrderValidationError("Order ID is required and must be a string")
        
        if not order.wix_order_id or not isinstance(order.wix_order_id, str):
            raise OrderValidationError("Wix Order ID is required and must be a string")
        
        if not order.items or not isinstance(order.items, list):
            raise OrderValidationError("Order must contain at least one item")
        
        # Validate order items
        for item in order.items:
            if not item.name:
                raise OrderValidationError(f"Item name is required for item {item.id}")
            
            if item.quantity <= 0:
                raise OrderValidationError(f"Item quantity must be positive for item {item.id}")
            
            if item.price < 0:
                raise OrderValidationError(f"Item price cannot be negative for item {item.id}")
        
        # Validate total amount
        if order.total_amount < 0:
            raise OrderValidationError("Order total amount cannot be negative")
        
        # Validate customer information (basic check)
        if not order.customer.email and not order.customer.phone:
            logger.warning(f"Order {order.id} has no customer contact information")
    
    def _create_print_jobs(self, order: Order) -> List[PrintJob]:
        """
        Create print jobs for an order using the receipt formatter.
        
        Args:
            order: Order instance to create print jobs for
            
        Returns:
            List of PrintJob instances
        """
        print_jobs = []
        
        try:
            for receipt_type in self.enabled_receipt_types:
                # Generate formatted receipt content
                content = format_receipt(order, receipt_type)
                
                # Create print job
                print_job = PrintJob(
                    order_id=order.id,
                    job_type=receipt_type.value,
                    status=PrintJobStatus.PENDING,
                    content=content
                )
                
                print_jobs.append(print_job)
                logger.debug(f"Created {receipt_type.value} print job for order {order.id}")
            
            return print_jobs
            
        except Exception as e:
            logger.error(f"Error creating print jobs for order {order.id}: {e}")
            return []
    
    def set_offline_mode(self, offline: bool):
        """
        Set offline mode status.
        
        Args:
            offline: True to enable offline mode, False to disable
        """
        if offline != self.offline_mode:
            self.offline_mode = offline
            logger.info(f"Order service offline mode: {'enabled' if offline else 'disabled'}")
    
    def is_offline_mode(self) -> bool:
        """Check if service is in offline mode."""
        # Check connectivity monitor if available
        if self.connectivity_monitor:
            return not self.connectivity_monitor.is_internet_online()
        
        return self.offline_mode
    
    def generate_local_order_id(self) -> str:
        """
        Generate a local order ID for offline operations.
        
        Returns:
            Local order ID
        """
        self.local_order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"LOCAL_{timestamp}_{self.local_order_counter:04d}"
    
    def process_offline_order(self, order_data: Dict[str, Any]) -> Optional[Order]:
        """
        Process an order in offline mode.
        
        Args:
            order_data: Order data from webhook
            
        Returns:
            Processed Order instance or None if processing failed
        """
        try:
            logger.info("Processing order in offline mode")
            
            # Generate local order ID if needed
            if 'id' not in order_data or not order_data['id']:
                order_data['id'] = self.generate_local_order_id()
            
            # Create Order instance
            order = Order.from_wix_data(order_data)
            
            # Mark as offline order
            order.status = OrderStatus.PENDING
            
            # Validate order data
            self._validate_order(order)
            
            # Save order to database
            if self.database.save_order(order):
                logger.info(f"Offline order {order.id} saved successfully")
                
                # Queue order for processing when online
                priority = self._determine_order_priority(order)
                if self.offline_queue.queue_order(order, priority):
                    logger.info(f"Order {order.id} queued for offline processing")
                
                # Create print jobs for offline queue
                print_jobs = self._create_print_jobs(order)
                jobs_queued = 0
                
                for print_job in print_jobs:
                    # Save print job to database
                    job_id = self.database.save_print_job(print_job)
                    if job_id:
                        # Queue print job for offline processing
                        job_priority = self._determine_print_job_priority(print_job)
                        if self.offline_queue.queue_print_job(print_job, job_priority):
                            jobs_queued += 1
                            logger.info(f"Print job {job_id} ({print_job.job_type}) queued for offline processing")
                
                logger.info(f"Queued {jobs_queued}/{len(print_jobs)} print jobs for offline processing")
                return order
            else:
                logger.error(f"Failed to save offline order {order.id}")
                return None
                
        except (OrderValidationError, ValueError) as e:
            logger.error(f"Offline order validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing offline order: {e}")
            return None
    
    def ingest_order_from_api(self, wix_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest a single order returned from the Wix API without duplicating print jobs.
        If the order is new, it will be saved and print jobs will be created.
        If the order already exists, it will be updated but print jobs will not be duplicated.

        Args:
            wix_data: Raw order data from Wix API response

        Returns:
            Dict with result info: { order_id, created_jobs, existing }
        """
        try:
            order = Order.from_wix_data(wix_data)
            # Validate order data
            self._validate_order(order)

            # Check if order already exists to avoid duplicate jobs
            existing_order = self.database.get_order(order.id)

            # Save (insert or update) order
            saved = self.database.save_order(order)
            created_jobs = 0

            if saved and existing_order is None:
                # Create print jobs only for new orders
                print_jobs = self._create_print_jobs(order)
                for print_job in print_jobs:
                    job_id = self.database.save_print_job(print_job)
                    if job_id:
                        created_jobs += 1

            return {
                "order_id": order.id,
                "created_jobs": created_jobs,
                "existing": existing_order is not None
            }

        except (OrderValidationError, ValueError) as e:
            logger.error(f"Order validation failed during ingest: {e}")
            return {"error": str(e), "order_id": wix_data.get('id', None)}
        except Exception as e:
            logger.error(f"Unexpected error ingesting order from API: {e}")
            return {"error": str(e), "order_id": wix_data.get('id', None)}

    
    def _determine_order_priority(self, order: Order) -> QueuePriority:
        """
        Determine priority for an order in the offline queue.
        
        Args:
            order: Order to prioritize
            
        Returns:
            Queue priority level
        """
        # High priority for large orders
        if order.total_amount > 100:
            return QueuePriority.HIGH
        
        # Critical priority for orders with special requirements
        if order.items:
            for item in order.items:
                if item.notes and any(keyword in item.notes.lower() for keyword in ['allergie', 'urgent', 'asap']):
                    return QueuePriority.CRITICAL
        
        return QueuePriority.NORMAL
    
    def _determine_print_job_priority(self, print_job: PrintJob) -> QueuePriority:
        """
        Determine priority for a print job in the offline queue.
        
        Args:
            print_job: Print job to prioritize
            
        Returns:
            Queue priority level
        """
        # Kitchen jobs have higher priority
        if print_job.job_type == 'kitchen':
            return QueuePriority.HIGH
        
        # Customer receipts have lower priority
        if print_job.job_type == 'customer':
            return QueuePriority.LOW
        
        return QueuePriority.NORMAL
    
    
    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """
        Retrieve an order by ID.
        
        Args:
            order_id: Order ID to retrieve
            
        Returns:
            Order instance or None if not found
        """
        return self.database.get_order(order_id)
    
    def get_orders_by_status(self, status: OrderStatus) -> list:
        """
        Retrieve orders by status.
        
        Args:
            status: Order status to filter by
            
        Returns:
            List of Order instances
        """
        return self.database.get_orders_by_status(status)

    def order_exists(self, wix_order_id: str) -> bool:
        """Check if an order with the given Wix Order ID already exists."""
        return self.database.get_order_by_wix_id(wix_order_id) is not None
