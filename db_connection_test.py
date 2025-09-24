
import os
import sys
import psycopg2
from dotenv import load_dotenv

def test_db_connection():
    """
    Tests the database connection using the DATABASE_URL from the .env file.
    """
    print("--- Database Connection Test ---")
    
    # Load environment variables from .env file
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment or .env file.")
        sys.exit(1)
    
    print(f"Attempting to connect to database...")
    # Hide password in output
    try:
        # Basic parsing to hide password
        user_part = db_url.split('@')[0].split('//')[1].split(':')[0]
        host_part = db_url.split('@')[1]
        print(f"Target: postgresql://{user_part}:****@{host_part}")
    except Exception:
        print("Target: (Could not parse URL to hide password)")


    try:
        # Try to connect with a timeout
        conn = psycopg2.connect(db_url, connect_timeout=10)
        print("\nSUCCESS: Database connection established successfully!")
        conn.close()
        print("Connection closed.")
        sys.exit(0)
    except psycopg2.OperationalError as e:
        print(f"\nERROR: Connection Failed. The server is running but rejected the connection.")
        print(f"Details: {e}")
        print("\nTroubleshooting:")
        print("1. Check if the username and password in your DATABASE_URL are correct.")
        print("2. Verify that the database server is configured to accept connections from your Raspberry Pi's IP address.")
    except Exception as e:
        print(f"\nERROR: A critical error occurred: {e}")
        print("\nTroubleshooting:")
        print("1. Check if the host and port in the DATABASE_URL are correct.")
        print("2. Verify that no firewall on the Raspberry Pi or your network is blocking outbound traffic on the specified port.")
        print("3. Ensure the database server is running and accessible from the internet.")

    sys.exit(1)

if __name__ == "__main__":
    test_db_connection()
