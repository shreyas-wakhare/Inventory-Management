"""HTTP controller layer for the ai domain."""

from app.modules.ai.schemas import AIModuleStatus
from app.modules.ai.service import AIService
from app.shared.schemas import APIResponse


class AIController:
    """Coordinates HTTP request/response mapping for ai routes."""

    def __init__(self, service: AIService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[AIModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)