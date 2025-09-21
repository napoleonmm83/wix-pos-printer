---
description: Anleitung zum erneuten Drucken von Bestellungen über die Web-Oberfläche
---

# Funktion: Erneutes Drucken von Bestellungen über die Web-Oberfläche

Diese Funktion ermöglicht es dem Servicepersonal, eine Bestellung einfach und schnell erneut zu drucken, ohne technische Kenntnisse zu benötigen.

## Zusammenfassung der Funktion

*   **Einfache Web-Oberfläche:** Anstelle eines technischen API-Endpunkts gibt es jetzt eine einfache Webseite, die direkt vom Raspberry Pi bereitgestellt wird.
*   **Leichte Erreichbarkeit:** Das Servicepersonal kann diese Seite von jedem Gerät (Handy, Tablet, Kasse) im selben WLAN aufrufen, indem es die IP-Adresse des Raspberry Pi gefolgt von Port 5000 in den Browser eingibt (z.B. `http://192.168.1.123:5000`).
*   **Intuitive Bedienung:** Die Seite zeigt eine Liste der letzten 10 Bestellungen. Ein einfacher Klick auf den **"Erneut Drucken"**-Button neben einer Bestellung genügt, um den Druckvorgang erneut zu starten.
*   **Sicher und Robust:** Die Seite ist nur im lokalen Netzwerk erreichbar. Der Druckauftrag wird an den Haupt-Drucker-Service übergeben und profitiert von dessen kompletter Logik (Warteschlange, Fehlerbehandlung etc.).
