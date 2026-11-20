"""Business logic and transaction service layer for the reconciliation domain."""

from app.modules.reconciliation.repository import ReconciliationRepository
from app.modules.reconciliation.schemas import ReconciliationModuleStatus


class ReconciliationService:
    """Orchestrates business rules and atomic transactions for reconciliation."""

    def __init__(self, repository: ReconciliationRepository) -> None:
        self.repository = repository

    def get_status(self) -> ReconciliationModuleStatus:
        """Return placeholder module readiness status."""
        payload = self.repository.get_module_health()
        return ReconciliationModuleStatus(**payload)