"""Data-access repository layer for the ai domain."""

from sqlalchemy.orm import Session

from app.shared.repository import BaseRepository


class AIRepository(BaseRepository[object]):
    """Encapsulates SQLAlchemy 2.0 persistence operations for ai."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_module_health(self) -> dict[str, str]:
        """Return scaffold status without executing business logic."""
        return {
            "module": "ai",
            "status": "scaffolded",
            "message": "Isolated future AI capabilities (disabled by default).",
        }