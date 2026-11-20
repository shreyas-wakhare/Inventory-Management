# Database Layer (`backend/database/`)

Owns all PostgreSQL configuration, SQLAlchemy base/session plumbing, Alembic migrations, bootstrap SQL, seed scripts, and schema documentation for the SER Inventory Management System.

## Contents
- `base.py`: `DeclarativeBase`, naming conventions, and `UUIDPrimaryKeyMixin` / `TimestampMixin`.
- `session.py`: SQLAlchemy 2.0 engine, `SessionLocal`, and FastAPI `get_db` dependency.
- `alembic.ini` & `migrations/`: Versioned schema migrations.
- `init/01_init.sql`: PostgreSQL extensions (`uuid-ossp`, `pgcrypto`).
- `seeds/seed_dev.py`: Idempotent local/staging seed entrypoint.
- `schema/er_diagram.md`: Schema & ER notes.
- `docker-compose.postgres.yml`: Local PostgreSQL 16 service definition.

