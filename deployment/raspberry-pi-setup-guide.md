# 🍓 Raspberry Pi Setup Guide - Wix Printer Service

**Version**: 1.0  
**Date**: 2025-09-20  
**Epic Status**: Epic 2 Complete - Self-Healing System Ready

---

## 📋 **Prerequisites**

### **Hardware Requirements**
- **Raspberry Pi 4** (4GB+ RAM recommended)
- **MicroSD Card** (32GB+ Class 10)
- **Epson TM-m30III** POS Printer
- **USB Cable** or **Ethernet Connection** for printer
- **Stable Internet Connection**

### **Software Requirements**
- **Raspberry Pi OS** (64-bit recommended)
- **Python 3.11+** (should be pre-installed)
- **Git** (should be pre-installed)

---

## 🚀 **Phase 1: System Preparation (15 minutes)**

### **1.1 Update System**
```bash
# Update package lists and system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y git python3-pip python3-venv sqlite3 curl

# Verify Python version (should be 3.11+)
python3 --version
```

### **1.2 Create Service User**
```bash
# Create dedicated user for the service
sudo useradd -r -s /bin/bash -d /opt/wix-printer-service wix-printer

# Create service directory
sudo mkdir -p /opt/wix-printer-service
sudo chown wix-printer:wix-printer /opt/wix-printer-service
```

### **1.3 Setup Printer Connection**
```bash
# Install CUPS for printer management
sudo apt install -y cups cups-client

# Add wix-printer user to lp group
sudo usermod -a -G lp wix-printer

# Check if printer is detected
lsusb | grep -i epson
```

---

## 📦 **Phase 2: Code Deployment (10 minutes)**

### **2.1 Clone Repository**
```bash
# Switch to service user
sudo su - wix-printer

# Clone the repository
cd /opt/wix-printer-service
git clone https://github.com/your-repo/wix-pos-order.git .

# Or copy from development machine
# scp -r /path/to/wix-pos-order/* pi@raspberry-ip:/opt/wix-printer-service/
```

### **2.2 Setup Python Environment**
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install additional Raspberry Pi specific packages
pip install psutil  # For health monitoring
```

### **2.3 Update Requirements for Raspberry Pi**
```bash
# Add Raspberry Pi specific dependencies
cat >> requirements.txt << EOF
psutil>=5.9.0
RPi.GPIO>=0.7.1
gpiozero>=1.6.2
EOF

# Install new dependencies
pip install -r requirements.txt
```

---

## ⚙️ **Phase 3: Configuration Setup (20 minutes)**

### **3.1 Environment Configuration**
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Required .env Configuration:**
```bash
# Database
DATABASE_URL=sqlite:///data/wix_printer.db

# Wix API Configuration
WIX_API_KEY=your_wix_api_key_here
WIX_SITE_ID=your_wix_site_id_here
WIX_API_BASE_URL=https://www.wixapis.com

# Printer Configuration
PRINTER_TYPE=epson
PRINTER_INTERFACE=usb
PRINTER_DEVICE_PATH=/dev/usb/lp0

# Service Configuration
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8000
LOG_LEVEL=INFO

# Self-Healing Configuration
HEALTH_CHECK_INTERVAL=30
RETRY_MAX_ATTEMPTS=5
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3

# Email Notifications (run setup script later)
SMTP_SERVER=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
NOTIFICATION_FROM_EMAIL=
NOTIFICATION_TO_EMAIL=
```

### **3.2 Create Data Directories**
```bash
# Create necessary directories
mkdir -p data logs backups

# Set permissions
chmod 755 data logs backups
```

### **3.3 Database Initialization**
```bash
# Initialize database
python -c "
from wix_printer_service.database import Database
db = Database('data/wix_printer.db')
db.initialize()
print('Database initialized successfully!')
"
```

---

## 📧 **Phase 4: Email Notifications Setup (10 minutes)**

### **4.1 Run Interactive SMTP Setup**
```bash
# Run the interactive setup script
python scripts/setup-notifications.py

# This will guide you through:
# - Email provider selection (Gmail/Outlook/Yahoo/Custom)
# - SMTP credentials input
# - Connection testing
# - Test email sending
# - Automatic .env file update
```

### **4.2 Verify Email Configuration**
```bash
# Test email functionality
python -c "
import asyncio
from wix_printer_service.notification_service import NotificationService
from wix_printer_service.database import Database

