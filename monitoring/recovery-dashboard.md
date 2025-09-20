# Recovery Monitoring Dashboard

## Übersicht

Dieses Dokument definiert das Monitoring und Alerting Setup für die automatische Wiederherstellung (Story 2.2) im Wix Printer Service.

## Recovery Dashboards

### 1. Real-Time Recovery Status Dashboard

**Endpunkt**: `/recovery/status`

**Key Metrics**:
- Aktuelle Recovery Session (falls aktiv)
- Recovery Phase (Validation/Processing/Completion)
- Progress Percentage
- Items Total/Processed/Failed
- Recovery Type (Printer/Internet/Combined/Manual)

**Visualisierung**:
```
┌─────────────────────────────────────────┐
│ Recovery Status Dashboard               │
├─────────────────────────────────────────┤
│ Current Session: printer_recovery_001   │
│ Phase: Processing ████████░░ 80%        │
│ Items: 45/50 processed, 2 failed       │
│ Started: 2025-09-19 20:35:12           │
│ ETA: ~2 minutes                        │
└─────────────────────────────────────────┘
```

### 2. Recovery History Dashboard

**Endpunkt**: `/recovery/history`

**Metriken**:
- Recovery Sessions (letzte 24h/7d/30d)
- Erfolgsrate nach Recovery-Typ
- Durchschnittliche Recovery-Dauer
- Häufigste Fehlerursachen

**Visualisierung**:
```
Recovery History (Last 7 Days)
┌─────────────────────────────────────────┐
│ Total Sessions: 23                      │
│ Success Rate: 95.7% (22/23)            │
│ Avg Duration: 3m 24s                   │
│                                         │
│ By Type:                               │
│ • Printer Recovery: 15 (93% success)   │
│ • Internet Recovery: 6 (100% success)  │
│ • Combined Recovery: 2 (100% success)  │
└─────────────────────────────────────────┘
```

### 3. Queue Statistics Dashboard

**Endpunkt**: `/recovery/statistics`

**Metriken**:
- Aktuelle Queue-Größe nach Priorität
- Recovery Urgency Level
- Ältester Queue-Item
- Items kurz vor Ablauf

## Alerting Configuration

### 1. Critical Alerts (Sofortige Benachrichtigung)

#### Recovery Failure Alert
```yaml
alert: recovery_failure
condition: recovery_session.status == "failed"
severity: critical
notification: immediate
message: "Recovery session {session_id} failed: {error_message}"
```

#### Queue Overflow Alert
```yaml
alert: queue_overflow
condition: offline_queue.size > 1000
severity: critical
notification: immediate
message: "Offline queue overflow: {queue_size} items, urgency: {urgency_level}"
```

#### Recovery Timeout Alert
```yaml
alert: recovery_timeout
condition: recovery_session.duration > 30_minutes
severity: high
notification: 5_minutes
message: "Recovery session {session_id} running for {duration}, phase: {phase}"
```

### 2. Warning Alerts (Überwachung erforderlich)

#### High Failure Rate Alert
```yaml
alert: high_failure_rate
condition: recovery_success_rate_24h < 80%
severity: warning
notification: 15_minutes
message: "Recovery success rate dropped to {success_rate}% in last 24h"
```

#### Queue Age Alert
```yaml
alert: queue_aging
condition: oldest_queue_item_age > 6_hours
severity: warning
notification: 30_minutes
message: "Oldest queue item is {age} old, urgency: {urgency_level}"
```

### 3. Info Alerts (Informational)

#### Recovery Completion Alert
```yaml
alert: recovery_completed
condition: recovery_session.status == "completed"
severity: info
notification: optional
message: "Recovery completed: {items_processed} items in {duration}"
```

## Performance Monitoring

### 1. Recovery Performance Metrics

**Metriken zu überwachen**:
- Recovery Initiation Time (Ziel: < 5 Sekunden)
- Batch Processing Rate (Ziel: ≥ 10 Jobs/Sekunde)
- Memory Usage während Recovery
- CPU Usage während Recovery
- Database Connection Pool Usage

### 2. System Health Checks

**Kontinuierliche Überwachung**:
```python
# Recovery Manager Health Check
GET /recovery/status
- Response Time: < 500ms
- Recovery Manager Running: True
- Current Session Valid: True/False

# Queue Health Check  
GET /offline/queue/status
- Queue Size: Monitoring
- Database Connectivity: OK
- Queue Processing: Active/Idle

# Connectivity Health Check
GET /connectivity/status
- Printer Status: Online/Offline
- Internet Status: Online/Offline
- Last Check: < 60 seconds ago
```

### 3. Performance Thresholds

**Warning Thresholds**:
- Recovery Initiation > 10 Sekunden
- Batch Processing < 5 Jobs/Sekunde
- Memory Usage > 500MB während Recovery
- Recovery Duration > 15 Minuten

