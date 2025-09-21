# User Story: Proactive Order Polling

*   **Title:** Proactive Order Polling for Maximum Reliability
*   **ID:** `STORY-POLLING-01`
*   **As a:** System Operator
*   **I want:** The printer service to periodically and actively check the Wix API for new, paid orders
*   **So that:** No orders are missed if a webhook fails or is delayed, ensuring 100% of orders are printed.

---

### Acceptance Criteria (AC)

1.  **AC-1 (Polling Task):** A background task MUST run at a configurable interval (default: 30 seconds).
2.  **AC-2 (API Query):** The task MUST query the Wix API for orders created in the last 5 minutes with a `PAID` payment status.
3.  **AC-3 (Duplicate Prevention):** The service MUST check if an order's `wix_order_id` already exists in the local database before processing it.
4.  **AC-4 (New Order Processing):** Only orders that are NOT already in the database MUST be processed and have print jobs created for them.
5.  **AC-5 (Logging):** The polling activity, including the number of orders found and processed, MUST be clearly logged.
6.  **AC-6 (Resilience):** The polling mechanism MUST be resilient to temporary API or network errors and continue its cycle.
