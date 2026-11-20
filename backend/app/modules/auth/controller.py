"""HTTP controller layer for the auth domain."""

from app.modules.auth.schemas import AuthModuleStatus
from app.modules.auth.service import AuthService
from app.shared.schemas import APIResponse


class AuthController:
    """Coordinates HTTP request/response mapping for auth routes."""

    def __init__(self, service: AuthService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[AuthModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)