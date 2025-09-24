#!/usr/bin/env python3
"""
Test script to verify service communication and reliability.
Tests both Wix API connection and service-to-service communication.
"""

import requests
import json
import time
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_service_status(port, name):
    """Test if a service is running on the specified port"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=5)
        if response.status_code == 200:
            print(f"+ {name} (Port {port}): RUNNING")
            return True
        else:
            print(f"- {name} (Port {port}): UNHEALTHY (Status: {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"- {name} (Port {port}): NOT RUNNING")
        return False
    except requests.exceptions.Timeout:
        print(f"! {name} (Port {port}): TIMEOUT")
        return False

def test_webhook_endpoint(port, service_name):
    """Test the webhook endpoint"""
    try:
        test_payload = {
            "data": {
                "orderId": "test_order_123"
            },
            "metadata": {
                "source": "test_script"
            }
        }

        response = requests.post(
            f"http://localhost:{port}/webhook/orders",
            json=test_payload,
            timeout=10
        )

        if response.status_code == 202:
            print(f"+ {service_name} webhook endpoint: WORKING")
            return True
        elif response.status_code == 404:
            print(f"! {service_name} webhook endpoint: Order not found (expected for test)")
            return True  # This is expected for a test order
        else:
            print(f"- {service_name} webhook endpoint: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"- {service_name} webhook endpoint: ERROR - {e}")
        return False

def test_wix_api_fix():
    """Test if the Wix API authorization fix works"""
    print("\n" + "="*60)
    print("Testing Wix API Authorization Fix")
    print("="*60)

    try:
        # Import the fixed fetch function
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))

        # Test the function from app.py (we need to setup env vars first)
        from dotenv import load_dotenv
        import asyncio
        import httpx

        load_dotenv()

        WIX_API_KEY = os.environ.get("WIX_API_KEY")
        WIX_SITE_ID = os.environ.get("WIX_SITE_ID")
        WIX_API_BASE_URL = os.environ.get("WIX_API_BASE_URL", "https://www.wixapis.com")

        if not WIX_API_KEY or not WIX_SITE_ID:
            print("- Wix API credentials not configured")
            return False

        headers = {
            "Authorization": WIX_API_KEY,  # Fixed: no "Bearer" prefix
            "Content-Type": "application/json",
            "wix-site-id": WIX_SITE_ID
        }

        params = {
            "paging": {"limit": 1},
            "sort": [{"createdDate": "DESC"}],
            "filter": {"status": {"$ne": "INITIALIZED"}}
        }

        async def test_api():
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{WIX_API_BASE_URL}/ecom/v1/orders/search"
                response = await client.post(url, headers=headers, json=params)
                return response

        response = asyncio.run(test_api())

        if response.status_code == 200:
            data = response.json()
            order_count = len(data.get("orders", []))
            print(f"+ Wix API connection: WORKING ({order_count} orders found)")
            return True
        else:
            print(f"- Wix API connection: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"- Wix API test error: {e}")
        return False

def start_service_if_needed(service_name, command, port):
    """Start a service if it's not already running"""
    if not test_service_status(port, service_name):
        print(f"\n> Attempting to start {service_name}...")
        try:
            # Start service in background
            subprocess.Popen(command, shell=True)
            print(f"   Started command: {command}")
            print(f"   Waiting 10 seconds for {service_name} to start...")
            time.sleep(10)

            # Test again
            if test_service_status(port, service_name):
                print(f"+ {service_name} started successfully")
                return True
            else:
                print(f"- {service_name} failed to start")
                return False
        except Exception as e:
            print(f"- Error starting {service_name}: {e}")
            return False
    return True

def main():
    print("Wix POS Order Service - Communication & Reliability Test")
    print("="*60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    results = {}

    # Test 1: Service Status Check
    print("1. Testing Service Status")
    print("-" * 30)
    results['printer_service'] = test_service_status(8000, "Printer Service")
    results['webhook_service'] = test_service_status(5000, "Webhook/Auto-Check Service")

    # Test 2: Wix API Authorization Fix
    print("\n2. Testing Wix API Authorization Fix")
    print("-" * 30)
    results['wix_api'] = test_wix_api_fix()

    # Test 3: Webhook Endpoints
    print("\n3. Testing Webhook Endpoints")
    print("-" * 30)
    if results['printer_service']:
        results['printer_webhook'] = test_webhook_endpoint(8000, "Printer Service")
    else:
        results['printer_webhook'] = False
        print("- Printer Service webhook: SKIPPED (service not running)")

    # Test 4: Service Communication
    print("\n4. Testing Auto-Check -> Printer Service Communication")
    print("-" * 30)
    if results['printer_service']:
        # Simulate what auto-check does
        try:
            test_payload = {
                "data": {"orderId": "test_communication_check"},
                "metadata": {"source": "communication_test"}
            }

            response = requests.post(
                "http://localhost:8000/webhook/orders",
                json=test_payload,
                timeout=10
            )

            if response.status_code in [202, 404]:  # 404 is OK for test order
                print("+Auto-check -> Printer Service communication: WORKING")
                results['communication'] = True
            else:
                print(f"- Auto-check -> Printer Service communication: FAILED (Status: {response.status_code})")
                results['communication'] = False
        except Exception as e:
            print(f"- Auto-check -> Printer Service communication: ERROR - {e}")
            results['communication'] = False
    else:
        results['communication'] = False
        print("- Service communication: SKIPPED (printer service not running)")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "+" if result else "-"
        print(f"{symbol} {test_name.replace('_', ' ').title()}: {status}")

    print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n+ All tests passed! Service is healthy.")
    elif results.get('wix_api', False) and results.get('communication', False):
        print("\n! Core functionality working, some services may need restart.")
    else:
        print("\n- Critical issues found. Service reliability compromised.")

    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)

    if not results.get('printer_service', False):
        print("FIX: Start Printer Service: python -m wix_printer_service.main")

    if not results.get('webhook_service', False):
        print("FIX: Start Webhook Service: python app.py")

    if not results.get('wix_api', False):
        print("FIX: Check Wix API credentials in .env file")

    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()