# Project Brief: Automatischer Wix-Druckdienst

## 1. Executive Summary
Dieses Projekt befasst sich mit der Entwicklung eines automatisierten Druckdienstes, der auf einem Raspberry Pi läuft. Die Anwendung überwacht das Wix-Bestellsystem des Restaurants auf neue Online- und In-Restaurant-Bestellungen und druckt diese automatisch auf einem Epson TM-m30III POS-Bondrucker aus. Das Hauptproblem, das gelöst wird, ist der manuelle und fehleranfällige Prozess der Bestellübertragung in die Küche und an die Fahrer, was zu Verzögerungen führen kann. Der Kernnutzen liegt in der Steigerung der Effizienz, der Reduzierung von Fehlern und der Beschleunigung der Auftragsabwicklung durch eine zuverlässige, überwachte und mit Selbstheilungsfunktionen ausgestattete Automatisierungslösung.

## 2. Problembeschreibung
Der derzeitige Arbeitsablauf zur Bearbeitung von Online- und In-Restaurant-Bestellungen ist manuell und ineffizient. Mitarbeiter müssen aktiv das Wix-System auf neue Bestellungen überwachen, diese manuell abschreiben oder mündlich an die Küche sowie die Lieferfahrer weiterleiten. Dieser Prozess bindet wertvolle Personalressourcen, ist besonders in Stosszeiten fehleranfällig und führt zu Verzögerungen. Die direkten Folgen sind eine langsamere Bestellabwicklung, Übertragungsfehler bei Bestelldetails und im schlimmsten Fall komplett übersehene Bestellungen. Dies resultiert in unzufriedenen Kunden, potenziellen Umsatzeinbussen und unnötigem Stress für das Personal.

## 3. Vorgeschlagene Lösung
Die vorgeschlagene Lösung ist ein eigenständiger, immer aktiver Softwaredienst, der auf einem energieeffizienten Raspberry Pi im Restaurant läuft. Dieser Dienst verbindet sich direkt mit der API von Wix, um in Echtzeit auf alle neuen Bestellungen zu lauschen. Sobald eine Bestellung erfasst wird, formatiert die Anwendung die Daten automatisch für drei verschiedene, anpassbare Belegtypen (Küche, Fahrer, Kunde) und sendet sie an den Drucker. Das System ist auf maximale Zuverlässigkeit und Autonomie ausgelegt; es verfügt über Mechanismen zur Überwachung und kann bei Störungen proaktiv Benachrichtigungen senden und versuchen, sich selbst zu heilen.

## 4. Zielbenutzer
* **Primäre Benutzergruppe: Küchen- & Servicepersonal:** Benötigen sofortige, klare und fehlerfreie Bestellinformationen, um die Zubereitung korrekt und ohne Verzögerung zu starten.
* **Sekundäre Benutzergruppe: Lieferfahrer:** Benötigen einen eindeutigen Beleg mit allen relevanten Lieferinformationen (Adresse, Bestellung, Zahlungsstatus), um die Auslieferung effizient und korrekt abzuwickeln.

## 5. Ziele & Erfolgsmetriken
* **Geschäftsziele:** Effizienz steigern, Fehlerquote senken, Durchlaufzeit verkürzen.
* **Benutzer-Erfolgsmetriken:** Das Personal erhält 100% der Bestellungen sofort und korrekt; Fahrer erhalten für jede Lieferung einen vollständigen und eindeutigen Beleg.
* **KPIs:** System-Verfügbarkeit > 99.5%, 0 verlorene Bestellungen, Erfolgsrate der Benachrichtigungen > 98%.

## 6. MVP-Umfang
* **Kernfunktionen:** Wix-API-Anbindung für Online-Bestellungen, automatischer Druck der 3 Belegtypen, Zuverlässigkeit bei Neustart, Offline-Pufferung, Basis-Benachrichtigung per E-Mail.
* **Nicht im MVP-Umfang:** Grafisches Dashboard, erweiterte Benachrichtigungen (Webhook/Push), erweiterte Selbstheilung, Druck von In-Restaurant-Bestellungen.
* **Erfolgskriterien:** 99% aller Online-Bestellungen über 2 Wochen korrekt und automatisch gedruckt.

## 7. Post-MVP-Vision
* **Phase 2:** Erweiterung auf In-Restaurant-Bestellungen, Implementierung erweiterter Benachrichtigungen, Entwicklung eines Überwachungs-Dashboards.
* **Langfristig:** Ausbau zur Management-Zentrale mit Analysen; Unterstützung für mehrere Drucker und weitere Bestellplattformen.

## 8. Technische Überlegungen
* **Plattform:** Raspberry Pi (Modell 4+) mit Raspberry Pi OS, ressourcenschonender 24/7-Betrieb.
* **Technologie:** Backend in Python/Node.js/Go; leichtgewichtige DB wie SQLite für Pufferung; lokale Ausführung ohne Cloud-Server.
* **Architektur:** Monolithischer Dienst ("Daemon"), robuste Integration mit Wix-API und Epson-Drucker (USB/LAN), sichere Speicherung von API-Keys.

## 9. Einschränkungen & Annahmen
* **Einschränkungen:** Gebunden an Raspberry Pi, Epson TM-m30III und die Wix-API.
* **Annahmen:** Stabile Strom- und Internetversorgung im Restaurant; Wix-API stellt alle nötigen Daten in Echtzeit bereit; Drucker ist über Linux ansteuerbar.

## 10. Risiken & offene Fragen
* **Risiken:** Limitierungen der Wix-API, Komplexität der Drucker-Ansteuerung unter Linux, Netzwerk-Instabilität.
* **Offene Fragen:** Genaue Authentifizierung der Wix-API, Details zum Druckerstatus (Papier niedrig/leer), Umgang mit stornierten Bestellungen.
* **Recherche:** Detaillierte Analyse der Wix-API und der Epson-Drucker-Treiber für Linux erforderlich.