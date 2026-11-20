# Isolated AI Module (`backend/app/modules/ai/`)

This module defines the clean boundary for future AI capabilities in the SER Inventory Management System (for example: equipment demand forecasting, stock variance anomaly detection, or natural-language inventory queries).

## Isolation Rules
1. **Disabled by default**: Controlled via `AI_ENABLED=false` in `app.core.config.settings`.
2. **No direct write coupling**: Core transactional modules (`delivery_orders`, `collection_orders`, `stock_movements`, `stock_balances`, `reconciliation`) must never depend on `ai/`.
3. **Interface-first**: Future LLM/ML providers implement contracts in `interfaces.py` without leaking provider SDKs into core business services.

