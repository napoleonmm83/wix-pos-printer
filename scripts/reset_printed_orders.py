#!/usr/bin/env python3
"""
This script clears the auto_checked_orders table to allow existing orders
to be re-processed and printed.
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

def main():
    """Connects to the database and clears the auto_checked_orders table."""
    # Assume the script is run from the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    
    print(f"Loading environment from: {env_path}")
    if not os.path.exists(env_path):
        print(f"ERROR: .env file not found at {env_path}")
        sys.exit(1)
        
    load_dotenv(env_path)
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in .env file.")
        sys.exit(1)

    print("Connecting to the database...")
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        print("Executing DELETE FROM auto_checked_orders...")
        cursor.execute("DELETE FROM auto_checked_orders;")
        
        reset_count = cursor.rowcount
        conn.commit()
        
        print(f"✅ Success! Reset {reset_count} orders for re-printing.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
