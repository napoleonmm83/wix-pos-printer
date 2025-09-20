# Production Deployment Plan - Story 2.2 & Monitoring

## 🎯 Deployment Overview

**Deployment Scope**: Story 2.2 (Automatic Recovery) + Comprehensive Monitoring System
**Target Environment**: Raspberry Pi Production
**Deployment Date**: Geplant für nächste Woche
**Downtime**: ~10-15 Minuten (Rolling Update)

## 📋 Pre-Deployment Checklist

### ✅ Code Readiness
- [x] Story 2.2 Implementation completed
- [x] QA Review passed (Quality Score: 97/100)
- [x] Comprehensive test coverage (20+ tests)
- [x] Monitoring system implemented
- [x] Story status updated to "Done"

### 🔧 Infrastructure Preparation
- [ ] Backup current production database
- [ ] Verify Raspberry Pi system resources
- [ ] Test network connectivity (SMTP, Internet)
- [ ] Prepare rollback plan
- [ ] Schedule maintenance window

### 📊 Monitoring Setup
- [x] Monitoring scripts created
- [x] Dashboard templates prepared
- [x] Alert configurations defined
- [x] systemd services configured
- [ ] SMTP credentials configured
- [ ] Email recipients configured

## 🚀 Deployment Steps

### Phase 1: Pre-Deployment (30 minutes)

#### 1.1 System Backup
```bash
# Backup current database
sudo cp /opt/wix-printer-service/data/printer_service.db /opt/backups/printer_service_$(date +%Y%m%d_%H%M%S).db

# Backup current service files
sudo tar -czf /opt/backups/service_backup_$(date +%Y%m%d_%H%M%S).tar.gz /opt/wix-printer-service/

# Backup systemd service files
sudo cp /etc/systemd/system/wix-printer-service.service /opt/backups/
```

#### 1.2 Environment Preparation
```bash
# Stop current service
sudo systemctl stop wix-printer-service

# Create monitoring directories
sudo mkdir -p /opt/wix-printer-service/monitoring
sudo mkdir -p /opt/wix-printer-service/config/monitoring
sudo mkdir -p /opt/wix-printer-service/logs/recovery

# Set permissions
sudo chown -R pi:pi /opt/wix-printer-service/
```

### Phase 2: Code Deployment (15 minutes)

#### 2.1 Deploy New Code
```bash
# Deploy recovery manager
sudo cp wix_printer_service/recovery_manager.py /opt/wix-printer-service/wix_printer_service/

# Deploy enhanced offline queue
sudo cp wix_printer_service/offline_queue.py /opt/wix-printer-service/wix_printer_service/

# Deploy enhanced print manager
sudo cp wix_printer_service/print_manager.py /opt/wix-printer-service/wix_printer_service/

# Deploy enhanced API
sudo cp wix_printer_service/api/main.py /opt/wix-printer-service/wix_printer_service/api/

# Deploy notification service (Story 2.3)
sudo cp wix_printer_service/notification_service.py /opt/wix-printer-service/wix_printer_service/
```

#### 2.2 Deploy Monitoring System
```bash
# Deploy monitoring files
sudo cp -r monitoring/* /opt/wix-printer-service/monitoring/
sudo cp -r config/monitoring/* /opt/wix-printer-service/config/monitoring/

# Make scripts executable
sudo chmod +x /opt/wix-printer-service/monitoring/*.py
sudo chmod +x /opt/wix-printer-service/monitoring/*.sh
```

### Phase 3: Database Migration (5 minutes)

#### 3.1 Database Schema Updates
```sql
-- Add notification history table
CREATE TABLE IF NOT EXISTS notification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type TEXT NOT NULL,
    context TEXT,
    success BOOLEAN NOT NULL,
    sent_at TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Add recovery sessions table (if not exists from Story 2.2)
CREATE TABLE IF NOT EXISTS recovery_sessions (
    id TEXT PRIMARY KEY,
    recovery_type TEXT NOT NULL,
    phase TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    items_total INTEGER DEFAULT 0,
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    error_message TEXT,
    metadata TEXT
);

-- Add indices for performance
CREATE INDEX IF NOT EXISTS idx_notification_history_type ON notification_history(notification_type);
CREATE INDEX IF NOT EXISTS idx_notification_history_sent_at ON notification_history(sent_at);
CREATE INDEX IF NOT EXISTS idx_recovery_sessions_type ON recovery_sessions(recovery_type);
CREATE INDEX IF NOT EXISTS idx_recovery_sessions_started_at ON recovery_sessions(started_at);
```

### Phase 4: Configuration (10 minutes)

