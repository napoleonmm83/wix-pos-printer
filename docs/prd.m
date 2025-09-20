# Product Requirements Document: Automatischer Wix-Druckdienst
**Version: 1.0**

## 1. Ziele und Hintergrundkontext
* **Ziele:**
    * Die manuelle Arbeitszeit zur Bearbeitung von Online-Bestellungen auf nahezu Null reduzieren.
    * Übertragungsfehler bei Bestellungen eliminieren.
    * Die Zeit vom Bestelleingang bis zum Ausdruck in der Küche drastisch verkürzen.
    * Sicherstellen, dass das Küchenpersonal 100% aller Bestellungen sofort, korrekt und lesbar erhält.
    * Sicherstellen, dass die Lieferfahrer für jede Tour einen vollständigen und eindeutigen Beleg erhalten.
* **Hintergrundkontext:**
    Der aktuelle manuelle Prozess zur Handhabung von Wix-Bestellungen ist ineffizient, bindet Personal und ist besonders in Stosszeiten fehleranfällig. Dieses Projekt löst das Problem durch einen autonomen Dienst auf einem Raspberry Pi, der eine direkte, zuverlässige und überwachte Brücke zwischen dem Wix-Bestellsystem und dem physischen Bondrucker schlägt und so den gesamten Arbeitsablauf automatisiert.
* **Änderungsprotokoll:**
    | Datum | Version | Beschreibung | Autor |
    | :--- | :--- | :--- | :--- |
    | 18.09.2025 | 1.0 | Ersterstellung des Dokuments | John (PM) |

---
## 2. Anforderungen
* **Funktionale Anforderungen (FR):**
    * **FR1:** Das System muss sich mit der Wix-API verbinden und neue Bestelldaten in Echtzeit empfangen.
    * **FR2:** Das System muss sowohl Online-Bestellungen (von der Website) als auch In-Restaurant-Bestellungen (aus der Wix-App) verarbeiten können.
    * **FR3:** Das System muss aus einer einzigen Bestellung drei unterschiedliche Belegtypen generieren: einen für die Küche, einen für den Lieferfahrer und einen für den Kunden.
    * **FR4:** Das Layout für jeden Belegtyp muss anpassbar sein (z.B. Küchenbeleg grösser und ohne Preise).
    * **FR5:** Das System muss die generierten Belege an den angeschlossenen Epson TM-m30III Drucker senden.
    * **FR6:** Das System muss eingehende Bestellungen in einer Warteschlange zurückhalten, falls der Drucker offline ist, und diese automatisch drucken, sobald der Drucker wieder verfügbar ist.
* **Nicht-funktionale Anforderungen (NFR):**
    * **NFR1:** Der Dienst muss beim Hochfahren des Raspberry Pi automatisch starten.
    * **NFR2:** Der Dienst muss Unterbrechungen der Internetverbindung erkennen und selbstständig periodisch versuchen, die Verbindung wiederherzustellen.
    * **NFR3:** Das System muss bei Druckerfehlern (z.B. offline, kein Papier) Benachrichtigungen via E-Mail versenden können (Webhook & Push-Nachrichten sind für eine spätere Version vorgesehen).
    * **NFR4:** Das System soll eine proaktive Benachrichtigung senden, wenn der Papiervorrat des Druckers zur Neige geht (Abhängig von der Unterstützung durch die Drucker-API).
    * **NFR5:** Der Dienst muss Selbstheilungsstrategien implementieren, mindestens aber intelligente Wiederholungsversuche (Smart Retries) für fehlgeschlagene Druckaufträge.
    * **NFR6:** Die Anwendung muss ressourcenschonend sein, um stabil im 24/7-Betrieb auf einem Raspberry Pi zu laufen.
    * **NFR7:** API-Schlüssel und andere sensible Zugangsdaten müssen sicher auf dem Gerät gespeichert werden.

