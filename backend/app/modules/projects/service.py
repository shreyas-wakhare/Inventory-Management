"""Business logic service for projects including active-equipment closure guard."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.core.exceptions import (
    DuplicateBusinessKeyError,
    NotFoundError,
    ProjectHasActiveEquipmentError,
    ValidationDomainError,
)
from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
)
from app.shared.enums import ProjectStatus
from app.shared.schemas import PaginatedResponse, build_pagination_meta


class ProjectService:
    """Manages construction & dewatering project lifecycles."""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def list_projects(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        status: ProjectStatus | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[ProjectSummaryResponse]:
        rows, total = self.repository.list_projects_with_unit_counts(
            ctx.organization_id,
            status=status,
            search=search,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        items = [
            ProjectSummaryResponse(
                **ProjectResponse.model_validate(proj).model_dump(),
                deployed_units_count=count,
            )
            for proj, count in rows
        ]
        return PaginatedResponse(
            items=items,
            meta=build_pagination_meta(
                page=pagination.page,
                page_size=pagination.page_size,
                total=total,
            ),
        )

    def create_project(
        self,
        ctx: CurrentUserContext,
        payload: ProjectCreate,
    ) -> ProjectResponse:
        code = payload.project_code.strip().upper()
        if self.repository.get_by_code(ctx.organization_id, code) is not None:
            raise DuplicateBusinessKeyError(
                f"Project code '{code}' already exists in this organization.",
                details={"project_code": code},
            )
        project = Project(
            organization_id=ctx.organization_id,
            project_code=code,
            project_name=payload.project_name.strip(),
            location=payload.location.strip() if payload.location else None,
            status=ProjectStatus.ACTIVE.value,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        self.repository.db.add(project)
        self.repository.db.commit()
        self.repository.db.refresh(project)
        return ProjectResponse.model_validate(project)

    def get_project_detail(
        self,
        ctx: CurrentUserContext,
        project_id: UUID,
    ) -> ProjectDetailResponse:
        project = self.repository.get_by_id(ctx.organization_id, project_id)
        if project is None:
            raise NotFoundError("Project not found.", details={"project_id": str(project_id)})

        deployed_units, active_dos, open_recons, variance_qty = self.repository.get_project_metrics(
            ctx.organization_id,
            project_id,
        )
        return ProjectDetailResponse(
            **ProjectResponse.model_validate(project).model_dump(),
            deployed_units_count=deployed_units,
            active_delivery_orders_count=active_dos,
            open_reconciliations_count=open_recons,
            outstanding_variance_qty=variance_qty,
        )

    def update_project(
        self,
        ctx: CurrentUserContext,
        project_id: UUID,
        payload: ProjectUpdate,
    ) -> ProjectResponse:
        project = self.repository.get_by_id(ctx.organization_id, project_id)
        if project is None:
            raise NotFoundError("Project not found.", details={"project_id": str(project_id)})

        next_start = payload.start_date if payload.start_date is not None else project.start_date
        next_end = payload.end_date if payload.end_date is not None else project.end_date
        if next_start and next_end and next_end < next_start:
            raise ValidationDomainError("end_date cannot be earlier than start_date.")

        if payload.status == ProjectStatus.CLOSED:
            deployed_units, _, open_recons, _ = self.repository.get_project_metrics(
                ctx.organization_id,
                project_id,
            )
            if deployed_units > 0 or open_recons > 0:
                raise ProjectHasActiveEquipmentError(
                    "Project cannot be CLOSED while equipment units are still deployed or reconciliations remain open.",
                    details={
                        "deployed_units_count": deployed_units,
                        "open_reconciliations_count": open_recons,
                    },
                )

        if payload.project_name is not None:
            project.project_name = payload.project_name.strip()
        if payload.location is not None:
            project.location = payload.location.strip() or None
        if payload.status is not None:
            project.status = payload.status.value
        if payload.start_date is not None:
            project.start_date = payload.start_date
        if payload.end_date is not None:
            project.end_date = payload.end_date

        self.repository.db.commit()
        self.repository.db.refresh(project)
        return ProjectResponse.model_validate(project)