#### 4.1 Environment Configuration
```bash
# Update .env file with new settings
cat >> /opt/wix-printer-service/.env << EOF

# Recovery Manager Settings
RECOVERY_BATCH_SIZE=5
RECOVERY_BATCH_DELAY=2.0
RECOVERY_MAX_RETRIES=3
RECOVERY_VALIDATION_TIMEOUT=30

# Notification Service Settings
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

#### 4.2 Install Monitoring Services
```bash
# Install monitoring systemd services
sudo /opt/wix-printer-service/monitoring/install-monitoring.sh
```

### Phase 5: Service Restart (5 minutes)

#### 5.1 Start Services
```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Start main service
sudo systemctl start wix-printer-service

# Verify service status
sudo systemctl status wix-printer-service

# Start monitoring services
sudo systemctl start recovery-performance-monitor
sudo systemctl enable recovery-health-check.timer
sudo systemctl start recovery-health-check.timer
```

### Phase 6: Verification (15 minutes)

#### 6.1 Health Checks
```bash
# Run health check
python3 /opt/wix-printer-service/monitoring/health-check.py

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/recovery/status
curl http://localhost:8000/connectivity/status
curl http://localhost:8000/offline/queue/status
```

#### 6.2 Functionality Tests
```bash
# Test recovery endpoints
curl http://localhost:8000/recovery/statistics
curl http://localhost:8000/recovery/history

# Test notification configuration
curl -X POST http://localhost:8000/notifications/test

# Verify monitoring
sudo systemctl status recovery-performance-monitor
sudo systemctl status recovery-health-check.timer
```

## 🔄 Rollback Plan

### Rollback Triggers
- Health checks fail after deployment
- Critical API endpoints not responding
- Database migration errors
- Service startup failures

### Rollback Steps
```bash
# Stop new services
sudo systemctl stop wix-printer-service
sudo systemctl stop recovery-performance-monitor
sudo systemctl disable recovery-health-check.timer

# Restore database backup
sudo cp /opt/backups/printer_service_YYYYMMDD_HHMMSS.db /opt/wix-printer-service/data/printer_service.db

# Restore service files
sudo tar -xzf /opt/backups/service_backup_YYYYMMDD_HHMMSS.tar.gz -C /

# Restore systemd service
sudo cp /opt/backups/wix-printer-service.service /etc/systemd/system/

# Restart old service
sudo systemctl daemon-reload
sudo systemctl start wix-printer-service
```

## 📊 Post-Deployment Monitoring

### Immediate Monitoring (First 24 hours)
- [ ] Service uptime and stability
- [ ] API response times
- [ ] Recovery system functionality
- [ ] Notification system operation
- [ ] Database performance
- [ ] System resource usage

### Performance Baselines
- **Recovery Initiation**: < 5 seconds
- **API Response Time**: < 500ms
- **Memory Usage**: < 512MB
- **CPU Usage**: < 50% average
- **Database Queries**: < 100ms average

### Success Criteria
- [ ] All health checks passing
- [ ] Recovery system operational
- [ ] Monitoring dashboards functional
- [ ] No critical errors in logs
- [ ] Email notifications working
- [ ] Performance within thresholds

## 🚨 Emergency Contacts

**Primary**: System Administrator
**Secondary**: Development Team
**Escalation**: Restaurant Manager

## 📝 Deployment Log Template

```
Deployment Date: _______________
Deployment Start Time: _______________
Deployment End Time: _______________

Pre-Deployment Checklist:
[ ] Backup completed
[ ] Environment prepared
[ ] Monitoring configured

Deployment Steps:
[ ] Code deployed
[ ] Database migrated
[ ] Configuration updated
[ ] Services restarted

Verification:
[ ] Health checks passed
[ ] API endpoints responding
[ ] Monitoring active
[ ] Performance acceptable

Issues Encountered:
_________________________________
_________________________________

Resolution Actions:
_________________________________
_________________________________

Deployment Status: SUCCESS / ROLLBACK
Signed: _______________
```

## 📈 Success Metrics

### Technical Metrics
- **Deployment Time**: Target < 30 minutes
- **Downtime**: Target < 15 minutes
- **Rollback Time**: Target < 10 minutes (if needed)
- **Health Check Pass Rate**: Target 100%

### Business Metrics
- **Order Processing Continuity**: No orders lost
- **Recovery Functionality**: Automatic recovery working
- **Notification System**: Alerts functioning
- **System Reliability**: 99.9% uptime target

## 🎯 Next Steps After Deployment

1. **Monitor for 48 hours** - Continuous monitoring of all systems
2. **Collect Performance Baseline** - 1 week of performance data
3. **Fine-tune Thresholds** - Adjust monitoring thresholds based on baseline
4. **User Training** - Train restaurant staff on new monitoring capabilities
5. **Story 2.3 Completion** - Finalize email notification implementation
6. **Story 2.4 Planning** - Begin self-healing mechanisms story

---

**Deployment Status**: 📋 PLANNED  
**Estimated Duration**: 1.5 hours  
**Risk Level**: LOW (comprehensive testing and rollback plan)  
**Business Impact**: MINIMAL (improved reliability and monitoring)