async def test_email():
    db = Database('data/wix_printer.db')
    service = NotificationService(db)
    await service.start()
    
    # Send test notification
    await service.send_notification(
        'system_test',
        'Raspberry Pi Setup Complete',
        {'message': 'Email notifications are working!'}
    )
    
    await service.stop()
    print('Test email sent successfully!')

asyncio.run(test_email())
"
```

---

## 🖨️ **Phase 5: Printer Setup & Testing (15 minutes)**

### **5.1 Configure Printer**
```bash
# Check printer connection
lsusb | grep -i epson

# Test basic printer communication
python -c "
from wix_printer_service.printer_client import PrinterClient
client = PrinterClient()
print('Printer connected:', client.is_connected)
"
```

### **5.2 Print Test Receipt**
```bash
# Test complete printing workflow
python -c "
import asyncio
from wix_printer_service.print_manager import PrintManager
from wix_printer_service.database import Database
from wix_printer_service.printer_client import PrinterClient

async def test_print():
    db = Database('data/wix_printer.db')
    printer = PrinterClient()
    manager = PrintManager(db, printer)
    
    # Test self-healing system
    status = manager.get_self_healing_status()
    print('Self-Healing Status:', status['retry_manager']['running'])
    print('Health Monitor:', status['health_monitor']['running'])
    
    print('Print test completed!')

asyncio.run(test_print())
"
```

---

## 🔧 **Phase 6: Service Installation (10 minutes)**

### **6.1 Create Systemd Service**
```bash
# Copy service file
sudo cp deployment/wix-printer.service /etc/systemd/system/

# Update service file paths
sudo sed -i 's|/path/to/wix-pos-order|/opt/wix-printer-service|g' /etc/systemd/system/wix-printer.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable wix-printer.service
```

### **6.2 Start Service**
```bash
# Start the service
sudo systemctl start wix-printer.service

# Check service status
sudo systemctl status wix-printer.service

# View service logs
sudo journalctl -u wix-printer.service -f
```

---

## 🏥 **Phase 7: Health Monitoring Setup (5 minutes)**

### **7.1 Install Monitoring Scripts**
```bash
# Install monitoring
sudo bash monitoring/install-monitoring.sh

# Verify monitoring services
sudo systemctl status wix-printer-health-check.timer
sudo systemctl status wix-printer-performance-monitor.service
```

### **7.2 Test Self-Healing System**
```bash
# Test health monitoring
curl http://localhost:8000/health/metrics

# Test circuit breakers
curl http://localhost:8000/circuit-breakers/status

# Test retry manager
curl http://localhost:8000/retry-manager/status

# Trigger manual health check
curl -X POST http://localhost:8000/self-healing/trigger-check
```

---

## 🧪 **Phase 8: Comprehensive Testing (20 minutes)**

### **8.1 API Endpoint Tests**
```bash
# Test all API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/status
curl http://localhost:8000/jobs
curl http://localhost:8000/recovery/status
curl http://localhost:8000/notifications/status

# Test self-healing endpoints (NEW in Epic 2!)
curl http://localhost:8000/self-healing/status
curl http://localhost:8000/self-healing/history
curl http://localhost:8000/health/metrics
curl http://localhost:8000/circuit-breakers/status
curl http://localhost:8000/retry-manager/status
```

### **8.2 Self-Healing System Tests**
```bash
# Test retry mechanism
python -c "
import asyncio
from wix_printer_service.retry_manager import retry_print_job

async def test_retry():
    # This will test the intelligent retry system
    result = await retry_print_job('test_job_123', max_attempts=3)
    print('Retry test completed:', result)

asyncio.run(test_retry())
"

# Test health monitoring
python -c "
from wix_printer_service.health_monitor import get_system_health
health = get_system_health()
print('System Health:', health)
"

# Test circuit breaker
python -c "
from wix_printer_service.circuit_breaker import printer_circuit_breaker
cb = printer_circuit_breaker()
print('Circuit Breaker State:', cb.state.value)
print('Failure Count:', cb.failure_count)
"
```

### **8.3 Integration Tests**
```bash
# Run comprehensive test suite
cd /opt/wix-printer-service
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run specific Epic 2 tests
python -m pytest tests/test_retry_manager.py -v
python -m pytest tests/test_health_monitor.py -v
python -m pytest tests/test_circuit_breaker.py -v
```

---

## 📊 **Phase 9: Monitoring & Validation (10 minutes)**

### **9.1 Setup Monitoring Dashboard**
```bash
# Access monitoring endpoints
echo "=== System Status ==="
curl -s http://localhost:8000/status | python -m json.tool

