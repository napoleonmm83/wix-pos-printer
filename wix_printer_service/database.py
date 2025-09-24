"""
Database management for the Wix Printer Service.
Handles PostgreSQL database initialization and CRUD operations using psycopg2.
"""
import psycopg2
import psycopg2.extras
import logging
import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import Order, PrintJob, OrderStatus, PrintJobStatus, OrderItem, CustomerInfo, DeliveryInfo

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass


class Database:
    """
    PostgreSQL database manager for orders and print jobs.
    Handles database initialization, connections, and CRUD operations.
    """
    
    def __init__(self):
        """
        Initialize database connection URL and ensure tables are created.
        """
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise DatabaseError("DATABASE_URL environment variable not set.")
        
        self._initialize_database()
        logger.info("Database initialized with PostgreSQL.")
    
    @contextmanager
    def get_connection(self):
        """Provide a transactional scope around a series of operations."""
        conn = None
        try:
            conn = psycopg2.connect(self.db_url)
            yield conn
            conn.commit()
        except (psycopg2.Error, Exception) as e:
            logger.error(f"Database transaction failed: {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(f"Database transaction failed: {e}")
        finally:
            if conn:
                conn.close()

    def _initialize_database(self):
        """Create database tables if they don't exist using PostgreSQL syntax."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Create orders table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS orders (
                            id TEXT PRIMARY KEY,
                            wix_order_id TEXT UNIQUE NOT NULL,
                            status TEXT NOT NULL,
                            items_json JSONB NOT NULL,
                            customer_json JSONB NOT NULL,
                            delivery_json JSONB NOT NULL,
                            total_amount NUMERIC(10, 2) NOT NULL,
                            currency TEXT NOT NULL DEFAULT 'EUR',
                            order_date TIMESTAMPTZ NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL,
                            raw_data_json JSONB
                        )
                    """)
                    
                    # Create print_jobs table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS print_jobs (
                            id SERIAL PRIMARY KEY,
                            order_id TEXT NOT NULL,
                            job_type TEXT NOT NULL,
                            status TEXT NOT NULL,
                            content TEXT NOT NULL,
                            printer_name TEXT,
                            attempts INTEGER DEFAULT 0,
                            max_attempts INTEGER DEFAULT 3,
                            created_at TIMESTAMPTZ NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL,
                            printed_at TIMESTAMPTZ,
                            error_message TEXT,
                            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Create health_metrics table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS health_metrics (
                            id SERIAL PRIMARY KEY,
                            timestamp TIMESTAMPTZ NOT NULL,
                            metric_name TEXT NOT NULL,
                            value REAL NOT NULL,
                            tags TEXT,
                            status TEXT
                        )
                    """)
                    
                    # Create circuit_breaker_failures table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS circuit_breaker_failures (
                            id SERIAL PRIMARY KEY,
                            breaker_name TEXT NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL
                        )
                    """)
                    
                    # Create indexes for better performance
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_wix_id ON orders(wix_order_id);")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_print_jobs_order_id ON print_jobs(order_id);")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_print_jobs_status ON print_jobs(status);")

                    # Create self_healing_events table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS self_healing_events (
                            id SERIAL PRIMARY KEY,
                            event_type TEXT NOT NULL,
                            resource_type TEXT NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL,
                            details JSONB
                        )
                    """)
                
                logger.info("Database tables checked/created successfully")
                
        except psycopg2.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")

    def save_order(self, order: Order) -> bool:
        """Saves or updates an order in the database using ON CONFLICT."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    order_dict = order.to_dict()
                    
                    # Use INSERT ... ON CONFLICT for "upsert" behavior
                    cursor.execute("""
                        INSERT INTO orders (
                            id, wix_order_id, status, items_json, customer_json,
                            delivery_json, total_amount, currency, order_date,
                            created_at, updated_at, raw_data_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (wix_order_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            items_json = EXCLUDED.items_json,
                            customer_json = EXCLUDED.customer_json,
                            delivery_json = EXCLUDED.delivery_json,
                            total_amount = EXCLUDED.total_amount,
                            currency = EXCLUDED.currency,
                            order_date = EXCLUDED.order_date,
                            updated_at = EXCLUDED.updated_at,
                            raw_data_json = EXCLUDED.raw_data_json;
                    """, (
                        order_dict['id'], order_dict['wix_order_id'], order_dict['status'],
                        json.dumps(order_dict['items_json']), json.dumps(order_dict['customer_json']),
                        json.dumps(order_dict['delivery_json']), order_dict['total_amount'],
                        order_dict['currency'], order_dict['order_date'],
                        order_dict['created_at'], order_dict['updated_at'],
                        json.dumps(order_dict['raw_data_json'])
                    ))
            logger.info(f"Order {order.id} saved successfully")
            return True
        except psycopg2.Error as e:
            logger.error(f"Error saving order {order.id}: {e}")
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        """Retrieve an order by its primary key."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
                    row = cursor.fetchone()
                    return self._row_to_order(row) if row else None
        except psycopg2.Error as e:
            logger.error(f"Error retrieving order {order_id}: {e}")
            return None

    def get_order_by_wix_id(self, wix_order_id: str) -> Optional[Order]:
        """Retrieve an order by its Wix Order ID."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT * FROM orders WHERE wix_order_id = %s", (wix_order_id,))
                    row = cursor.fetchone()
                    return self._row_to_order(row) if row else None
        except psycopg2.Error as e:
            logger.error(f"Error retrieving order by Wix ID {wix_order_id}: {e}")
            return None

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """Retrieve orders by status."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute(
                        "SELECT * FROM orders WHERE status = %s ORDER BY created_at DESC",
                        (status.value,)
                    )
                    rows = cursor.fetchall()
                    return [self._row_to_order(row) for row in rows]
        except psycopg2.Error as e:
            logger.error(f"Error retrieving orders by status {status}: {e}")
            return []

    def save_print_job(self, print_job: PrintJob) -> Optional[int]:
        """Save a print job to the database and return its ID."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    job_dict = print_job.to_dict()
                    
                    if print_job.id:
                        # Update existing job
                        cursor.execute("""
                            UPDATE print_jobs SET
                                order_id = %s, job_type = %s, status = %s, content = %s,
                                printer_name = %s, attempts = %s, max_attempts = %s,
                                updated_at = %s, printed_at = %s, error_message = %s
                            WHERE id = %s
                        """, (
                            job_dict['order_id'], job_dict['job_type'], job_dict['status'],
                            job_dict['content'], job_dict['printer_name'], job_dict['attempts'],
                            job_dict['max_attempts'], job_dict['updated_at'],
                            job_dict['printed_at'], job_dict['error_message'], print_job.id
                        ))
                        job_id = print_job.id
                    else:
                        # Insert new job and return the new ID
                        cursor.execute("""
                            INSERT INTO print_jobs (
                                order_id, job_type, status, content, printer_name,
                                attempts, max_attempts, created_at, updated_at,
                                printed_at, error_message
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id;
                        """, (
                            job_dict['order_id'], job_dict['job_type'], job_dict['status'],
                            job_dict['content'], job_dict['printer_name'], job_dict['attempts'],
                            job_dict['max_attempts'], job_dict['created_at'],
                            job_dict['updated_at'], job_dict['printed_at'], job_dict['error_message']
                        ))
                        job_id = cursor.fetchone()[0]
                    
                    logger.info(f"Print job {job_id} saved successfully")
                    return job_id
        except psycopg2.Error as e:
            logger.error(f"Error saving print job: {e}")
            return None

    def get_pending_print_jobs(self) -> List[PrintJob]:
        """Retrieve all pending print jobs."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("""
                        SELECT * FROM print_jobs 
                        WHERE status = %s AND attempts < max_attempts
                        ORDER BY created_at ASC
                    """, (PrintJobStatus.PENDING.value,))
                    rows = cursor.fetchall()
                    return [self._row_to_print_job(row) for row in rows]
        except psycopg2.Error as e:
            logger.error(f"Error retrieving pending print jobs: {e}")
            return []

    def _row_to_order(self, row: psycopg2.extras.DictRow) -> Order:
        """Convert database row (DictRow) to Order instance."""
        # The JSONB fields might be returned as strings, so they must be loaded.
        items_list = json.loads(row['items_json']) if isinstance(row['items_json'], str) else row['items_json']
        customer_dict = json.loads(row['customer_json']) if isinstance(row['customer_json'], str) else row['customer_json']
        delivery_dict = json.loads(row['delivery_json']) if isinstance(row['delivery_json'], str) else row['delivery_json']
        raw_data_dict = json.loads(row['raw_data_json']) if isinstance(row['raw_data_json'], str) and row['raw_data_json'] else row['raw_data_json']

        return Order(
            id=row['id'],
            wix_order_id=row['wix_order_id'],
            status=OrderStatus(row['status']),
            items=[OrderItem(**item_data) for item_data in items_list],
            customer=CustomerInfo(**customer_dict),
            delivery=DeliveryInfo(**delivery_dict),
            total_amount=row['total_amount'],
            currency=row['currency'],
            order_date=row['order_date'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            raw_data=raw_data_dict
        )

    def _row_to_print_job(self, row: psycopg2.extras.DictRow) -> PrintJob:
        """Convert database row (DictRow) to PrintJob instance."""
        return PrintJob(
            id=row['id'],
            order_id=row['order_id'],
            job_type=row['job_type'],
            status=PrintJobStatus(row['status']),
            content=row['content'],
            printer_name=row['printer_name'],
            attempts=row['attempts'],
            max_attempts=row['max_attempts'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            printed_at=row['printed_at'],
            error_message=row['error_message']
        )
