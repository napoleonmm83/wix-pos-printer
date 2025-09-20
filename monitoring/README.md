# Recovery Monitoring System

## Übersicht

Dieses Monitoring-System überwacht die automatische Wiederherstellung (Story 2.2) des Wix Printer Service und stellt Dashboards, Alerting und Performance-Monitoring bereit.

## 🎯 Setup Status

✅ **Monitoring Setup Complete** - Alle Konfigurationsdateien und Scripts wurden erstellt

## 📁 Verzeichnisstruktur

```
monitoring/
├── recovery-dashboard.md          # Monitoring-Dokumentation
├── setup-monitoring.py           # Setup-Script (bereits ausgeführt)
├── health-check.py               # System Health Check
├── performance-monitor.py        # Performance Monitoring
├── install-monitoring.sh         # Service Installation
├── dashboards/
│   ├── recovery-status.json      # Status Dashboard Template
│   └── recovery-history.json     # History Dashboard Template
└── systemd/
    ├── recovery-health-check.service
    ├── recovery-health-check.timer
    └── recovery-performance-monitor.service

config/monitoring/
├── recovery-monitoring.json      # Monitoring-Konfiguration
└── alerts.json                  # Alert-Definitionen

logs/recovery/                    # Performance-Logs (wird erstellt)
```

## 🚀 Nächste Schritte

### 1. Health Check testen

```bash
# Test des Health Check Scripts
python3 monitoring/health-check.py
```

**Erwartete Ausgabe** (wenn Service läuft):
```
Recovery System Health Check - 2025-09-19 20:40:00
============================================================
✓ Recovery Manager: Online
  No active recovery session
✓ Offline Queue: 0 items
✓ Connectivity Monitor: Online
  Printer: online
  Internet: online
============================================================
Health Check Result: 3/3 checks passed
✓ All systems operational
```

### 2. Monitoring Services installieren

```bash
# Installation der systemd Services (auf Raspberry Pi)
./monitoring/install-monitoring.sh
```

### 3. Performance Monitoring starten

```bash
# Manueller Start für Tests
python3 monitoring/performance-monitor.py
```

## 📊 Monitoring Dashboards

### Real-Time Status Dashboard

**API Endpoint**: `GET /recovery/status`

**Überwacht**:
- Aktuelle Recovery Session
- Recovery Phase und Progress
- Verarbeitete/Fehlgeschlagene Items
- Recovery-Typ

### Recovery History Dashboard

**API Endpoint**: `GET /recovery/history`

**Überwacht**:
- Recovery Sessions (letzte 24h/7d/30d)
- Erfolgsrate nach Recovery-Typ
- Durchschnittliche Recovery-Dauer
- Fehleranalyse

### Queue Statistics Dashboard

**API Endpoint**: `GET /recovery/statistics`

**Überwacht**:
- Queue-Größe nach Priorität
- Recovery Urgency Level
- Ältester Queue-Item
- Items kurz vor Ablauf

## 🚨 Alerting Konfiguration

### Critical Alerts (Sofortige Benachrichtigung)

- **Recovery Failure**: Recovery Session fehlgeschlagen
- **Queue Overflow**: Queue > 1000 Items
- **Recovery Timeout**: Recovery > 30 Minuten

### Warning Alerts (Überwachung erforderlich)

- **High Failure Rate**: Erfolgsrate < 80% (24h)
- **Queue Aging**: Ältester Item > 6 Stunden

### Info Alerts (Informational)

- **Recovery Completed**: Erfolgreiche Recovery-Completion

## 📈 Performance Thresholds

### Warning Thresholds
- Recovery Initiation > 10 Sekunden
- Batch Processing < 5 Jobs/Sekunde
- Memory Usage > 500MB während Recovery
- Recovery Duration > 15 Minuten

### Critical Thresholds
- Recovery Initiation > 30 Sekunden
- Batch Processing < 1 Job/Sekunde
- Memory Usage > 1GB während Recovery
- Recovery Duration > 60 Minuten

## 🔧 Konfiguration

### Monitoring Configuration

**Datei**: `config/monitoring/recovery-monitoring.json`

```json
{
  "recovery_monitoring": {
    "enabled": true,
    "dashboard_refresh_interval": "30s",
    "history_retention_days": 30,
    "alerts": {
      "recovery_failure": {
        "enabled": true,
        "severity": "critical"
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
```

### Alert Configuration

**Datei**: `config/monitoring/alerts.json`

Definiert alle Alert-Regeln mit Bedingungen, Severity-Levels und Benachrichtigungs-Einstellungen.

## 🛠️ Operational Procedures

### Täglich
- [ ] Recovery Success Rate > 95%
- [ ] Keine kritischen Alerts in den letzten 24h
- [ ] Queue Size unter normalen Limits
- [ ] Performance Metrics innerhalb Thresholds

### Wöchentlich
- [ ] Recovery Performance Trend Analysis
- [ ] Error Pattern Analysis
- [ ] Capacity Planning Review
- [ ] Alert Threshold Review

## 🔍 Troubleshooting

### Health Check Fails

1. **Service nicht erreichbar**:
   ```bash
   # Prüfe Service Status
   systemctl status wix-printer-service
   
   # Prüfe API Erreichbarkeit
   curl http://localhost:8000/health
   ```

2. **Recovery Manager Offline**:
   ```bash
   # Prüfe Logs
   tail -f logs/wix_printer_service.log
   
   # Restart Service
   systemctl restart wix-printer-service
   ```

3. **Queue Issues**:
   ```bash
   # Prüfe Queue Status
   curl http://localhost:8000/offline/queue/status
   
   # Manual Queue Cleanup
   curl -X POST http://localhost:8000/offline/queue/cleanup
   ```

### Performance Issues

1. **Hohe Recovery-Zeiten**:
   - Prüfe System Resources (CPU, Memory, Disk I/O)
   - Analysiere Performance-Logs
   - Überprüfe Database Performance

2. **Queue Overflow**:
   - Analysiere Connectivity Status
   - Prüfe Recovery Manager Operation
   - Erwäge Resource-Skalierung

## 📋 Maintenance

### Wöchentliche Wartung
- Queue Cleanup (expired Items)
- Recovery History Archivierung
- Performance Metrics Review
- Alert Configuration Update

### Monatliche Wartung
- Recovery Pattern Analysis
- Capacity Planning Update
- Monitoring Configuration Review
- Dashboard Optimization

## 🔗 Dependencies

- **Story 2.2**: ✅ Implementiert und deployed
- **FastAPI Service**: Muss auf localhost:8000 laufen
- **Story 2.3**: Für E-Mail-Alerting (in Entwicklung)

## 📞 Support

Bei Problemen mit dem Monitoring System:

1. Prüfe Health Check: `python3 monitoring/health-check.py`
2. Analysiere Logs: `tail -f logs/recovery/performance-*.csv`
3. Überprüfe Service Status: `systemctl status recovery-*`
4. Konsultiere Recovery Dashboard Dokumentation

---

**Status**: ✅ Ready for Production  
**Last Updated**: 2025-09-19  
**Version**: 1.0
