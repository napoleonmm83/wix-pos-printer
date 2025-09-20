# Architektur-Dokument: Automatischer Wix-Druckdienst
**Version: 1.0**

## 1. Einleitung
Dieses Dokument beschreibt die Projektarchitektur für den automatischen Wix-Druckdienst. Es dient als leitender architektonischer Entwurf für die KI-gesteuerte Entwicklung. Da das Projekt keine Benutzeroberfläche hat, ist dieses Dokument die alleinige technische Architekturreferenz. Es wird eine saubere, pragmatische Struktur von Grund auf definiert.

## 2. High-Level-Architektur
Die Architektur basiert auf einem kontinuierlich laufenden, monolithischen Hintergrunddienst (Daemon) in Python auf dem Raspberry Pi. Der Dienst ist ereignisgesteuert und nutzt eine persistente Warteschlange (SQLite) sowie einen Zustandsautomaten, um Zuverlässigkeit und Robustheit bei der Verarbeitung von Wix-Bestellungen zu gewährleisten.

## 3. Tech Stack
| Kategorie | Technologie | Version | Zweck |
| :--- | :--- | :--- | :--- |
| **Sprache** | Python | 3.11.x | Haupt-Programmiersprache |
| **HTTP-Client** | `requests` | ~2.31 | Kommunikation mit der Wix-API |
| **Drucker-Steuerung**|`python-escpos`| ~3.1 | Generierung von Druckbefehlen |
| **Datenbank/Queue** |`sqlite3` | In Python 3.11| Persistente Warteschlange |
| **Service-Management**|`systemd` | System-Standard| Autom. Start & Überwachung |

## 4. Datenmodelle
* **Order:** Bildet die von der Wix-API empfangenen Bestelldaten strukturiert ab.
* **PrintJob:** Repräsentiert einen einzelnen Druckauftrag in der SQLite-Warteschlange.

## 5. Komponenten
Der Dienst ist in 5 logische Komponenten unterteilt: `WixListener`, `OrderProcessor`, `PrintQueue`, `PrintManager`, und `ServiceMonitor & Notifier`.

## 6. Externe APIs
* **Wix Orders API:** Dient dem Empfang von Bestellungen via Webhooks. Dokumentation: https://dev.wix.com/docs
* **SMTP Server:** Dient dem Versand von E-Mail-Benachrichtigungen.

## 7. Kern-Arbeitsabläufe
Sequenzdiagramme definieren den "Happy Path" für erfolgreiche Bestellungen und den Fehlerfall, wenn der Drucker offline ist, inklusive Pufferung und Benachrichtigung.

## 8. REST-API-Spezifikation
Eine interne OpenAPI 3.0 Spezifikation definiert einen `/health`- und einen `/status`-Endpunkt für Monitoring-Zwecke.

## 9. Datenbank-Schema
Eine einzelne Tabelle `print_jobs` in SQLite wird verwendet, um die Druckaufträge persistent zu speichern.

## 10. Source Tree
Eine klare Ordnerstruktur, die Logik, Tests und Konfiguration trennt, ist definiert, inklusive eines `.github/workflows/` Verzeichnisses.

## 11. Infrastruktur und Deployment
Der Deployment-Prozess ist via GitHub Actions und einem Self-Hosted Runner auf dem Raspberry Pi vollständig automatisiert. Ein Rollback erfolgt durch einen `git revert` und anschliessenden Push.

## 12. Fehlerbehandlungs-Strategie
Eine robuste Strategie mit benutzerdefinierten Exceptions, strukturiertem Logging und Timeouts ist definiert.

## 13. Coding Standards
Ein minimaler, aber strikter Satz von Regeln (PEP 8, `black`, `flake8`, keine Hardcodings) ist für den KI-Agenten verbindlich.

## 14. Test-Strategie
Eine umfassende Strategie mit Unit- und Integrationstests (>90% Abdeckung), `pytest` und CI-Integration via GitHub Actions ist geplant.

## 15. Sicherheit
Grundlegende Sicherheitsmassnahmen für Eingabe-Validierung, Secrets Management und Schutz von Kundendaten sind definiert.

## 16. Bericht der Checklisten-Prüfung
* **Status:** Bereit für die Entwicklungsphase. Alle relevanten Sektionen der Architekten-Checkliste wurden erfüllt. Die Architektur ist robust, pragmatisch und gut auf die Anforderungen im PRD abgestimmt.

## 17. Nächste Schritte
Das Architektur-Dokument ist fertiggestellt. Der nächste Schritt ist der Beginn der Entwicklungs-Zyklen mit dem Scrum Master.