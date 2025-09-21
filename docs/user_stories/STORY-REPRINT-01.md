# User Story: Reprint Orders via Local Web UI

*   **Title:** Reprint Orders via Local Web UI
*   **ID:** `STORY-REPRINT-01`
*   **As a:** Service Staff Member
*   **I want:** A simple web page, accessible from any device on the local network
*   **So that I can:** Quickly and easily reprint a recent order without needing technical assistance.

---

### Acceptance Criteria (AC)

1.  **AC-1 (Accessibility):** The web page MUST be accessible by navigating to the Raspberry Pi's IP address on port 5000 (e.g., `http://<pi-ip>:5000`).
2.  **AC-2 (Order List):** The page MUST display a list of the last 10 processed orders, sorted with the most recent at the top.
3.  **AC-3 (Order Details):** Each order in the list MUST clearly display the `Wix Order ID` and the `timestamp` of its creation.
4.  **AC-4 (Reprint Button):** Each order in the list MUST have a distinct "Erneut Drucken" (Reprint) button next to it.
5.  **AC-5 (Functionality):** Clicking the "Erneut Drucken" button MUST trigger a reprint request for that specific order ID.
6.  **AC-6 (Backend Logic):** The reprint request MUST be handled by the main printer service, leveraging its existing queuing, error-handling, and retry logic.
7.  **AC-7 (User Feedback):** The web UI MUST provide immediate visual feedback to the user, indicating the status of the reprint request (e.g., "Drucke...", "Auftrag gesendet!", "Fehler").
8.  **AC-8 (Security):** The web page MUST only be accessible from within the local network and not be exposed to the public internet.
9.  **AC-9 (Responsiveness):** The user interface SHOULD be simple, clean, and usable on both desktop and mobile device browsers.
