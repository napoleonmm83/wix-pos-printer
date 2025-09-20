# Production Deployment Plan v2.0 - Stories 2.2 & 2.3

## 🎯 Deployment Overview

**Deployment Scope**: 
- Story 2.2: Automatic Recovery + Monitoring System
- Story 2.3: Error Notifications + SMTP Integration
**Target Environment**: Raspberry Pi Production
**Deployment Date**: Ready for immediate deployment
**Estimated Duration**: 2-3 hours (inkl. Testing)
**Downtime**: ~20-30 Minuten (Rolling Update)

## 📋 Pre-Deployment Status Check

### ✅ Story Readiness
- **Story 2.1**: ✅ DONE (Offline Queue - bereits deployed)
- **Story 2.2**: ✅ DONE (QA Score: 97/100)
- **Story 2.3**: ✅ DONE (QA Score: 94/100)
- **Monitoring System**: ✅ Ready (comprehensive setup)
- **Database Migrations**: ✅ Ready (automated)

### 🔧 Infrastructure Requirements
- **Raspberry Pi**: 4GB RAM, 32GB Storage (minimum)
- **Network**: Internet + Printer connectivity
- **SMTP Server**: Gmail/Outlook/Custom SMTP access
- **Database**: SQLite with backup strategy
- **Python**: 3.11+ with virtual environment

## 🚀 Deployment Phases

### Phase 1: Pre-Deployment Setup (30 minutes)

#### 1.1 System Backup & Preparation
```bash
# Create comprehensive backup
sudo mkdir -p /opt/backups/$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/$(date +%Y%m%d_%H%M%S)"

# Backup database
sudo cp /opt/wix-printer-service/data/printer_service.db $BACKUP_DIR/

# Backup service files
sudo tar -czf $BACKUP_DIR/service_backup.tar.gz /opt/wix-printer-service/

# Backup systemd services
sudo cp /etc/systemd/system/wix-printer-service.service $BACKUP_DIR/

# Stop current service
sudo systemctl stop wix-printer-service
```

#### 1.2 Environment Preparation
```bash
# Create new directories
sudo mkdir -p /opt/wix-printer-service/monitoring
sudo mkdir -p /opt/wix-printer-service/config/monitoring
sudo mkdir -p /opt/wix-printer-service/logs/recovery
sudo mkdir -p /opt/wix-printer-service/scripts

# Set permissions
sudo chown -R pi:pi /opt/wix-printer-service/
```

### Phase 2: Code Deployment (20 minutes)

#### 2.1 Deploy Story 2.2 Components
```bash
# Deploy Recovery Manager
sudo cp wix_printer_service/recovery_manager.py /opt/wix-printer-service/wix_printer_service/

# Deploy enhanced Offline Queue
sudo cp wix_printer_service/offline_queue.py /opt/wix-printer-service/wix_printer_service/

# Deploy enhanced Print Manager
sudo cp wix_printer_service/print_manager.py /opt/wix-printer-service/wix_printer_service/

# Deploy Monitoring System
sudo cp -r monitoring/* /opt/wix-printer-service/monitoring/
sudo chmod +x /opt/wix-printer-service/monitoring/*.py
sudo chmod +x /opt/wix-printer-service/monitoring/*.sh
```

#### 2.2 Deploy Story 2.3 Components
```bash
# Deploy Notification Service
sudo cp wix_printer_service/notification_service.py /opt/wix-printer-service/wix_printer_service/

# Deploy Database Migrations
sudo cp wix_printer_service/database_migrations.py /opt/wix-printer-service/wix_printer_service/

# Deploy Setup Scripts
sudo cp scripts/setup-notifications.py /opt/wix-printer-service/scripts/
sudo chmod +x /opt/wix-printer-service/scripts/*.py

# Deploy enhanced API
sudo cp wix_printer_service/api/main.py /opt/wix-printer-service/wix_printer_service/api/
```

#### 2.3 Deploy Configuration
```bash
# Copy monitoring configurations
sudo cp -r config/monitoring/* /opt/wix-printer-service/config/monitoring/

# Update systemd services
sudo cp monitoring/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
```

### Phase 3: Database Migration (10 minutes)

