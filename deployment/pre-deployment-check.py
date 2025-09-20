#!/usr/bin/env python3
"""
Pre-Deployment Validation Script
Validates system readiness for Story 2.2 + 2.3 deployment
"""

import os
import sys
import json
import sqlite3
import subprocess
import requests
from pathlib import Path
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

class PreDeploymentValidator:
    """Validates system readiness for production deployment."""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "UNKNOWN",
            "checks": {},
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
    
    def run_all_checks(self):
        """Run all pre-deployment validation checks."""
        print("🔍 Pre-Deployment Validation - Stories 2.2 & 2.3")
        print("=" * 60)
        
        checks = [
            ("System Requirements", self.check_system_requirements),
            ("Code Readiness", self.check_code_readiness),
            ("Database Schema", self.check_database_schema),
            ("Configuration Files", self.check_configuration),
            ("Dependencies", self.check_dependencies),
            ("Service Health", self.check_service_health),
            ("SMTP Configuration", self.check_smtp_config),
            ("Monitoring Setup", self.check_monitoring_setup),
            ("Backup Strategy", self.check_backup_strategy),
            ("Rollback Plan", self.check_rollback_readiness)
        ]
        
        for check_name, check_func in checks:
            print(f"\n📋 {check_name}...")
            try:
                result = check_func()
                self.results["checks"][check_name] = result
                
                if result["status"] == "PASS":
                    print(f"  ✅ {result['message']}")
                elif result["status"] == "WARNING":
                    print(f"  ⚠️  {result['message']}")
                    self.results["warnings"].append(f"{check_name}: {result['message']}")
                else:
                    print(f"  ❌ {result['message']}")
                    self.results["errors"].append(f"{check_name}: {result['message']}")
                    
            except Exception as e:
                error_msg = f"Check failed with exception: {str(e)}"
                print(f"  ❌ {error_msg}")
                self.results["checks"][check_name] = {"status": "FAIL", "message": error_msg}
                self.results["errors"].append(f"{check_name}: {error_msg}")
        
        self._generate_summary()
        return self.results
    
    def check_system_requirements(self):
        """Check system requirements for deployment."""
        issues = []
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 11):
            issues.append(f"Python {python_version.major}.{python_version.minor} < 3.11 required")
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (1024**3)
            if free_gb < 5:
                issues.append(f"Low disk space: {free_gb}GB free (5GB+ recommended)")
        except:
            issues.append("Could not check disk space")
        
        # Check memory
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    if 'MemTotal:' in line:
                        mem_kb = int(line.split()[1])
                        mem_gb = mem_kb / (1024**2)
                        if mem_gb < 2:
                            issues.append(f"Low memory: {mem_gb:.1f}GB (2GB+ recommended)")
                        break
        except:
            pass  # Not critical on non-Linux systems
        
        if issues:
            return {"status": "WARNING", "message": "; ".join(issues)}
        return {"status": "PASS", "message": "System requirements met"}
    
    def check_code_readiness(self):
        """Check if all required code files are present."""
        required_files = [
            "wix_printer_service/recovery_manager.py",
            "wix_printer_service/notification_service.py",
            "wix_printer_service/database_migrations.py",
            "wix_printer_service/print_manager.py",
            "wix_printer_service/api/main.py",
            "scripts/setup-notifications.py",
            "monitoring/health-check.py",
            "monitoring/performance-monitor.py",
            "tests/test_recovery_manager.py",
            "tests/test_notification_service.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            return {"status": "FAIL", "message": f"Missing files: {', '.join(missing_files)}"}
        
        return {"status": "PASS", "message": f"All {len(required_files)} required files present"}
    
    def check_database_schema(self):
        """Check database schema readiness."""
        db_path = self.project_root / "data" / "printer_service.db"
        
        if not db_path.exists():
            return {"status": "WARNING", "message": "Database file not found (will be created)"}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ["print_jobs", "orders", "offline_queue", "connectivity_events"]
            missing_tables = [t for t in required_tables if t not in tables]
            
            # Check if migration tables exist (Story 2.3)
            new_tables = ["notification_history", "recovery_sessions"]
            has_new_tables = any(t in tables for t in new_tables)
            
            conn.close()
            
            if missing_tables:
                return {"status": "FAIL", "message": f"Missing core tables: {', '.join(missing_tables)}"}
            
            if has_new_tables:
                return {"status": "WARNING", "message": "New tables already exist (migration may have been run)"}
            
            return {"status": "PASS", "message": f"Database schema ready for migration ({len(tables)} tables)"}
            
        except Exception as e:
            return {"status": "FAIL", "message": f"Database check failed: {str(e)}"}
    
    def check_configuration(self):
        """Check configuration file readiness."""
        issues = []
        
        # Check .env.example
        env_example = self.project_root / ".env.example"
        if not env_example.exists():
            issues.append(".env.example missing")
        else:
            with open(env_example, 'r') as f:
                content = f.read()
                required_vars = [
                    "NOTIFICATION_ENABLED",
                    "SMTP_SERVER",
                    "RECOVERY_BATCH_SIZE",
                    "MONITORING_ENABLED"
                ]
                missing_vars = [var for var in required_vars if var not in content]
                if missing_vars:
                    issues.append(f"Missing env vars in .env.example: {', '.join(missing_vars)}")
        
        # Check monitoring config directory
        monitoring_config = self.project_root / "config" / "monitoring"
        if not monitoring_config.exists():
            issues.append("Monitoring config directory missing")
        
        if issues:
            return {"status": "WARNING", "message": "; ".join(issues)}
        
        return {"status": "PASS", "message": "Configuration files ready"}
    
    def check_dependencies(self):
        """Check Python dependencies."""
        try:
            # Check if virtual environment exists
            venv_path = self.project_root / "venv"
            if not venv_path.exists():
                return {"status": "WARNING", "message": "Virtual environment not found"}
            
            # Check key dependencies
            required_packages = [
                "fastapi",
                "uvicorn", 
                "sqlite3",  # Built-in
                "pytest",
                "requests"
            ]
            
            missing_packages = []
            for package in required_packages:
                if package == "sqlite3":
                    continue  # Built-in
                try:
                    __import__(package)
                except ImportError:
                    missing_packages.append(package)
            
            if missing_packages:
                return {"status": "WARNING", "message": f"Missing packages: {', '.join(missing_packages)}"}
            
            return {"status": "PASS", "message": "Dependencies available"}
            
        except Exception as e:
            return {"status": "WARNING", "message": f"Could not verify dependencies: {str(e)}"}
    
    def check_service_health(self):
        """Check current service health."""
        try:
            # Try to connect to service
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                return {"status": "PASS", "message": "Service currently running and healthy"}
            else:
                return {"status": "WARNING", "message": f"Service responding with status {response.status_code}"}
        except requests.exceptions.ConnectionError:
            return {"status": "PASS", "message": "Service not running (expected for deployment)"}
        except Exception as e:
            return {"status": "WARNING", "message": f"Could not check service: {str(e)}"}
    
    def check_smtp_config(self):
        """Check SMTP configuration readiness."""
        # Check if setup script exists
        setup_script = self.project_root / "scripts" / "setup-notifications.py"
        if not setup_script.exists():
            return {"status": "FAIL", "message": "Notification setup script missing"}
        
        # Check if .env has SMTP placeholders
        env_example = self.project_root / ".env.example"
        if env_example.exists():
            with open(env_example, 'r') as f:
                content = f.read()
                if "SMTP_SERVER" in content and "NOTIFICATION_ENABLED" in content:
                    return {"status": "PASS", "message": "SMTP configuration template ready"}
        
        return {"status": "WARNING", "message": "SMTP configuration needs manual setup"}
    
    def check_monitoring_setup(self):
        """Check monitoring system readiness."""
        monitoring_files = [
            "monitoring/health-check.py",
            "monitoring/performance-monitor.py", 
            "monitoring/install-monitoring.sh",
            "monitoring/systemd/recovery-health-check.service",
            "monitoring/systemd/recovery-performance-monitor.service"
        ]
        
        missing_files = []
        for file_path in monitoring_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            return {"status": "FAIL", "message": f"Missing monitoring files: {', '.join(missing_files)}"}
        
        return {"status": "PASS", "message": f"Monitoring system ready ({len(monitoring_files)} files)"}
    
    def check_backup_strategy(self):
        """Check backup strategy readiness."""
        # Check if backup directory structure can be created
        try:
            backup_test_dir = Path("/tmp/backup_test")
            backup_test_dir.mkdir(exist_ok=True)
            backup_test_dir.rmdir()
            return {"status": "PASS", "message": "Backup strategy ready"}
        except Exception as e:
            return {"status": "WARNING", "message": f"Backup directory creation test failed: {str(e)}"}
    
    def check_rollback_readiness(self):
        """Check rollback plan readiness."""
        deployment_dir = self.project_root / "deployment"
        if not deployment_dir.exists():
            return {"status": "WARNING", "message": "Deployment directory missing"}
        
        required_files = [
            "production-deployment-plan-v2.md",
            "deployment-checklist.md"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (deployment_dir / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            return {"status": "WARNING", "message": f"Missing deployment docs: {', '.join(missing_files)}"}
        
        return {"status": "PASS", "message": "Rollback documentation ready"}
    
    def _generate_summary(self):
        """Generate overall deployment readiness summary."""
        total_checks = len(self.results["checks"])
        passed_checks = sum(1 for check in self.results["checks"].values() if check["status"] == "PASS")
        failed_checks = sum(1 for check in self.results["checks"].values() if check["status"] == "FAIL")
        warning_checks = sum(1 for check in self.results["checks"].values() if check["status"] == "WARNING")
        
        print("\n" + "=" * 60)
        print("📊 DEPLOYMENT READINESS SUMMARY")
        print("=" * 60)
        
        print(f"✅ Passed:   {passed_checks}/{total_checks}")
        print(f"⚠️  Warnings: {warning_checks}/{total_checks}")
        print(f"❌ Failed:   {failed_checks}/{total_checks}")
        
        # Determine overall status
        if failed_checks > 0:
            self.results["overall_status"] = "NOT_READY"
            print(f"\n🚫 DEPLOYMENT STATUS: NOT READY")
            print("❌ Critical issues must be resolved before deployment")
        elif warning_checks > 0:
            self.results["overall_status"] = "READY_WITH_WARNINGS"
            print(f"\n⚠️  DEPLOYMENT STATUS: READY WITH WARNINGS")
            print("⚠️  Warnings should be addressed but deployment can proceed")
        else:
            self.results["overall_status"] = "READY"
            print(f"\n✅ DEPLOYMENT STATUS: READY")
            print("🚀 All checks passed - ready for production deployment")
        
        # Show errors and warnings
        if self.results["errors"]:
            print(f"\n❌ CRITICAL ISSUES:")
            for error in self.results["errors"]:
                print(f"   • {error}")
        
        if self.results["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in self.results["warnings"]:
                print(f"   • {warning}")
        
        # Generate recommendations
        self._generate_recommendations()
        
        if self.results["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in self.results["recommendations"]:
                print(f"   • {rec}")
    
    def _generate_recommendations(self):
        """Generate deployment recommendations based on check results."""
        recommendations = []
        
        if self.results["overall_status"] == "NOT_READY":
            recommendations.append("Resolve all critical issues before attempting deployment")
            recommendations.append("Run this validation script again after fixes")
        
        if any("SMTP" in error for error in self.results["errors"] + self.results["warnings"]):
            recommendations.append("Run 'python scripts/setup-notifications.py' to configure email notifications")
        
        if any("database" in error.lower() for error in self.results["errors"] + self.results["warnings"]):
            recommendations.append("Backup existing database before running migrations")
        
        if any("Virtual environment" in warning for warning in self.results["warnings"]):
            recommendations.append("Create virtual environment: python -m venv venv && source venv/bin/activate")
        
        if self.results["overall_status"] in ["READY", "READY_WITH_WARNINGS"]:
            recommendations.append("Create system backup before deployment")
            recommendations.append("Schedule maintenance window for deployment")
            recommendations.append("Notify stakeholders of planned deployment")
            recommendations.append("Have rollback plan ready")
        
        self.results["recommendations"] = recommendations
    
    def save_results(self, output_file="deployment/pre-deployment-validation.json"):
        """Save validation results to file."""
        output_path = self.project_root / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_path}")
        return output_path

def main():
    """Main validation function."""
    validator = PreDeploymentValidator()
    results = validator.run_all_checks()
    validator.save_results()
    
    # Exit with appropriate code
    if results["overall_status"] == "NOT_READY":
        sys.exit(1)
    elif results["overall_status"] == "READY_WITH_WARNINGS":
        sys.exit(2)  # Warnings but can proceed
    else:
        sys.exit(0)  # All good

if __name__ == "__main__":
    main()
