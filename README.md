# SER Inventory Management System

Real-time **Dewatering & Construction Equipment Inventory Management System** for the SER department, engineered with a modular monolith architecture, strict layered service boundaries, and future AI integration readiness.

## Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS |
| **Backend** | FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy 2.0, Alembic |
| **Database** | PostgreSQL (managed inside [`backend/database/`](backend/database/)) |
| **Future AI** | Isolated `ai` domain module (disabled by default, zero coupling to core transactions) |

## Repository Structure

```text
.
├── backend/                  # FastAPI modular monolith + PostgreSQL database management
│   ├── app/
│   │   ├── api/v1/           # Versioned API router aggregation
│   │   ├── core/             # Config, security, exceptions, shared dependencies, logging
│   │   ├── shared/           # Cross-domain schemas, base repository, shared enums
│   │   └── modules/          # Layered domain services (router → controller → service → repository)
│   │       ├── auth/
│   │       ├── users/
│   │       ├── projects/
│   │       ├── items/
│   │       ├── equipment_units/
│   │       ├── stock_balances/
│   │       ├── delivery_orders/
│   │       ├── collection_orders/
│   │       ├── stock_movements/
│   │       ├── reconciliation/
│   │       └── ai/           # Isolated AI boundary (placeholder)
│   ├── database/             # PostgreSQL engine/session, Alembic migrations, seeds, init SQL, ER docs
│   └── tests/                # Unit and integration tests
├── frontend/                 # Next.js App Router + TypeScript + Tailwind CSS
│   └── src/
│       ├── app/              # App Router pages & route groups ((auth), (dashboard))
│       ├── features/         # Domain-modular features (services, types, hooks, components)
│       ├── components/       # Shared UI primitives, layout shell, feedback states
│       ├── lib/              # Typed API client, env config, utilities
│       ├── config/           # Navigation & app constants
│       └── types/            # Shared API response/pagination contracts
├── docs/                     # System Design Documents (SDD-1, SDD-2, SDD-3)
├── .env.example              # Shared environment template
└── .gitignore
```

## Architectural Principles

1. **Strict Layered Separation (Backend)**:
   - `router.py`: FastAPI HTTP route registration and dependency injection.
   - `controller.py`: Request/response orchestration, HTTP status handling, and DTO mapping.
   - `service.py`: Domain business rules, validations, and atomic database transaction boundaries.
   - `repository.py`: Encapsulated SQLAlchemy 2.0 data-access queries.
   - `schemas.py` & `models.py`: Pydantic v2 contracts and SQLAlchemy 2.0 ORM definitions.
2. **Database Ownership Inside `backend/database/`**:
   - All PostgreSQL configuration, SQLAlchemy session lifecycle, Alembic migrations, seed scripts, initialization SQL, and ER schema docs reside under `backend/database/`.
3. **Domain-Modular Frontend (`frontend/src/features/`)**:
   - Mirrors backend business domains with isolated API service modules, TypeScript contracts, hooks, and UI components.
4. **Future AI Readiness Without Over-Engineering**:
   - `backend/app/modules/ai/` and `frontend/src/features/ai/` expose explicit boundaries for future forecasting, anomaly detection, or natural-language inventory queries without coupling to core stock transactions.

## Documentation

- [`docs/sdd-1-architecture.md`](docs/sdd-1-architecture.md) — System Architecture & Domain Overview
- [`docs/sdd-2-backend-database.md`](docs/sdd-2-backend-database.md) — Backend Services, API Contracts & PostgreSQL Schema
- [`docs/sdd-3-frontend-ui.md`](docs/sdd-3-frontend-ui.md) — Frontend Architecture, UX Flows & Component System

## Quick Start (Local Development)

### 1. Environment Setup
```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

### 2. PostgreSQL (via `backend/database/`)
```bash
docker compose -f backend/database/docker-compose.postgres.yml up -d
```

### 3. Backend (FastAPI)
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic -c database/alembic.ini upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```

