# Isolated Frontend AI Feature (`frontend/src/features/ai/`)

Reserved frontend feature boundary for future AI assistants, anomaly insights, or forecasting panels.

- Communicates strictly through `/api/v1/ai/*` via `services/ai.service.ts`.
- Remains decoupled from core operational workflows (`delivery-orders`, `collection-orders`, `stock-balances`, `reconciliation`).

