#!/usr/bin/env python3
"""
Script to update the database schema for enhanced order change detection
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def update_schema():
    """Add new columns to auto_checked_orders table"""
    print("Updating database schema for order change detection...")

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                # Add new columns if they don't exist
                print("Adding last_updated_date column...")
                try:
                    cursor.execute("""
                        ALTER TABLE auto_checked_orders
                        ADD COLUMN IF NOT EXISTS last_updated_date TEXT
                    """)
                    print("+ last_updated_date column added")
                except Exception as e:
                    print(f"- Error adding last_updated_date: {e}")

                print("Adding reprint_count column...")
                try:
                    cursor.execute("""
                        ALTER TABLE auto_checked_orders
                        ADD COLUMN IF NOT EXISTS reprint_count INTEGER DEFAULT 0
                    """)
                    print("+ reprint_count column added")
                except Exception as e:
                    print(f"- Error adding reprint_count: {e}")

                # Show current table structure
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'auto_checked_orders'
                    ORDER BY ordinal_position
                """)

                columns = cursor.fetchall()
                print(f"\nUpdated table structure ({len(columns)} columns):")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")

                conn.commit()
                print("\n+ Database schema updated successfully!")

    except Exception as e:
        print(f"- Database update failed: {e}")

if __name__ == "__main__":
    update_schema()