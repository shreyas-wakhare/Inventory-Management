"""Shared domain enumerations (placeholder for SDD-2)."""

from enum import StrEnum


class UserRole(StrEnum):
    """Baseline SER RBAC roles (to be finalized in SDD-1/SDD-2)."""

    ADMIN = "admin"
    STOREKEEPER = "storekeeper"
    SITE_ENGINEER = "site_engineer"
    AUDITOR = "auditor"

