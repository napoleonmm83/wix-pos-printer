#!/usr/bin/env python3
"""
Recovery System Health Check Script
Überprüft den Status des Recovery Systems
"""

import requests
import json
import sys
from datetime import datetime

def check_recovery_status():
    """Überprüfe Recovery Manager Status"""
    try:
        response = requests.get("http://localhost:8000/recovery/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✓ Recovery Manager: Online")
            
            if data.get("current_session"):
                session = data["current_session"]
                print(f"  Active Session: {session['id']} ({session['type']})")
                print(f"  Phase: {session['phase']}")
                print(f"  Progress: {session.get('progress_percentage', 0):.1f}%")
            else:
                print("  No active recovery session")
            
            return True
        else:
            print(f"✗ Recovery Manager: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Recovery Manager: Connection failed - {e}")
        return False

def check_queue_status():
    """Überprüfe Queue Status"""
    try:
        response = requests.get("http://localhost:8000/offline/queue/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            total_items = data.get("total_items", 0)
            print(f"✓ Offline Queue: {total_items} items")
            
            if total_items > 1000:
                print("  ⚠️  Warning: Queue size is high")
            elif total_items > 500:
                print("  ⚠️  Notice: Queue size is elevated")
            
            return True
        else:
            print(f"✗ Offline Queue: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Offline Queue: Connection failed - {e}")
        return False

def check_connectivity():
    """Überprüfe Connectivity Status"""
    try:
        response = requests.get("http://localhost:8000/connectivity/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            printer_status = data.get("printer", {}).get("status", "unknown")
            internet_status = data.get("internet", {}).get("status", "unknown")
            
            print(f"✓ Connectivity Monitor: Online")
            print(f"  Printer: {printer_status}")
            print(f"  Internet: {internet_status}")
            
            return True
        else:
            print(f"✗ Connectivity Monitor: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Connectivity Monitor: Connection failed - {e}")
        return False

def main():
    """Main health check function"""
    print(f"Recovery System Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    checks = [
        check_recovery_status(),
        check_queue_status(), 
        check_connectivity()
    ]
    
    passed = sum(checks)
    total = len(checks)
    
    print("=" * 60)
    print(f"Health Check Result: {passed}/{total} checks passed")
    
    if passed == total:
        print("✓ All systems operational")
        sys.exit(0)
    else:
        print("✗ Some systems have issues")
        sys.exit(1)

if __name__ == "__main__":
    main()