**Critical Thresholds**:
- Recovery Initiation > 30 Sekunden
- Batch Processing < 1 Job/Sekunde
- Memory Usage > 1GB während Recovery
- Recovery Duration > 60 Minuten

## Monitoring Implementation

### 1. Logging Configuration

**Recovery Event Logging**:
```python
# Recovery Session Events
logger.info("Recovery session started", extra={
    "session_id": session.id,
    "recovery_type": session.recovery_type.value,
    "items_total": session.items_total,
    "timestamp": session.started_at.isoformat()
})

# Recovery Progress Events
logger.info("Recovery progress update", extra={
    "session_id": session.id,
    "phase": session.phase.value,
    "items_processed": session.items_processed,
    "items_failed": session.items_failed,
    "progress_percentage": progress_pct
})

# Recovery Completion Events
logger.info("Recovery session completed", extra={
    "session_id": session.id,
    "status": session.phase.value,
    "duration_seconds": duration.total_seconds(),
    "success_rate": success_rate
})
```

### 2. Metrics Collection

**Prometheus Metrics** (Future Enhancement):
```python
# Recovery Metrics
recovery_sessions_total = Counter('recovery_sessions_total', ['type', 'status'])
recovery_duration_seconds = Histogram('recovery_duration_seconds', ['type'])
recovery_items_processed = Counter('recovery_items_processed_total', ['type'])
recovery_items_failed = Counter('recovery_items_failed_total', ['type'])

# Queue Metrics
offline_queue_size = Gauge('offline_queue_size_total', ['priority'])
offline_queue_age_seconds = Histogram('offline_queue_age_seconds')
```

### 3. Dashboard Integration

**Grafana Dashboard** (Future Enhancement):
- Recovery Session Timeline
- Success Rate Trends
- Performance Metrics Graphs
- Queue Size and Age Visualization
- Error Rate Analysis

## Operational Procedures

### 1. Recovery Monitoring Checklist

**Täglich**:
- [ ] Recovery Success Rate > 95%
- [ ] Keine kritischen Alerts in den letzten 24h
- [ ] Queue Size unter normalen Limits
- [ ] Performance Metrics innerhalb Thresholds

**Wöchentlich**:
- [ ] Recovery Performance Trend Analysis
- [ ] Error Pattern Analysis
- [ ] Capacity Planning Review
- [ ] Alert Threshold Review

### 2. Incident Response

**Recovery Failure Response**:
1. Überprüfe Recovery Manager Status
2. Analysiere Fehler-Logs
3. Prüfe System Resources (Memory, CPU, Disk)
4. Validiere Database Connectivity
5. Trigger Manual Recovery falls erforderlich

**Queue Overflow Response**:
1. Analysiere Queue Growth Rate
2. Überprüfe Connectivity Status
3. Validiere Recovery Manager Operation
4. Erwäge Queue Cleanup für expired Items
5. Skaliere Resources falls erforderlich

### 3. Maintenance Procedures

**Wöchentliche Wartung**:
- Queue Cleanup (expired Items)
- Recovery History Archivierung
- Performance Metrics Review
- Alert Configuration Update

**Monatliche Wartung**:
- Recovery Pattern Analysis
- Capacity Planning Update
- Monitoring Configuration Review
- Dashboard Optimization

## Configuration Files

### 1. Monitoring Configuration

**monitoring.yml**:
```yaml
recovery_monitoring:
  enabled: true
  dashboard_refresh_interval: 30s
  history_retention_days: 30
  
  alerts:
    recovery_failure:
      enabled: true
      severity: critical
      
    queue_overflow:
      enabled: true
      threshold: 1000
      severity: critical
      
    recovery_timeout:
      enabled: true
      threshold_minutes: 30
      severity: high

  performance_thresholds:
    recovery_initiation_seconds: 5
    batch_processing_rate: 10
    memory_usage_mb: 500
    max_recovery_duration_minutes: 15
```

### 2. Logging Configuration

**logging.yml**:
```yaml
loggers:
  recovery_manager:
    level: INFO
    handlers: [file, console]
    
  offline_queue:
    level: INFO
    handlers: [file, console]
    
formatters:
  recovery_formatter:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    datefmt: '%Y-%m-%d %H:%M:%S'
```

## Next Steps

1. **Implement Basic Monitoring**: API Endpoints bereits verfügbar
2. **Setup Alerting**: E-Mail Benachrichtigungen (wird in Story 2.3 implementiert)
3. **Performance Baseline**: Sammle 1 Woche Baseline-Daten
4. **Dashboard Creation**: Erstelle Web-basierte Dashboards
5. **Advanced Monitoring**: Prometheus/Grafana Integration (Future)

---

**Status**: Ready for Implementation
**Dependencies**: Story 2.2 (✅ Completed), Story 2.3 (für E-Mail Alerts)
**Estimated Effort**: 2-3 Tage für Basic Setup
