"""Business logic and transaction service layer for the auth domain."""

from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AuthModuleStatus


class AuthService:
    """Orchestrates business rules and atomic transactions for auth."""

    def __init__(self, repository: AuthRepository) -> None:
        self.repository = repository

    def get_status(self) -> AuthModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return AuthModuleStatus(**payload)