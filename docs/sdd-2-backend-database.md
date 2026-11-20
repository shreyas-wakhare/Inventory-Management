# SDD-2: Backend Services, API Contracts & PostgreSQL Database Design

> **Status**: Draft Placeholder — To be populated during SDD-2 authoring.

## 1. PostgreSQL Schema & Indexing Strategy
- Managed in `backend/database/`.
- Refer to `backend/database/schema/er_diagram.md`.

## 2. Layered Module Conventions
- `router.py` → `controller.py` → `service.py` → `repository.py` → `models.py` / `schemas.py`.

## 3. Core Transactional Workflows
- Delivery Order issuance & stock deduction / unit assignment.
- Collection Order return & inspection / stock replenishment.
- Immutable Stock Movement ledger (`stock_movements`).
- Periodic physical count & variance resolution (`reconciliation`).

## 4. REST API Contract (`/api/v1`)
- TBD.