#### 3.1 Run Automated Migrations
```bash
# Execute database migrations
cd /opt/wix-printer-service
python3 wix_printer_service/database_migrations.py data/printer_service.db

# Verify migration success
python3 -c "
import sqlite3
conn = sqlite3.connect('data/printer_service.db')
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)
assert 'notification_history' in tables
assert 'recovery_sessions' in tables
print('✓ Database migrations successful')
conn.close()
"
```

### Phase 4: Configuration Setup (30 minutes)

#### 4.1 Environment Configuration
```bash
# Update .env file with new settings
cat >> /opt/wix-printer-service/.env << 'EOF'

# Recovery Manager Settings (Story 2.2)
RECOVERY_BATCH_SIZE=5
RECOVERY_BATCH_DELAY=2.0
RECOVERY_MAX_RETRIES=3
RECOVERY_VALIDATION_TIMEOUT=30

# Notification Service Settings (Story 2.3)
NOTIFICATION_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_FROM_EMAIL=your-email@gmail.com
NOTIFICATION_TO_EMAILS=manager@restaurant.com,owner@restaurant.com
RESTAURANT_NAME=Your Restaurant Name

# Monitoring Settings
MONITORING_ENABLED=true
MONITORING_HEALTH_CHECK_INTERVAL=300
MONITORING_PERFORMANCE_INTERVAL=60
EOF
```

#### 4.2 Interactive SMTP Setup
```bash
# Run interactive notification setup
cd /opt/wix-printer-service
python3 scripts/setup-notifications.py

# This will:
# - Guide through SMTP provider selection
# - Test SMTP connection
# - Send test email
# - Update .env automatically
# - Run database migrations
```

### Phase 5: Service Startup (15 minutes)

#### 5.1 Start Core Service
```bash
# Start main service
sudo systemctl start wix-printer-service
sudo systemctl enable wix-printer-service

# Verify service status
sudo systemctl status wix-printer-service
```

#### 5.2 Start Monitoring Services
```bash
# Install and start monitoring services
sudo /opt/wix-printer-service/monitoring/install-monitoring.sh

# Verify monitoring services
sudo systemctl status recovery-performance-monitor
sudo systemctl status recovery-health-check.timer
```

### Phase 6: Verification & Testing (45 minutes)

#### 6.1 Health Checks
```bash
# Run comprehensive health check
python3 /opt/wix-printer-service/monitoring/health-check.py

# Expected output:
# ✓ Recovery Manager: Online
# ✓ Offline Queue: X items
# ✓ Connectivity Monitor: Online
# ✓ Notification Service: Enabled
```

#### 6.2 API Endpoint Testing
```bash
# Test core endpoints
curl -f http://localhost:8000/health || echo "❌ Health endpoint failed"
curl -f http://localhost:8000/connectivity/status || echo "❌ Connectivity endpoint failed"
curl -f http://localhost:8000/recovery/status || echo "❌ Recovery endpoint failed"
curl -f http://localhost:8000/notifications/status || echo "❌ Notifications endpoint failed"

# Test notification functionality
curl -X POST http://localhost:8000/notifications/test \
  -H "Content-Type: application/json" \
  -d '{"notification_type": "system_error"}'
```

#### 6.3 Integration Testing
```bash
# Test recovery system
curl -X POST http://localhost:8000/recovery/trigger \
  -H "Content-Type: application/json" \
  -d '{"recovery_type": "manual"}'

# Test notification history
curl http://localhost:8000/notifications/history?limit=10

# Test monitoring endpoints
curl http://localhost:8000/recovery/statistics
```

## 🔄 Rollback Plan

### Rollback Triggers
- Health checks fail after 30 minutes
- Critical API endpoints not responding
- Database migration errors
- SMTP configuration failures
- Service startup failures

### Rollback Procedure
```bash
# Stop new services
sudo systemctl stop wix-printer-service
sudo systemctl stop recovery-performance-monitor
sudo systemctl disable recovery-health-check.timer

# Restore database
sudo cp $BACKUP_DIR/printer_service.db /opt/wix-printer-service/data/

# Restore service files
sudo tar -xzf $BACKUP_DIR/service_backup.tar.gz -C /

# Restore systemd service
sudo cp $BACKUP_DIR/wix-printer-service.service /etc/systemd/system/

# Restart old service
sudo systemctl daemon-reload
sudo systemctl start wix-printer-service

# Verify rollback
curl http://localhost:8000/health
```

