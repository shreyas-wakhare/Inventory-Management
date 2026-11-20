# Frontend — SER Inventory Management System

Next.js (App Router) + TypeScript + Tailwind CSS.

## Modular Feature Architecture (`src/`)

- `src/app/`: Next.js App Router routes and layouts (`(auth)` and `(dashboard)` route groups).
- `src/features/<domain>/`: Domain-isolated modules mirroring backend services:
  - `services/`: Typed API client calls to FastAPI `/api/v1/...`.
  - `types/`: Domain TypeScript interfaces and DTOs.
  - `hooks/`: Stateful React hooks & data-fetching orchestrators.
  - `components/`: Domain-specific UI components.
- `src/components/`: Reusable cross-domain UI primitives (`ui/`), layout (`layout/`), and feedback (`feedback/`).
- `src/lib/`: Core HTTP `apiClient`, env validation, and shared utilities.
- `src/types/`: Shared API response and pagination contracts.
- `src/config/`: Navigation registry and app constants.

## Development Commands (run from `frontend/`)

```bash
npm install
npm run dev
npm run typecheck
npm run lint
```

