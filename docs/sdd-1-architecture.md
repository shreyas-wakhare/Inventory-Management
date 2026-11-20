# SDD-1: System Architecture & Domain Design

> **Status**: Draft Placeholder — To be populated during SDD-1 authoring.

## 1. System Context & Goals
- Real-time inventory tracking for SER Dewatering & Construction Equipment.
- Support for serialized equipment units (`equipment_units`) and bulk/consumable stock (`stock_balances`).

## 2. High-Level Architecture
- Modular Monolith (`backend/` FastAPI + `backend/database/` PostgreSQL) paired with Next.js App Router (`frontend/`).

## 3. Domain Boundaries
- `auth`, `users`, `projects`, `items`, `equipment_units`, `stock_balances`, `delivery_orders`, `collection_orders`, `stock_movements`, `reconciliation`, `ai`.

## 4. Security, RBAC & Auditability
- TBD.

## 5. Future AI Integration Boundaries
- Isolated `ai` module consuming read-only domain interfaces/views.

