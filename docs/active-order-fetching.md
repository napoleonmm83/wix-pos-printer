# Aktives Abholen von Wix Bestellungen

Diese Funktionalität ermöglicht es, aktiv neue Bestellungen von der Wix Orders API in einem bestimmten Zeitraum abzuholen, anstatt nur auf Webhooks zu warten. Das System bietet sowohl manuelle API-Endpunkte als auch eine automatische Background-Task-Funktionalität.

## Automatische Bestellungsüberwachung (Auto-Check)

Das System kann automatisch alle 30 Sekunden (konfigurierbar) nach neuen Bestellungen suchen und diese automatisch zum Drucken weiterleiten.

### Konfiguration der automatischen Überwachung

```env
# Auto-Check aktivieren/deaktivieren
AUTO_CHECK_ENABLED=true

# Überprüfungsintervall in Sekunden (Standard: 30)
AUTO_CHECK_INTERVAL=30

# Zeitraum für die Rückschau in Stunden (Standard: 1)
AUTO_CHECK_HOURS_BACK=1
```

### Auto-Check Steuerungsendpunkte

#### Status abrufen
**GET** `/auto-check/status`

Zeigt den aktuellen Status der automatischen Überwachung an.

```json
{
  "enabled": true,
  "running": true,
  "interval_seconds": 30,
  "hours_back": 1,
  "api_configured": true,
  "statistics": {
    "total_processed": 45,
    "processed_today": 12,
    "last_check": "2024-01-01T15:30:00Z"
  }
}
```

#### Auto-Check manuell starten
**POST** `/auto-check/start`

#### Auto-Check manuell stoppen
**POST** `/auto-check/stop`

### Funktionsweise der automatischen Überwachung

1. **Kontinuierliche Überwachung**: Alle 30 Sekunden (oder konfiguriertes Intervall)
2. **Intelligente Duplikatserkennung**: Bereits verarbeitete Bestellungen werden nicht erneut gedruckt
3. **Datenbanktracking**: Alle überprüften Bestellungen werden in der Datenbank verfolgt
4. **Automatische Weiterleitung**: Neue Bestellungen werden automatisch an den Drucker-Service gesendet
5. **Umfassendes Logging**: Alle Aktivitäten werden protokolliert

### Datenbank-Schema für Auto-Check

Das System erstellt automatisch eine Tabelle `auto_checked_orders`:

```sql
CREATE TABLE auto_checked_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wix_order_id TEXT UNIQUE NOT NULL,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_for_print BOOLEAN DEFAULT FALSE,
    print_status TEXT DEFAULT 'pending'
);
```

## Manuelle API-Endpunkte

### 1. `/orders/fetch` - Bestellungen nach Zeitraum abrufen

**GET** `/orders/fetch`

#### Parameter:
- `from_date` (optional): Startdatum im ISO-Format (z.B. "2024-01-01T00:00:00Z")
- `to_date` (optional): Enddatum im ISO-Format (z.B. "2024-01-31T23:59:59Z")
- `hours_back` (optional): Stunden zurück von jetzt (Alternative zu from_date/to_date)
- `limit` (optional): Maximale Anzahl Bestellungen (1-100, Standard: 50)
- `process_orders` (optional): Ob Bestellungen automatisch zum Drucken verarbeitet werden sollen (Standard: false)

#### Beispiele:

```bash
# Bestellungen der letzten 2 Stunden abrufen
GET /orders/fetch?hours_back=2

# Bestellungen eines bestimmten Zeitraums abrufen
GET /orders/fetch?from_date=2024-01-01T00:00:00Z&to_date=2024-01-01T23:59:59Z

# Bestellungen abrufen und automatisch drucken
GET /orders/fetch?hours_back=1&process_orders=true

# Standard: Bestellungen der letzten 24 Stunden
GET /orders/fetch
```

### 2. `/orders/recent` - Aktuelle Bestellungen (Vereinfacht)

**GET** `/orders/recent`

#### Parameter:
- `hours` (optional): Stunden zurück (1-168, Standard: 1)
- `limit` (optional): Maximale Anzahl Bestellungen (1-100, Standard: 20)
- `process_orders` (optional): Automatisch drucken (Standard: false)

#### Beispiele:

```bash
# Bestellungen der letzten Stunde
GET /orders/recent

# Bestellungen der letzten 4 Stunden mit automatischem Druck
GET /orders/recent?hours=4&process_orders=true
```

## Konfiguration

Stellen Sie sicher, dass diese Umgebungsvariablen in Ihrer `.env` Datei konfiguriert sind:

```env
# Wix API Konfiguration
WIX_API_KEY=your_wix_api_key_here
WIX_SITE_ID=your_wix_site_id_here
WIX_API_BASE_URL=https://www.wixapis.com

# Drucker Service URL (für automatische Verarbeitung)
PRINTER_SERVICE_URL=http://localhost:8000
```

## API-Response Format

```json
{
  "success": true,
  "fetched_count": 5,
  "date_range": {
    "from_date": "2024-01-01T00:00:00Z",
    "to_date": "2024-01-01T23:59:59Z"
  },
  "orders": [
    {
      "id": "order-id-1",
      "createdDate": "2024-01-01T12:00:00Z",
      "status": "APPROVED",
      // ... weitere Bestelldetails
    }
  ],
  "processed_for_printing": {
    "count": 3,
    "order_ids": ["order-id-1", "order-id-2", "order-id-3"]
  }
}
```

## Verwendungsszenarien

### Automatische Überwachung (Empfohlen)
- **Primärer Betriebsmodus**: Kontinuierliche Überwachung auf neue Bestellungen
- **Webhook-Backup**: Fängt Bestellungen ab, die über Webhooks verpasst wurden
- **Ausfallsicherheit**: Funktioniert auch bei temporären Webhook-Ausfällen
- **Zero-Configuration**: Läuft automatisch im Hintergrund nach dem Start

### Manuelle Endpunkte
1. **Manuelle Synchronisation**: Bestellungen abrufen, die möglicherweise über Webhook verpasst wurden
2. **Historische Daten**: Alte Bestellungen für Reporting oder Nachbearbeitung abrufen
3. **Bulk-Verarbeitung**: Mehrere Bestellungen auf einmal für das Drucken verarbeiten
4. **Debugging**: Manuelle Überprüfung für Debugging-Zwecke

## Sicherheit

- Die API verwendet Ihre Wix API-Credentials (WIX_API_KEY und WIX_SITE_ID)
- Stellen Sie sicher, dass diese Credentials sicher gespeichert sind
- Die Endpunkte haben keine zusätzliche Authentifizierung - implementieren Sie bei Bedarf API-Keys oder andere Sicherheitsmaßnahmen

## Fehlerbehandlung

Die API behandelt verschiedene Fehlerszenarien:
- Fehlende Wix API-Credentials (500 Internal Server Error)
- Netzwerkfehler zur Wix API (503 Service Unavailable)
- Wix API-Fehler (502 Bad Gateway)
- Interne Serverfehler (500 Internal Server Error)

Alle Fehler werden geloggt für Debugging-Zwecke.