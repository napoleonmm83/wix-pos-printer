# 5. Epic-Details

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