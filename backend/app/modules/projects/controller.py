"""HTTP controller layer for the projects domain."""

from app.modules.projects.schemas import ProjectModuleStatus
from app.modules.projects.service import ProjectService
from app.shared.schemas import APIResponse


class ProjectController:
    """Coordinates HTTP request/response mapping for projects routes."""

    def __init__(self, service: ProjectService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[ProjectModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)