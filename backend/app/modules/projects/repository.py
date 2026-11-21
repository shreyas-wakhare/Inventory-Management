"""Data-access repository for projects."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.delivery_orders.models import DeliveryOrder
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.projects.models import Project
from app.modules.reconciliation.models import ReconciliationRecord
from app.shared.enums import ProjectStatus
from app.shared.repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Encapsulates tenant-scoped queries and operational counts for projects."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_id(self, organization_id: UUID, project_id: UUID) -> Project | None:
        return self.get_by_id_for_org(Project, project_id, organization_id)

    def get_by_code(self, organization_id: UUID, project_code: str) -> Project | None:
        return self.db.scalar(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.project_code == project_code.strip().upper(),
            )
        )

    def list_projects_with_unit_counts(
        self,
        organization_id: UUID,
        *,
        status: ProjectStatus | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[tuple[Project, int]], int]:
        unit_counts = (
            select(
                EquipmentUnit.current_project_id.label("project_id"),
                func.count(EquipmentUnit.id).label("deployed_units_count"),
            )
            .where(
                EquipmentUnit.organization_id == organization_id,
                EquipmentUnit.current_project_id.is_not(None),
            )
            .group_by(EquipmentUnit.current_project_id)
            .subquery()
        )

        base_stmt = select(Project).where(Project.organization_id == organization_id)
        if status is not None:
            base_stmt = base_stmt.where(Project.status == status.value)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            base_stmt = base_stmt.where(
                or_(
                    Project.project_code.ilike(pattern),
                    Project.project_name.ilike(pattern),
                    Project.location.ilike(pattern),
                )
            )

        total = self.count_query(base_stmt)

        stmt = (
            select(
                Project,
                func.coalesce(unit_counts.c.deployed_units_count, 0).label("deployed_units_count"),
            )
            .outerjoin(unit_counts, unit_counts.c.project_id == Project.id)
            .where(Project.organization_id == organization_id)
        )
        if status is not None:
            stmt = stmt.where(Project.status == status.value)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Project.project_code.ilike(pattern),
                    Project.project_name.ilike(pattern),
                    Project.location.ilike(pattern),
                )
            )

        rows = [
            (row[0], int(row[1]))
            for row in self.db.execute(
                stmt.order_by(Project.created_at.desc(), Project.project_code.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        ]
        return rows, total

    def get_project_metrics(
        self,
        organization_id: UUID,
        project_id: UUID,
    ) -> tuple[int, int, int, Decimal]:
        deployed_units = int(
            self.db.scalar(
                select(func.count(EquipmentUnit.id)).where(
                    EquipmentUnit.organization_id == organization_id,
                    EquipmentUnit.current_project_id == project_id,
                )
            )
            or 0
        )
        active_dos = int(
            self.db.scalar(
                select(func.count(DeliveryOrder.id)).where(
                    DeliveryOrder.organization_id == organization_id,
                    DeliveryOrder.project_id == project_id,
                    DeliveryOrder.status.in_(["DISPATCHED", "PARTIALLY_RETURNED"]),
                )
            )
            or 0
        )
        open_recon_row = self.db.execute(
            select(
                func.count(ReconciliationRecord.id),
                func.coalesce(func.sum(ReconciliationRecord.variance_qty), 0),
            ).where(
                ReconciliationRecord.organization_id == organization_id,
                ReconciliationRecord.project_id == project_id,
                ReconciliationRecord.reconciliation_status.in_(["OPEN", "DISCREPANCY"]),
            )
        ).one()
        return (
            deployed_units,
            active_dos,
            int(open_recon_row[0] or 0),
            Decimal(str(open_recon_row[1] or 0)),
        )
