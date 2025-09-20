"""
Database migration scripts for Wix Printer Service.
Handles schema updates and data migrations between versions.
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Base class for database migrations."""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
    
    def apply(self, connection: sqlite3.Connection) -> bool:
        """
        Apply the migration.
        
        Args:
            connection: Database connection
            
        Returns:
            True if migration was successful
        """
        raise NotImplementedError("Subclasses must implement apply method")
    
    def rollback(self, connection: sqlite3.Connection) -> bool:
        """
        Rollback the migration.
        
        Args:
            connection: Database connection
            
        Returns:
            True if rollback was successful
        """
        raise NotImplementedError("Subclasses must implement rollback method")


class Migration_2_3_NotificationTables(DatabaseMigration):
    """Migration for Story 2.3: Add notification tables."""
    
    def __init__(self):
        super().__init__("2.3.0", "Add notification tables for Story 2.3")
    
    def apply(self, connection: sqlite3.Connection) -> bool:
        """Apply notification tables migration."""
        try:
            cursor = connection.cursor()
            
            # Create notification_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_type TEXT NOT NULL,
                    context TEXT,
                    success BOOLEAN NOT NULL,
                    sent_at TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT
                )
            """)
            
            # Create notification_templates table for custom templates
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_type TEXT NOT NULL UNIQUE,
                    subject_template TEXT NOT NULL,
                    body_template TEXT NOT NULL,
                    html_template TEXT,
                    throttle_minutes INTEGER DEFAULT 15,
                    max_per_hour INTEGER DEFAULT 4,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create notification_config table for settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL UNIQUE,
                    config_value TEXT,
                    config_type TEXT DEFAULT 'string',
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_history_type 
                ON notification_history(notification_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_history_sent_at 
                ON notification_history(sent_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_history_success 
                ON notification_history(success)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_templates_type 
                ON notification_templates(notification_type)
            """)
            
            # Insert default notification configuration
            default_configs = [
                ('smtp_server', '', 'string', 'SMTP server hostname'),
                ('smtp_port', '587', 'integer', 'SMTP server port'),
                ('smtp_username', '', 'string', 'SMTP username'),
                ('smtp_use_tls', 'true', 'boolean', 'Use TLS encryption'),
                ('from_email', '', 'string', 'From email address'),
                ('to_emails', '', 'string', 'Comma-separated recipient emails'),
                ('enabled', 'false', 'boolean', 'Enable notifications'),
                ('restaurant_name', 'Restaurant', 'string', 'Restaurant name for notifications')
            ]
            
            for config_key, config_value, config_type, description in default_configs:
                cursor.execute("""
                    INSERT OR IGNORE INTO notification_config 
                    (config_key, config_value, config_type, description)
                    VALUES (?, ?, ?, ?)
                """, (config_key, config_value, config_type, description))
            
            connection.commit()
            logger.info("Successfully applied notification tables migration")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply notification tables migration: {e}")
            connection.rollback()
            return False
    
    def rollback(self, connection: sqlite3.Connection) -> bool:
        """Rollback notification tables migration."""
        try:
            cursor = connection.cursor()
            
            # Drop tables in reverse order
            cursor.execute("DROP TABLE IF EXISTS notification_config")
            cursor.execute("DROP TABLE IF EXISTS notification_templates")
            cursor.execute("DROP TABLE IF EXISTS notification_history")
            
            connection.commit()
            logger.info("Successfully rolled back notification tables migration")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback notification tables migration: {e}")
            connection.rollback()
            return False


