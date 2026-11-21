"""HTTP controller layer for projects endpoints."""

from __future__ import annotations

from uuid import UUID

from app.core.dependencies import CurrentUserContext, PaginationParams
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
)
from app.modules.projects.service import ProjectService
from app.shared.enums import ProjectStatus
from app.shared.schemas import APIResponse, PaginatedResponse


class ProjectController:
    """Coordinates HTTP responses for projects."""

    def __init__(self, service: ProjectService) -> None:
        self.service = service

    def list_projects(
        self,
        ctx: CurrentUserContext,
        pagination: PaginationParams,
        *,
        status: ProjectStatus | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[ProjectSummaryResponse]:
        return self.service.list_projects(ctx, pagination, status=status, search=search)

    def create_project(
        self,
        ctx: CurrentUserContext,
        payload: ProjectCreate,
    ) -> APIResponse[ProjectResponse]:
        return APIResponse(data=self.service.create_project(ctx, payload), message="created")

    def get_project_detail(
        self,
        ctx: CurrentUserContext,
        project_id: UUID,
    ) -> APIResponse[ProjectDetailResponse]:
        return APIResponse(data=self.service.get_project_detail(ctx, project_id))

    def update_project(
        self,
        ctx: CurrentUserContext,
        project_id: UUID,
        payload: ProjectUpdate,
    ) -> APIResponse[ProjectResponse]:
        return APIResponse(data=self.service.update_project(ctx, project_id, payload))
