"""Business logic and transaction service layer for the projects domain."""

from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import ProjectModuleStatus


class ProjectService:
    """Orchestrates business rules and atomic transactions for projects."""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def get_status(self) -> ProjectModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return ProjectModuleStatus(**payload)