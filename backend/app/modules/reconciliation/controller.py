"""HTTP controller layer for the reconciliation domain."""

from app.modules.reconciliation.schemas import ReconciliationModuleStatus
from app.modules.reconciliation.service import ReconciliationService
from app.shared.schemas import APIResponse


class ReconciliationController:
    """Coordinates HTTP request/response mapping for reconciliation routes."""

    def __init__(self, service: ReconciliationService) -> None:
        self.service = service

    def get_status(self) -> APIResponse[ReconciliationModuleStatus]:
        """Handle module status check request."""
        result = self.service.get_status()
        return APIResponse(data=result)