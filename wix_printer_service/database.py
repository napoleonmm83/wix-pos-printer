"""
Database management for the Wix Printer Service.
Handles SQLite database initialization and CRUD operations.
"""
import sqlite3
import logging
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import Order, PrintJob, OrderStatus, PrintJobStatus, OrderItem, CustomerInfo, DeliveryInfo

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass


class Database:
    """
    SQLite database manager for orders and print jobs.
    Handles database initialization, connections, and CRUD operations.
    """
    
    def __init__(self, db_path: str = "wix_printer_service.db"):
        """
        Initialize database connection and create tables if needed.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection = None
        self._initialize_database()
        logger.info(f"Database initialized at {db_path}")
    
    def _initialize_database(self):
        """Create database tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Create orders table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id TEXT PRIMARY KEY,
                        wix_order_id TEXT UNIQUE NOT NULL,
                        status TEXT NOT NULL,
                        items_json TEXT NOT NULL,
                        customer_json TEXT NOT NULL,
                        delivery_json TEXT NOT NULL,
                        total_amount REAL NOT NULL,
                        currency TEXT NOT NULL DEFAULT 'EUR',
                        order_date TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        raw_data_json TEXT
                    )
                """)
                
                # Create print_jobs table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS print_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id TEXT NOT NULL,
                        job_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        content TEXT NOT NULL,
                        printer_name TEXT,
                        attempts INTEGER DEFAULT 0,
                        max_attempts INTEGER DEFAULT 3,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        printed_at TEXT,
                        error_message TEXT,
                        FOREIGN KEY (order_id) REFERENCES orders (id)
                    )
                """)
                
                # Create health_metrics table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS health_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        value REAL NOT NULL,
                        tags TEXT,
                        resource_type TEXT
                    )
                """)
                
                # Create circuit_breaker_failures table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS circuit_breaker_failures (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        breaker_name TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_wix_id ON orders(wix_order_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_print_jobs_order_id ON print_jobs(order_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_print_jobs_status ON print_jobs(status)")
                
                conn.commit()
                logger.info("Database tables created successfully")
                
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def save_order(self, order: Order) -> bool:
        """
        Save an order to the database.
        
        Args:
            order: Order instance to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                order_dict = order.to_dict()
                
                # Insert or replace order
                conn.execute("""
                    INSERT OR REPLACE INTO orders (
                        id, wix_order_id, status, items_json, customer_json,
                        delivery_json, total_amount, currency, order_date,
                        created_at, updated_at, raw_data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_dict['id'], order_dict['wix_order_id'], order_dict['status'],
                    order_dict['items_json'], order_dict['customer_json'],
                    order_dict['delivery_json'], order_dict['total_amount'],
                    order_dict['currency'], order_dict['order_date'],
                    order_dict['created_at'], order_dict['updated_at'],
                    order_dict['raw_data_json']
                ))
                
                conn.commit()
                logger.info(f"Order {order.id} saved successfully")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error saving order {order.id}: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Retrieve an order by ID.
        
        Args:
            order_id: Order ID to retrieve
            
        Returns:
            Order instance or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM orders WHERE id = ?", (order_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_order(row)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving order {order_id}: {e}")
            return None
    
    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """
        Retrieve orders by status.
        
        Args:
            status: Order status to filter by
            
        Returns:
            List of Order instances
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
                    (status.value,)
                )
                rows = cursor.fetchall()
                
                return [self._row_to_order(row) for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving orders by status {status}: {e}")
            return []
    
    def save_print_job(self, print_job: PrintJob) -> Optional[str]:
        """
        Save a print job to the database.
        
        Args:
            print_job: PrintJob instance to save
            
        Returns:
            Print job ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                job_dict = print_job.to_dict()
                
                if print_job.id:
                    # Update existing job
                    conn.execute("""
                        UPDATE print_jobs SET
                            order_id = ?, job_type = ?, status = ?, content = ?,
                            printer_name = ?, attempts = ?, max_attempts = ?,
                            updated_at = ?, printed_at = ?, error_message = ?
                        WHERE id = ?
                    """, (
                        job_dict['order_id'], job_dict['job_type'], job_dict['status'],
                        job_dict['content'], job_dict['printer_name'], job_dict['attempts'],
                        job_dict['max_attempts'], job_dict['updated_at'],
                        job_dict['printed_at'], job_dict['error_message'], print_job.id
                    ))
                    job_id = print_job.id
                else:
                    # Insert new job
                    cursor = conn.execute("""
                        INSERT INTO print_jobs (
                            order_id, job_type, status, content, printer_name,
                            attempts, max_attempts, created_at, updated_at,
                            printed_at, error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job_dict['order_id'], job_dict['job_type'], job_dict['status'],
                        job_dict['content'], job_dict['printer_name'], job_dict['attempts'],
                        job_dict['max_attempts'], job_dict['created_at'],
                        job_dict['updated_at'], job_dict['printed_at'], job_dict['error_message']
                    ))
                    job_id = str(cursor.lastrowid)
                
                conn.commit()
                logger.info(f"Print job {job_id} saved successfully")
                return job_id
                
        except sqlite3.Error as e:
            logger.error(f"Error saving print job: {e}")
            return None
    
    def get_pending_print_jobs(self) -> List[PrintJob]:
        """
        Retrieve all pending print jobs.
        
        Returns:
            List of PrintJob instances with pending status
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM print_jobs 
                    WHERE status = ? AND attempts < max_attempts
                    ORDER BY created_at ASC
                """, (PrintJobStatus.PENDING.value,))
                rows = cursor.fetchall()
                
                return [self._row_to_print_job(row) for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving pending print jobs: {e}")
            return []
    
    def _row_to_order(self, row: sqlite3.Row) -> Order:
        """Convert database row to Order instance."""
        # Parse JSON fields
        items_data = json.loads(row['items_json'])
        customer_data = json.loads(row['customer_json'])
        delivery_data = json.loads(row['delivery_json'])
        raw_data = json.loads(row['raw_data_json']) if row['raw_data_json'] else None
        
        # Reconstruct items
        items = [OrderItem(**item_data) for item_data in items_data]
        
        # Reconstruct customer and delivery info
        customer = CustomerInfo(**customer_data)
        delivery = DeliveryInfo(**delivery_data)
        
        return Order(
            id=row['id'],
            wix_order_id=row['wix_order_id'],
            status=OrderStatus(row['status']),
            items=items,
            customer=customer,
            delivery=delivery,
            total_amount=row['total_amount'],
            currency=row['currency'],
            order_date=datetime.fromisoformat(row['order_date']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            raw_data=raw_data
        )
    
    def _row_to_print_job(self, row: sqlite3.Row) -> PrintJob:
        """Convert database row to PrintJob instance."""
        return PrintJob(
            id=str(row['id']),
            order_id=row['order_id'],
            job_type=row['job_type'],
            status=PrintJobStatus(row['status']),
            content=row['content'],
            printer_name=row['printer_name'],
            attempts=row['attempts'],
            max_attempts=row['max_attempts'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            printed_at=datetime.fromisoformat(row['printed_at']) if row['printed_at'] else None,
            error_message=row['error_message']
        )
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
