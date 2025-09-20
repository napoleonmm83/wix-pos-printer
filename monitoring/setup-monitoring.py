#!/usr/bin/env python3
"""
Recovery Monitoring Setup Script
Konfiguriert Monitoring und Alerting für Story 2.2 Recovery System
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

class RecoveryMonitoringSetup:
    """Setup-Klasse für Recovery Monitoring"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.monitoring_dir = self.project_root / "monitoring"
        self.config_dir = self.project_root / "config"
        self.logs_dir = self.project_root / "logs"
        
    def setup_directories(self):
        """Erstelle erforderliche Verzeichnisse"""
        directories = [
            self.monitoring_dir,
            self.monitoring_dir / "dashboards",
            self.monitoring_dir / "alerts",
            self.config_dir / "monitoring",
            self.logs_dir / "recovery"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created directory: {directory}")
    
    def create_monitoring_config(self):
        """Erstelle Monitoring-Konfigurationsdateien"""
        
        # Monitoring Configuration
        monitoring_config = {
            "recovery_monitoring": {
                "enabled": True,
                "dashboard_refresh_interval": "30s",
                "history_retention_days": 30,
                "alerts": {
                    "recovery_failure": {
                        "enabled": True,
                        "severity": "critical"
                    },
                    "queue_overflow": {
                        "enabled": True,
                        "threshold": 1000,
                        "severity": "critical"
                    },
                    "recovery_timeout": {
                        "enabled": True,
                        "threshold_minutes": 30,
                        "severity": "high"
                    },
                    "high_failure_rate": {
                        "enabled": True,
                        "threshold_percentage": 80,
                        "severity": "warning"
                    }
                },
                "performance_thresholds": {
                    "recovery_initiation_seconds": 5,
                    "batch_processing_rate": 10,
                    "memory_usage_mb": 500,
                    "max_recovery_duration_minutes": 15
                }
            }
        }
        
        config_file = self.config_dir / "monitoring" / "recovery-monitoring.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(monitoring_config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Created monitoring config: {config_file}")
        
        # Alert Configuration
        alert_config = {
            "alerts": [
                {
                    "name": "recovery_failure",
                    "condition": "recovery_session.status == 'failed'",
                    "severity": "critical",
                    "notification": "immediate",
                    "message": "Recovery session {session_id} failed: {error_message}",
                    "enabled": True
                },
                {
                    "name": "queue_overflow",
                    "condition": "offline_queue.size > 1000",
                    "severity": "critical", 
                    "notification": "immediate",
                    "message": "Offline queue overflow: {queue_size} items, urgency: {urgency_level}",
                    "enabled": True
                },
                {
                    "name": "recovery_timeout",
                    "condition": "recovery_session.duration > 30_minutes",
                    "severity": "high",
                    "notification": "5_minutes",
                    "message": "Recovery session {session_id} running for {duration}, phase: {phase}",
                    "enabled": True
                }
            ]
        }
        
        alert_file = self.config_dir / "monitoring" / "alerts.json"
        with open(alert_file, 'w', encoding='utf-8') as f:
            json.dump(alert_config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Created alert config: {alert_file}")
    
    def create_dashboard_templates(self):
        """Erstelle Dashboard-Templates"""
        
        # Recovery Status Dashboard Template
        status_dashboard = {
            "dashboard": {
                "title": "Recovery Status Dashboard",
                "refresh_interval": 30,
                "panels": [
                    {
                        "title": "Current Recovery Session",
                        "type": "status",
                        "endpoint": "/recovery/status",
                        "fields": [
                            "current_session.id",
                            "current_session.type", 
                            "current_session.phase",
                            "current_session.progress_percentage",
                            "current_session.items_total",
                            "current_session.items_processed",
                            "current_session.items_failed"
                        ]
                    },
                    {
                        "title": "Queue Statistics",
                        "type": "metrics",
                        "endpoint": "/recovery/statistics",
                        "fields": [
                            "queue_statistics.total_items",
                            "recovery_statistics.priority_distribution",
                            "recovery_statistics.recovery_urgency"
                        ]
                    }
                ]
            }
        }
        
        dashboard_file = self.monitoring_dir / "dashboards" / "recovery-status.json"
        with open(dashboard_file, 'w', encoding='utf-8') as f:
            json.dump(status_dashboard, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Created status dashboard: {dashboard_file}")
        
        # Recovery History Dashboard Template
        history_dashboard = {
            "dashboard": {
                "title": "Recovery History Dashboard",
                "refresh_interval": 300,
                "panels": [
                    {
                        "title": "Recovery Sessions (Last 24h)",
                        "type": "timeline",
                        "endpoint": "/recovery/history",
                        "params": {"limit": 50},
                        "fields": [
                            "recovery_history.*.timestamp",
                            "recovery_history.*.event_type",
                            "recovery_history.*.details"
                        ]
                    },
                    {
                        "title": "Success Rate Trends",
                        "type": "chart",
                        "endpoint": "/recovery/statistics",
                        "chart_type": "line",
                        "time_range": "7d"
                    }
                ]
            }
        }
        
        history_file = self.monitoring_dir / "dashboards" / "recovery-history.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_dashboard, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Created history dashboard: {history_file}")
    
    def create_monitoring_scripts(self):
        """Erstelle Monitoring-Scripts"""
        
        # Health Check Script
        health_check_script = '''#!/usr/bin/env python3
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
'''
        
        health_check_file = self.monitoring_dir / "health-check.py"
        with open(health_check_file, 'w', encoding='utf-8') as f:
            f.write(health_check_script)
        
        # Make script executable
        os.chmod(health_check_file, 0o755)
        print(f"✓ Created health check script: {health_check_file}")
        
        # Performance Monitor Script
        perf_monitor_script = '''#!/usr/bin/env python3
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
            print("\\nMonitoring stopped")

def main():
    monitor = PerformanceMonitor()
    monitor.run_continuous()

if __name__ == "__main__":
    main()
'''
        
        perf_monitor_file = self.monitoring_dir / "performance-monitor.py"
        with open(perf_monitor_file, 'w', encoding='utf-8') as f:
            f.write(perf_monitor_script)
        
        os.chmod(perf_monitor_file, 0o755)
        print(f"✓ Created performance monitor: {perf_monitor_file}")
    
    def create_systemd_services(self):
        """Erstelle systemd Service-Definitionen für Monitoring"""
        
        # Health Check Service
        health_service = f'''[Unit]
Description=Recovery System Health Check
After=network.target

[Service]
Type=oneshot
ExecStart={self.monitoring_dir.absolute()}/health-check.py
User=pi
WorkingDirectory={self.project_root.absolute()}

[Install]
WantedBy=multi-user.target
'''
        
        # Health Check Timer
        health_timer = '''[Unit]
Description=Run Recovery Health Check every 5 minutes
Requires=recovery-health-check.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
'''
        
        # Performance Monitor Service
        perf_service = f'''[Unit]
Description=Recovery Performance Monitor
After=network.target
Wants=wix-printer-service.service

[Service]
Type=simple
ExecStart={self.monitoring_dir.absolute()}/performance-monitor.py
Restart=always
RestartSec=30
User=pi
WorkingDirectory={self.project_root.absolute()}

[Install]
WantedBy=multi-user.target
'''
        
        # Write service files
        systemd_dir = self.monitoring_dir / "systemd"
        systemd_dir.mkdir(exist_ok=True)
        
        services = [
            ("recovery-health-check.service", health_service),
            ("recovery-health-check.timer", health_timer),
            ("recovery-performance-monitor.service", perf_service)
        ]
        
        for filename, content in services:
            service_file = systemd_dir / filename
            with open(service_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Created systemd service: {service_file}")
        
        # Create installation script
        install_script = f'''#!/bin/bash
# Recovery Monitoring Installation Script

echo "Installing Recovery Monitoring Services..."

# Copy service files
sudo cp {systemd_dir.absolute()}/*.service /etc/systemd/system/
sudo cp {systemd_dir.absolute()}/*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable recovery-health-check.timer
sudo systemctl start recovery-health-check.timer

sudo systemctl enable recovery-performance-monitor.service
sudo systemctl start recovery-performance-monitor.service

echo "✓ Recovery monitoring services installed and started"
echo "✓ Health checks will run every 5 minutes"
echo "✓ Performance monitoring is running continuously"

# Show status
echo ""
echo "Service Status:"
sudo systemctl status recovery-health-check.timer --no-pager -l
sudo systemctl status recovery-performance-monitor.service --no-pager -l
'''
        
        install_file = self.monitoring_dir / "install-monitoring.sh"
        with open(install_file, 'w', encoding='utf-8') as f:
            f.write(install_script)
        
        os.chmod(install_file, 0o755)
        print(f"✓ Created installation script: {install_file}")
    
    def setup_complete(self):
        """Setup-Zusammenfassung"""
        print("\n" + "="*60)
        print("🎯 Recovery Monitoring Setup Complete!")
        print("="*60)
        
        print("\n📁 Created Files:")
        print(f"  • {self.monitoring_dir}/recovery-dashboard.md")
        print(f"  • {self.config_dir}/monitoring/recovery-monitoring.json")
        print(f"  • {self.config_dir}/monitoring/alerts.json")
        print(f"  • {self.monitoring_dir}/dashboards/recovery-status.json")
        print(f"  • {self.monitoring_dir}/dashboards/recovery-history.json")
        print(f"  • {self.monitoring_dir}/health-check.py")
        print(f"  • {self.monitoring_dir}/performance-monitor.py")
        print(f"  • {self.monitoring_dir}/systemd/ (service files)")
        print(f"  • {self.monitoring_dir}/install-monitoring.sh")
        
        print("\n🚀 Next Steps:")
        print("  1. Review configuration files")
        print("  2. Test health check script:")
        print(f"     python3 {self.monitoring_dir}/health-check.py")
        print("  3. Install monitoring services:")
        print(f"     {self.monitoring_dir}/install-monitoring.sh")
        print("  4. Configure alerting (Story 2.3)")
        print("  5. Create web dashboards (optional)")
        
        print("\n📊 Available Endpoints:")
        print("  • GET /recovery/status - Current recovery status")
        print("  • GET /recovery/history - Recovery history")
        print("  • GET /recovery/statistics - Queue and recovery stats")
        print("  • GET /connectivity/status - Connectivity status")
        
        print("\n⚠️  Dependencies:")
        print("  • Story 2.2 must be deployed and running")
        print("  • FastAPI service must be accessible on localhost:8000")
        print("  • Story 2.3 needed for email alerting")

def main():
    """Main setup function"""
    print("🔧 Setting up Recovery Monitoring for Story 2.2...")
    
    setup = RecoveryMonitoringSetup()
    
    try:
        setup.setup_directories()
        setup.create_monitoring_config()
        setup.create_dashboard_templates()
        setup.create_monitoring_scripts()
        setup.create_systemd_services()
        setup.setup_complete()
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
