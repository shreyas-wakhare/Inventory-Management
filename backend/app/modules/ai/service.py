"""Business logic and transaction service layer for the ai domain."""

from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import AIModuleStatus


class AIService:
    """Orchestrates business rules and atomic transactions for ai."""

    def __init__(self, repository: AIRepository) -> None:
        self.repository = repository

    def get_status(self) -> AIModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return AIModuleStatus(**payload)