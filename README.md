# 🍓 Wix Restaurant Printer Service

**Autonomous Restaurant Printing System with Self-Healing Capabilities**

[![Epic 2](https://img.shields.io/badge/Epic%202-Complete-brightgreen)](docs/stories/2.4.self-healing.md)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4+-red)](https://raspberrypi.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 🎯 **Project Overview**

An intelligent, autonomous printing service that runs on Raspberry Pi and automatically processes Wix restaurant orders. The system features comprehensive self-healing capabilities, intelligent retry mechanisms, and proactive monitoring to ensure 99.9% uptime with zero manual intervention.

### **🏆 Epic 2 Complete - Self-Healing System**
- ✅ **Intelligent Retry System** - Exponential backoff with jitter
- ✅ **Real-time Health Monitoring** - Memory, CPU, Disk, Thread monitoring
- ✅ **Circuit Breaker Protection** - Prevents cascading failures
- ✅ **Self-Healing Orchestration** - Automatic problem resolution
- ✅ **Proactive Email Notifications** - Instant alerts for critical issues
- ✅ **12 Management API Endpoints** - Complete system control

---

## 🚀 **Quick Start**

### **🍓 One-Command Setup (Recommended)**
```bash
# 1. Clone repository
git clone https://github.com/napoleonmm83/wix-pos-printer.git
cd wix-pos-printer

# 2. Run one-command setup (makes scripts executable automatically)
chmod +x setup.sh && ./setup.sh
```

### **🌐 Public URL Options Available:**
- **Cloudflare Tunnel** (no static IP needed) ⭐
- **Dynamic DNS** (works with changing IPs)  
- **Static IP Setup** (traditional method)

### **Manual Script Setup (Alternative)**
```bash
# Make scripts executable first
chmod +x scripts/*.sh

# Then run main setup
./scripts/raspberry-pi-quickstart.sh

# 2. Run interactive setup wizard
chmod +x scripts/raspberry-pi-quickstart.sh
./scripts/raspberry-pi-quickstart.sh

# 3. The wizard will guide you through:
#    - Wix API configuration
#    - Automatic printer detection
#    - Epic 2 self-healing settings
#    - Optional email notifications
#    - Service installation and startup
```

### **Reset/Cleanup Installation**
```bash
# Complete reset - removes all components
./scripts/raspberry-pi-quickstart.sh --reset

# After reset, you can run setup again
./scripts/raspberry-pi-quickstart.sh
```

### **Available Setup Options**
```bash
# Interactive setup wizard (default)
./scripts/raspberry-pi-quickstart.sh

# Complete system reset/cleanup
./scripts/raspberry-pi-quickstart.sh --reset

# Show help and available options
./scripts/raspberry-pi-quickstart.sh --help
```

### **Development Setup**
```bash
# 1. Clone and setup
git clone https://github.com/napoleonmm83/wix-pos-printer.git
cd wix-pos-printer

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
python -c "from wix_printer_service.database import Database; Database('data/wix_printer.db').initialize()"

# 5. Run development server
uvicorn wix_printer_service.api.main:app --reload
```

---

## 🏗️ **Architecture**

### **System Components**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Wix Orders    │───▶│  Print Manager   │───▶│ Epson Printer   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Self-Healing     │
                    │ Orchestration    │
                    └──────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Retry Manager│    │Health Monitor│    │Circuit Breaker│
└──────────────┘    └──────────────┘    └──────────────┘
```

### **Epic 2 Self-Healing Features**

#### **🔄 Intelligent Retry System**
- **Exponential Backoff** with jitter to prevent thundering herd
- **Dead Letter Queue** for permanently failed tasks
- **Failure Classification** (timeout, connection, service errors)
- **Configurable Strategies** per failure type

#### **🏥 Health Monitoring**
- **Resource Monitoring**: Memory, CPU, Disk, Thread usage
- **Configurable Thresholds**: Warning, Critical, Emergency levels
- **Automatic Cleanup**: Garbage collection, resource optimization
- **Proactive Alerts**: Email notifications before issues become critical

#### **⚡ Circuit Breaker Protection**
- **Three States**: Closed, Open, Half-Open
- **Failure Detection**: Automatic failure threshold monitoring
- **Fast Recovery**: Intelligent recovery testing
- **Service Protection**: Printer, Wix API, SMTP circuit breakers

---

## 📊 **API Endpoints**

### **Core System**
- `GET /health` - System health check
- `GET /status` - Service status
- `GET /jobs` - Print job management
- `POST /jobs` - Submit new print job

### **🆕 Epic 2 Self-Healing Management**
- `GET /self-healing/status` - Comprehensive self-healing status
- `POST /self-healing/trigger-check` - Manual health check
- `GET /self-healing/history` - Self-healing event history
- `GET /health/metrics` - Real-time resource metrics
- `GET /health/metrics/history` - Historical health data
- `GET /circuit-breakers/status` - Circuit breaker status
- `POST /circuit-breakers/{name}/reset` - Reset circuit breaker
- `GET /retry-manager/status` - Retry system status
- `GET /retry-manager/dead-letter-queue` - Failed tasks queue
- `POST /retry-manager/requeue/{task_id}` - Requeue failed task
- `POST /health/thresholds/update` - Update monitoring thresholds
- `GET /self-healing/config` - System configuration

---

## 🛠️ **Configuration**

### **Environment Variables**
```bash
# Database
DATABASE_URL=sqlite:///data/wix_printer.db

# Wix API
WIX_API_KEY=your_api_key
WIX_SITE_ID=your_site_id

# Printer
PRINTER_TYPE=epson
PRINTER_INTERFACE=usb

# Self-Healing
HEALTH_CHECK_INTERVAL=30
RETRY_MAX_ATTEMPTS=5
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3

# Email Notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
NOTIFICATION_TO_EMAIL=manager@restaurant.com
```

### **Health Monitoring Thresholds**
```json
{
  "memory": {
    "warning": 70,
    "critical": 85,
    "emergency": 95
  },
  "cpu": {
    "warning": 70,
    "critical": 85,
    "emergency": 95
  },
  "disk": {
    "warning": 80,
    "critical": 90,
    "emergency": 95
  }
}
```

---

## 🧪 **Testing**

### **Run Tests**
```bash
# All tests
pytest

# Epic 2 specific tests
pytest tests/test_retry_manager.py -v
pytest tests/test_health_monitor.py -v
pytest tests/test_circuit_breaker.py -v

# Integration tests
pytest tests/test_integration.py -v
```

### **Test Coverage**
- **Retry Manager**: 31+ tests covering all retry scenarios
- **Health Monitor**: 25+ tests for resource monitoring
- **Circuit Breaker**: 26+ tests for failure protection
- **Integration**: End-to-end self-healing workflows

---

## 📈 **Performance & Reliability**

### **Key Metrics**
- **🎯 Uptime**: 99.9% target with self-healing
- **⚡ API Response**: <500ms average
- **🔄 Recovery Time**: <5 seconds after connectivity restoration
- **📧 Alert Speed**: <30 seconds for critical issues
- **💾 Memory Usage**: <512MB typical
- **🖨️ Print Success**: 99%+ with intelligent retry

### **Self-Healing Capabilities**
- **Automatic Recovery** from temporary failures
- **Proactive Problem Prevention** via health monitoring
- **Intelligent Failure Handling** with circuit breakers
- **Zero Manual Intervention** for common issues
- **Test commit for auto-updater.**

---

## 📋 **System Requirements**

### **Hardware**
- **Raspberry Pi 4** (4GB+ RAM recommended)
- **Epson TM-m30III** POS Printer
- **32GB+ MicroSD Card** (Class 10)
- **Stable Internet Connection**

### **Software**
- **Raspberry Pi OS** (64-bit recommended)
- **Python 3.11+**
- **SQLite 3**
- **CUPS** (for printer management)

---

## 🚀 **Deployment**

### **Production Deployment**
1. **Follow Setup Guide**: [`deployment/raspberry-pi-setup-guide.md`](deployment/raspberry-pi-setup-guide.md)
2. **Run Quick Start**: `./scripts/raspberry-pi-quickstart.sh`
3. **Configure Environment**: Update `.env` file
4. **Setup Notifications**: `python scripts/setup-notifications.py`
5. **Start Service**: `sudo systemctl start wix-printer.service`

### **Monitoring**
- **Service Status**: `sudo systemctl status wix-printer.service`
- **Logs**: `sudo journalctl -u wix-printer.service -f`
- **Health Check**: `curl http://localhost:8000/self-healing/status`
- **Metrics**: `curl http://localhost:8000/health/metrics`

---

## 📖 **Documentation**

### **Stories & Implementation**
- [Epic 1: Core Printing Workflow](docs/stories/)
  - [Story 1.1: Service Setup](docs/stories/1.1.service-setup.md)
  - [Story 1.2: Wix API Integration](docs/stories/1.2.wix-api-integration.md)
  - [Story 1.3: Basic Printing](docs/stories/1.3.basic-printing.md)
  - [Story 1.4: Custom Receipt Layouts](docs/stories/1.4.custom-receipt-layouts.md)

- [Epic 2: Self-Healing System](docs/stories/)
  - [Story 2.1: Offline Queue](docs/stories/2.1.offline-queue.md)
  - [Story 2.2: Automatic Recovery](docs/stories/2.2.automatic-recovery.md)
  - [Story 2.3: Error Notifications](docs/stories/2.3.error-notifications.md)
  - [Story 2.4: Self-Healing Mechanisms](docs/stories/2.4.self-healing.md) ⭐

### **Technical Documentation**
- [Architecture Overview](docs/architecture.md)
- [Deployment Guide](deployment/raspberry-pi-setup-guide.md)
- [QA Gates](docs/qa/gates/)

---

## 🤝 **Contributing**

### **Development Workflow**
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### **Code Standards**
- **Python 3.11+** compatibility
- **Type hints** for all functions
- **Comprehensive tests** (>90% coverage)
- **Documentation** for all public APIs

---

## 📜 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎉 **Epic 2 Achievement**

**🏆 Complete Autonomous Restaurant System**

This project represents a complete transformation from a simple printer service to a fully autonomous, self-healing restaurant system. Epic 2 delivers:

- **Zero Manual Intervention** for common operational issues
- **Proactive Problem Prevention** through intelligent monitoring
- **Intelligent Failure Recovery** with exponential backoff and circuit breakers
- **Complete Operational Visibility** through comprehensive APIs and notifications

**Ready for mission-critical restaurant operations!** 🚀

---

## 📞 **Support**

- **Issues**: [GitHub Issues](https://github.com/napoleonmm83/wix-pos-printer/issues)
- **Documentation**: [Wiki](https://github.com/napoleonmm83/wix-pos-printer/wiki)
- **Email**: support@your-domain.com

---

**Built with ❤️ for restaurant automation**
