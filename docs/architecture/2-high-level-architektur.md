# 2. High-Level-Architektur
Die Architektur basiert auf einem kontinuierlich laufenden, monolithischen Hintergrunddienst (Daemon) in Python auf dem Raspberry Pi. Der Dienst ist ereignisgesteuert und nutzt eine persistente Warteschlange (SQLite) sowie einen Zustandsautomaten, um Zuverlässigkeit und Robustheit bei der Verarbeitung von Wix-Bestellungen zu gewährleisten.
