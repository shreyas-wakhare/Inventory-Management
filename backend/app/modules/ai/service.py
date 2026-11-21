"""Business service for the isolated future AI boundary (feature-flagged via AI_ENABLED)."""

from app.core.config import settings
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import AIModuleStatus


class AIService:
    """Exposes read-only AI availability without coupling to transactional inventory writes."""

    def __init__(self, repository: AIRepository) -> None:
        self.repository = repository

    def get_status(self) -> AIModuleStatus:
        enabled = settings.AI_ENABLED
        return AIModuleStatus(
            module="ai",
            status="enabled" if enabled else "disabled",
            message=(
                f"AI provider '{settings.AI_PROVIDER}' active (read-only boundary)."
                if enabled
                else "Isolated future AI module is disabled by default (AI_ENABLED=false)."
            ),
        )
