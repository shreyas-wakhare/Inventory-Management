"""HTTP controller layer for the users domain."""

from app.modules.users.schemas import UserModuleStatus
from app.modules.users.service import UserService
from app.shared.schemas import APIResponse


class UserController:
    """Coordinates HTTP request/response mapping for users routes."""

    def __init__(self, service: UserService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[UserModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)