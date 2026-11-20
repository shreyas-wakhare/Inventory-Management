# Backend — SER Inventory Management System

FastAPI (Python 3.11+) + Pydantic v2 + SQLAlchemy 2.0 + Alembic + PostgreSQL.

## Layered Architecture

Every domain under `app/modules/<domain>/` follows a strict top-down dependency flow:

```text
router.py (FastAPI routes & DI)
   └── controller.py (HTTP request/response orchestration)
          └── service.py (Business logic & transaction boundaries)
                 └── repository.py (SQLAlchemy 2.0 data access)
                        └── models.py (ORM tables) & schemas.py (Pydantic v2 DTOs)
```

## Database Management (`backend/database/`)

All PostgreSQL infrastructure lives inside `backend/database/`:
- `base.py` — SQLAlchemy 2.0 `Base` declarative class and shared model mixins.
- `session.py` — Engine creation, `SessionLocal`, and FastAPI `get_db` dependency.
- `alembic.ini` & `migrations/` — Alembic schema migrations.
- `init/` — Initial PostgreSQL bootstrap SQL scripts.
- `seeds/` — Local/staging seed scripts.
- `schema/` — ER diagrams and database design notes.
- `docker-compose.postgres.yml` — Local PostgreSQL service for development.

## Common Commands (run from `backend/`)

```bash
# Start local PostgreSQL
docker compose -f database/docker-compose.postgres.yml up -d

# Run Alembic migrations
alembic -c database/alembic.ini upgrade head

# Create a new migration
alembic -c database/alembic.ini revision --autogenerate -m "describe_change"

# Start API server
uvicorn app.main:app --reload --port 8000
```