class Migration_2_2_RecoveryTables(DatabaseMigration):
    """Migration for Story 2.2: Add recovery tables (if not already applied)."""
    
    def __init__(self):
        super().__init__("2.2.0", "Add recovery tables for Story 2.2")
    
    def apply(self, connection: sqlite3.Connection) -> bool:
        """Apply recovery tables migration."""
        try:
            cursor = connection.cursor()
            
            # Create recovery_sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_sessions (
                    id TEXT PRIMARY KEY,
                    recovery_type TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    items_total INTEGER DEFAULT 0,
                    items_processed INTEGER DEFAULT 0,
                    items_failed INTEGER DEFAULT 0,
                    error_message TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recovery_sessions_type 
                ON recovery_sessions(recovery_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recovery_sessions_started_at 
                ON recovery_sessions(started_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recovery_sessions_phase 
                ON recovery_sessions(phase)
            """)
            
            connection.commit()
            logger.info("Successfully applied recovery tables migration")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply recovery tables migration: {e}")
            connection.rollback()
            return False
    
    def rollback(self, connection: sqlite3.Connection) -> bool:
        """Rollback recovery tables migration."""
        try:
            cursor = connection.cursor()
            cursor.execute("DROP TABLE IF EXISTS recovery_sessions")
            connection.commit()
            logger.info("Successfully rolled back recovery tables migration")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback recovery tables migration: {e}")
            connection.rollback()
            return False


class DatabaseMigrator:
    """Manages database migrations."""
    
    def __init__(self, database_path: str):
        self.database_path = Path(database_path)
        self.migrations = [
            Migration_2_2_RecoveryTables(),
            Migration_2_3_NotificationTables()
        ]
    
    def _ensure_migration_table(self, connection: sqlite3.Connection):
        """Ensure migration tracking table exists."""
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                rollback_sql TEXT
            )
        """)
        connection.commit()
    
    def _is_migration_applied(self, connection: sqlite3.Connection, version: str) -> bool:
        """Check if a migration has been applied."""
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = ?", 
            (version,)
        )
        return cursor.fetchone()[0] > 0
    
    def _record_migration(self, connection: sqlite3.Connection, migration: DatabaseMigration):
        """Record that a migration has been applied."""
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES (?, ?)
        """, (migration.version, migration.description))
        connection.commit()
    
    def _remove_migration_record(self, connection: sqlite3.Connection, version: str):
        """Remove migration record."""
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM schema_migrations WHERE version = ?", 
            (version,)
        )
        connection.commit()
    
    def apply_migrations(self) -> bool:
        """Apply all pending migrations."""
        try:
            with sqlite3.connect(self.database_path) as connection:
                self._ensure_migration_table(connection)
                
                applied_count = 0
                for migration in self.migrations:
                    if not self._is_migration_applied(connection, migration.version):
                        logger.info(f"Applying migration {migration.version}: {migration.description}")
                        
                        if migration.apply(connection):
                            self._record_migration(connection, migration)
                            applied_count += 1
                            logger.info(f"Successfully applied migration {migration.version}")
                        else:
                            logger.error(f"Failed to apply migration {migration.version}")
                            return False
                    else:
                        logger.debug(f"Migration {migration.version} already applied")
                
                if applied_count > 0:
                    logger.info(f"Applied {applied_count} migrations successfully")
                else:
                    logger.info("No migrations to apply")
                
                return True
                
        except Exception as e:
            logger.error(f"Error applying migrations: {e}")
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration."""
        try:
            migration = next((m for m in self.migrations if m.version == version), None)
            if not migration:
                logger.error(f"Migration {version} not found")
                return False
            
            with sqlite3.connect(self.database_path) as connection:
                self._ensure_migration_table(connection)
                
                if not self._is_migration_applied(connection, version):
                    logger.warning(f"Migration {version} is not applied")
                    return True
                
                logger.info(f"Rolling back migration {version}: {migration.description}")
                
                if migration.rollback(connection):
                    self._remove_migration_record(connection, version)
                    logger.info(f"Successfully rolled back migration {version}")
                    return True
                else:
                    logger.error(f"Failed to rollback migration {version}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error rolling back migration {version}: {e}")
            return False
    
    def get_migration_status(self) -> List[Dict[str, Any]]:
        """Get status of all migrations."""
        try:
            with sqlite3.connect(self.database_path) as connection:
                self._ensure_migration_table(connection)
                
                cursor = connection.cursor()
                cursor.execute("""
                    SELECT version, description, applied_at 
                    FROM schema_migrations 
                    ORDER BY version
                """)
                applied_migrations = {row[0]: {"description": row[1], "applied_at": row[2]} 
                                    for row in cursor.fetchall()}
                
                status = []
                for migration in self.migrations:
                    if migration.version in applied_migrations:
                        status.append({
                            "version": migration.version,
                            "description": migration.description,
                            "status": "applied",
                            "applied_at": applied_migrations[migration.version]["applied_at"]
                        })
                    else:
                        status.append({
                            "version": migration.version,
                            "description": migration.description,
                            "status": "pending",
                            "applied_at": None
                        })
                
                return status
                
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return []
    
    def create_backup(self) -> str:
        """Create a backup of the database before migrations."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.database_path.parent / f"{self.database_path.stem}_backup_{timestamp}.db"
            
            # Copy database file
            import shutil
            shutil.copy2(self.database_path, backup_path)
            
            logger.info(f"Database backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return ""


def run_migrations(database_path: str) -> bool:
    """
    Run database migrations.
    
    Args:
        database_path: Path to the database file
        
    Returns:
        True if migrations were successful
    """
    migrator = DatabaseMigrator(database_path)
    
    # Create backup before migrations
    backup_path = migrator.create_backup()
    if not backup_path:
        logger.warning("Could not create database backup, proceeding anyway")
    
    # Apply migrations
    success = migrator.apply_migrations()
    
    if success:
        logger.info("All migrations completed successfully")
    else:
        logger.error("Migration failed")
        if backup_path:
            logger.info(f"Database backup available at: {backup_path}")
    
    return success


if __name__ == "__main__":
    # Run migrations if script is executed directly
    import sys
    
    if len(sys.argv) > 1:
        database_path = sys.argv[1]
    else:
        database_path = "data/printer_service.db"
    
    success = run_migrations(database_path)
    sys.exit(0 if success else 1)
