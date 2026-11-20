# PostgreSQL Schema & ER Documentation

> **Status**: Placeholder — Full Entity-Relationship diagram, constraints, indexes, and ledger invariants will be finalized in `docs/sdd-2-backend-database.md`.

## Planned Core Tables
- `users`, `roles` (Identity & RBAC)
- `projects` (Active construction & dewatering sites)
- `items` (Equipment & consumable catalog master)
- `equipment_units` (Serialized assets: pumps, generators, control panels, etc.)
- `stock_balances` (Real-time bulk/consumable quantities by location/warehouse)
- `delivery_orders` & `delivery_order_lines` (Outbound dispatch to projects)
- `collection_orders` & `collection_order_lines` (Inbound return from projects)
- `stock_movements` (Immutable append-only audit ledger)
- `reconciliation_sessions` & `reconciliation_lines` (Physical count & variance resolution)