echo "=== Self-Healing Status ==="
curl -s http://localhost:8000/self-healing/status | python -m json.tool

echo "=== Health Metrics ==="
curl -s http://localhost:8000/health/metrics | python -m json.tool
```

### **9.2 Performance Validation**
```bash
# Check system resources
echo "=== System Resources ==="
free -h
df -h
ps aux | grep wix-printer

# Check service performance
echo "=== Service Performance ==="
curl -w "@curl-format.txt" -s http://localhost:8000/health

# Create curl format file
cat > curl-format.txt << EOF
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF
```

---

## 🎯 **Success Criteria Validation**

### **✅ Epic 2 Features Working:**
- [ ] **Intelligent Retry System** - Exponential backoff working
- [ ] **Health Monitoring** - Memory/CPU/Disk monitoring active
- [ ] **Circuit Breakers** - Printer/API protection enabled
- [ ] **Self-Healing Orchestration** - All components integrated
- [ ] **Email Notifications** - Alerts working properly
- [ ] **API Management** - 12 new endpoints responding

### **✅ System Health Checks:**
- [ ] **Service Running** - `systemctl status wix-printer.service`
- [ ] **API Responding** - All endpoints return 200 OK
- [ ] **Database Working** - SQLite database accessible
- [ ] **Printer Connected** - Epson TM-m30III detected
- [ ] **Email Working** - Test notifications sent
- [ ] **Monitoring Active** - Health checks running

### **✅ Performance Targets:**
- [ ] **API Response Time** < 500ms
- [ ] **Memory Usage** < 512MB
- [ ] **CPU Usage** < 20% idle
- [ ] **Disk Usage** < 80%
- [ ] **Service Uptime** 99.9%

---

## 🚨 **Troubleshooting**

### **Common Issues & Solutions:**

#### **1. Printer Not Detected**
```bash
# Check USB connection
lsusb | grep -i epson

# Check printer permissions
sudo usermod -a -G lp wix-printer
sudo systemctl restart cups

# Test printer manually
echo "Test print" | lp
```

#### **2. Service Won't Start**
```bash
# Check service logs
sudo journalctl -u wix-printer.service -n 50

# Check permissions
sudo chown -R wix-printer:wix-printer /opt/wix-printer-service

# Check Python environment
sudo su - wix-printer
source venv/bin/activate
python -c "import wix_printer_service; print('Import successful')"
```

#### **3. Email Notifications Not Working**
```bash
# Re-run SMTP setup
python scripts/setup-notifications.py

# Test SMTP manually
python -c "
import smtplib
from email.mime.text import MIMEText
# Add your SMTP test code here
"
```

#### **4. Self-Healing System Issues**
```bash
# Check health monitor
curl http://localhost:8000/health/metrics

# Reset circuit breakers
curl -X POST http://localhost:8000/circuit-breakers/printer/reset

# Check retry manager
curl http://localhost:8000/retry-manager/status
```

---

## 🎉 **Deployment Complete!**

### **🏆 Epic 2 Features Now Active on Raspberry Pi:**
- ✅ **Intelligent Retry System** with exponential backoff
- ✅ **Real-time Health Monitoring** with automatic cleanup
- ✅ **Circuit Breaker Protection** for all external dependencies
- ✅ **Self-Healing Orchestration** with comprehensive logging
- ✅ **Proactive Email Notifications** for all critical events
- ✅ **12 New API Endpoints** for complete system management

### **🎯 Next Steps:**
1. **Monitor system for 24-48 hours**
2. **Test with real Wix orders**
3. **Validate MVP success criteria** (99% order success rate)
4. **Plan Phase 2 features** if system is stable

### **📞 Support:**
- **Logs**: `sudo journalctl -u wix-printer.service -f`
- **Status**: `curl http://localhost:8000/self-healing/status`
- **Health**: `curl http://localhost:8000/health/metrics`

**🚀 Your restaurant printing system is now fully autonomous with complete self-healing capabilities!**
