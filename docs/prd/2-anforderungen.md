# 2. Anforderungen
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