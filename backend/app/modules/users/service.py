"""Business logic and transaction service layer for the users domain."""

from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserModuleStatus


class UserService:
    """Orchestrates business rules and atomic transactions for users."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def get_status(self) -> UserModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return UserModuleStatus(**payload)