---
## 3. Technische Annahmen
* **Repository-Struktur:** Polyrepo (ein einziges Repository für den Dienst).
* **Service-Architektur:** Monolith (eine einzelne, eigenständige Anwendung).
* **Test-Anforderungen:** Unit-Tests und Integrationstests sind erforderlich.
* **Zusätzliche Annahmen:** Die Zielplattform ist ein Raspberry Pi (Modell 4 oder neuer) unter einem Debian-basierten Linux-Betriebssystem (z.B. Raspberry Pi OS).

---
## 4. Epic-Liste
1.  **Epic 1: Projekt-Grundlagen & Kern-Druckworkflow**
    * **Ziel:** Die grundlegende Service-Infrastruktur auf dem Raspberry Pi aufsetzen und einen zuverlässigen End-to-End-Workflow implementieren, um eine Online-Bestellung von Wix zu empfangen und alle drei definierten Belegtypen korrekt auszudrucken.
2.  **Epic 2: Robustheit, Überwachung & Selbstheilung**
    * **Ziel:** Den Kerndienst um die volle Bandbreite an Zuverlässigkeits-, Fehlerbehandlungs-, Benachrichtigungs- und Selbstheilungsfunktionen erweitern, um den Service autonom und produktionsreif zu machen.

---
## 5. Epic-Details

### 5.1: Epic 1 - Projekt-Grundlagen & Kern-Druckworkflow
* **Story 1.1: Service-Einrichtung und Erreichbarkeit:** Eine grundlegende, automatisch startende Service-Anwendung auf dem Raspberry Pi einrichten.
* **Story 1.2: Anbindung an Wix-API und Bestell-Protokollierung:** Den Dienst sicher mit der Wix-API verbinden und neue Online-Bestellungen empfangen und protokollieren.
* **Story 1.3: Implementierung des Basis-Drucks:** Eine einfache, unformatierte Version einer Bestellung auf dem Epson-Drucker ausdrucken.
* **Story 1.4: Implementierung der benutzerdefinierten Beleg-Layouts:** Die Bestelldaten analysieren und drei verschiedene, korrekt formatierte Belege (Küche, Fahrer, Kunde) drucken.

### 5.2: Epic 2 - Robustheit, Überwachung & Selbstheilung
* **Story 2.1: Implementierung der Offline-Warteschlange:** Eingehende Bestellungen sicher speichern, wenn der Drucker oder das Internet offline ist.
* **Story 2.2: Automatische Wiederherstellung und Druck aus der Warteschlange:** Alle aufgestauten Bestellungen automatisch drucken, sobald die Systeme wieder verfügbar sind.
* **Story 2.3: Implementierung der Fehler-Benachrichtigungen:** E-Mail-Benachrichtigungen bei kritischen Problemen (z.B. Drucker/Internet offline) versenden.
* **Story 2.4: Implementierung von Selbstheilungs-Mechanismen:** Automatische Wiederholungsversuche für Druckaufträge und einen kontrollierten Selbst-Neustart des Dienstes implementieren.

---
## 6. Bericht der Checklisten-Prüfung
**Executive Summary:**
* **PRD-Vollständigkeit:** Hoch (100% der relevanten Sektionen bestanden).
* **MVP-Umfang:** Angemessen und klar definiert.
* **Status:** Bereit für die Architektur-Phase.
* **Kritische Lücken:** Keine.

---
## 7. Nächste Schritte
**Aufforderung an den Architect:**
> Dieses Product Requirements Document (PRD) beschreibt einen "headless" Dienst für einen Raspberry Pi zum Drucken von Wix-Bestellungen. Bitte überprüfen Sie es gründlich und erstellen Sie ein entsprechendes technisches Architektur-Dokument. Achten Sie besonders auf die nicht-funktionalen Anforderungen bezüglich Zuverlässigkeit, Überwachung und Selbstheilung sowie auf die spezifischen Hardware- (Raspberry Pi, Epson TM-m30III) und API- (Wix) Einschränkungen.