#!/usr/bin/env python3
"""
Recovery Performance Monitor
Sammelt Performance-Metriken für das Recovery System
"""

import requests
import json
import time
import csv
from datetime import datetime
from pathlib import Path

class PerformanceMonitor:
    def __init__(self, output_dir="logs/recovery"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def collect_metrics(self):
        """Sammle aktuelle Performance-Metriken"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "recovery_status": self.get_recovery_metrics(),
            "queue_metrics": self.get_queue_metrics(),
            "connectivity_metrics": self.get_connectivity_metrics()
        }
        return metrics
    
    def get_recovery_metrics(self):
        """Sammle Recovery-spezifische Metriken"""
        try:
            response = requests.get("http://localhost:8000/recovery/status", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_queue_metrics(self):
        """Sammle Queue-Metriken"""
        try:
            response = requests.get("http://localhost:8000/recovery/statistics", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_connectivity_metrics(self):
        """Sammle Connectivity-Metriken"""
        try:
            response = requests.get("http://localhost:8000/connectivity/status", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def save_metrics(self, metrics):
        """Speichere Metriken in CSV-Datei"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        csv_file = self.output_dir / f"performance-{date_str}.csv"
        
        # CSV Header
        fieldnames = [
            "timestamp", "recovery_active", "recovery_type", "recovery_phase",
            "items_total", "items_processed", "items_failed", "queue_size",
            "printer_status", "internet_status"
        ]
        
        # Flatten metrics for CSV
        row = {
            "timestamp": metrics["timestamp"],
            "recovery_active": bool(metrics.get("recovery_status", {}).get("current_session")),
            "recovery_type": "",
            "recovery_phase": "",
            "items_total": 0,
            "items_processed": 0,
            "items_failed": 0,
            "queue_size": 0,
            "printer_status": "unknown",
            "internet_status": "unknown"
        }
        
        # Extract recovery metrics
        if metrics.get("recovery_status", {}).get("current_session"):
            session = metrics["recovery_status"]["current_session"]
            row.update({
                "recovery_type": session.get("type", ""),
                "recovery_phase": session.get("phase", ""),
                "items_total": session.get("items_total", 0),
                "items_processed": session.get("items_processed", 0),
                "items_failed": session.get("items_failed", 0)
            })
        
        # Extract queue metrics
        if metrics.get("queue_metrics", {}).get("queue_statistics"):
            queue_stats = metrics["queue_metrics"]["queue_statistics"]
            row["queue_size"] = queue_stats.get("total_items", 0)
        
        # Extract connectivity metrics
        if metrics.get("connectivity_metrics"):
            conn = metrics["connectivity_metrics"]
            row["printer_status"] = conn.get("printer", {}).get("status", "unknown")
            row["internet_status"] = conn.get("internet", {}).get("status", "unknown")
        
        # Write to CSV
        file_exists = csv_file.exists()
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    
    def run_continuous(self, interval=60):
        """Kontinuierliche Metriken-Sammlung"""
        print(f"Starting performance monitoring (interval: {interval}s)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                metrics = self.collect_metrics()
                self.save_metrics(metrics)
                print(f"Metrics collected at {metrics['timestamp']}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")

def main():
    monitor = PerformanceMonitor()
    monitor.run_continuous()

if __name__ == "__main__":
    main()