## 📊 Success Criteria

### Technical Metrics
- [ ] All health checks passing (100%)
- [ ] API response times < 500ms
- [ ] Recovery system operational
- [ ] Notification system functional
- [ ] Monitoring dashboards active
- [ ] Database migrations successful

### Business Metrics
- [ ] Zero order loss during deployment
- [ ] Automatic recovery working
- [ ] Email notifications delivering
- [ ] Monitoring alerts functional
- [ ] System stability maintained

### Performance Benchmarks
- **Recovery Initiation**: < 5 seconds after connectivity restoration
- **Email Delivery**: < 30 seconds after error detection
- **API Response Time**: < 500ms average
- **Memory Usage**: < 512MB total
- **CPU Usage**: < 50% average

## 🚨 Production Checklist

### Pre-Deployment
- [ ] **Backup completed** and verified
- [ ] **SMTP credentials** obtained and tested
- [ ] **Email recipients** configured and notified
- [ ] **Maintenance window** scheduled and communicated
- [ ] **Rollback plan** tested and ready

### During Deployment
- [ ] **Service stopped** gracefully
- [ ] **Code deployed** successfully
- [ ] **Database migrated** without errors
- [ ] **Configuration updated** and validated
- [ ] **Services started** successfully

### Post-Deployment
- [ ] **Health checks** all passing
- [ ] **API endpoints** responding correctly
- [ ] **Notifications** sending successfully
- [ ] **Monitoring** collecting metrics
- [ ] **Performance** within acceptable ranges

## 📧 SMTP Configuration Guide

### Gmail Setup
```bash
# Gmail SMTP Settings
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-character-app-password
```

**Gmail Requirements:**
1. Enable 2-Factor Authentication
2. Generate App Password (not regular password)
3. Use App Password in configuration

### Outlook Setup
```bash
# Outlook SMTP Settings
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-regular-password-or-app-password
```

### Custom SMTP
```bash
# Custom SMTP Settings
SMTP_SERVER=your-smtp-server.com
SMTP_PORT=587  # or 465 for SSL
SMTP_USE_TLS=true  # or false for SSL
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
```

## 📈 Monitoring Setup

### Dashboard URLs (after deployment)
- **Service Health**: http://localhost:8000/health
- **Recovery Status**: http://localhost:8000/recovery/status
- **Notification Status**: http://localhost:8000/notifications/status
- **Queue Statistics**: http://localhost:8000/recovery/statistics
- **API Documentation**: http://localhost:8000/docs

### Log Locations
- **Service Logs**: `/opt/wix-printer-service/logs/wix_printer_service.log`
- **Recovery Logs**: `/opt/wix-printer-service/logs/recovery/`
- **System Logs**: `journalctl -u wix-printer-service -f`

## 🎯 Post-Deployment Actions

### Immediate (0-24 hours)
- [ ] Monitor system stability
- [ ] Verify all functionality working
- [ ] Test notification delivery
- [ ] Collect performance baselines
- [ ] Address any issues immediately

### Short-term (1-7 days)
- [ ] Performance trend analysis
- [ ] User feedback collection
- [ ] Alert threshold optimization
- [ ] Documentation updates
- [ ] Team training on new features

### Long-term (1-4 weeks)
- [ ] Capacity planning review
- [ ] Monitoring optimization
- [ ] Story 2.4 planning
- [ ] Epic 2 completion
- [ ] Lessons learned documentation

---

## 📋 Deployment Execution Summary

**Ready for Production**: ✅ All components tested and validated
**Estimated Downtime**: 20-30 minutes
**Risk Level**: LOW (comprehensive testing and rollback plan)
**Business Impact**: POSITIVE (enhanced reliability and proactive monitoring)

**Key Benefits After Deployment**:
- 🔄 **Automatic Recovery** - Zero manual intervention for connectivity issues
- 📧 **Proactive Notifications** - Immediate alerts for system problems
- 📊 **Comprehensive Monitoring** - Real-time dashboards and metrics
- 🛡️ **Enhanced Reliability** - Robust error handling and self-healing capabilities

**This deployment establishes the complete robustness foundation for the restaurant printing system!** 🚀
