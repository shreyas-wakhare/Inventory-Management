"""FastAPI router definitions for /projects endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    CurrentUserContext,
    CurrentUserDep,
    DbSession,
    PaginationDep,
    require_roles,
)
from app.modules.projects.controller import ProjectController
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
)
from app.modules.projects.service import ProjectService
from app.shared.enums import ProjectStatus, UserRole
from app.shared.schemas import APIResponse, PaginatedResponse

router = APIRouter(prefix="/projects", tags=["projects"])


def get_controller(db: DbSession) -> ProjectController:
    return ProjectController(ProjectService(ProjectRepository(db)))


@router.get("", response_model=PaginatedResponse[ProjectSummaryResponse])
def list_projects(
    pagination: PaginationDep,
    current_user: CurrentUserDep,
    project_status: ProjectStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    controller: ProjectController = Depends(get_controller),
) -> PaginatedResponse[ProjectSummaryResponse]:
    return controller.list_projects(current_user, pagination, status=project_status, search=search)


@router.post("", response_model=APIResponse[ProjectResponse], status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: ProjectController = Depends(get_controller),
) -> APIResponse[ProjectResponse]:
    return controller.create_project(current_user, payload)


@router.get("/{project_id}", response_model=APIResponse[ProjectDetailResponse])
def get_project(
    project_id: UUID,
    current_user: CurrentUserDep,
    controller: ProjectController = Depends(get_controller),
) -> APIResponse[ProjectDetailResponse]:
    return controller.get_project_detail(current_user, project_id)


@router.patch("/{project_id}", response_model=APIResponse[ProjectResponse])
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: CurrentUserContext = Depends(
        require_roles(UserRole.ADMIN, UserRole.SER_OPERATOR)
    ),
    controller: ProjectController = Depends(get_controller),
) -> APIResponse[ProjectResponse]:
    return controller.update_project(current_user, project_id, payload)
