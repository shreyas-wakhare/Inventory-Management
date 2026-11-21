"""Isolated PostgreSQL savepoint test harness for SER Inventory Management System.

Uses SQLAlchemy 2.0 `join_transaction_mode="create_savepoint"` over an outer
transaction rolled back at test teardown so all real PostgreSQL constraints,
generated columns (`variance_qty`), and triggers (`trg_stock_movements_immutable`,
`set_updated_at`) execute authentically while leaving the seeded `SER` org data
completely untouched.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import database.models  # noqa: F401
from app.main import app
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.stock_balances.models import StockBalance
from app.modules.stock_movements.models import StockMovement
from app.modules.users.models import Organization, User
from database.session import engine, get_db


@dataclass
class SeededTestTenant:
    """Isolated SER-E2E-TEST organization fixture with all 4 RBAC roles and sample catalog."""

    org_id: UUID
    org_code: str
    users: dict[str, User]
    asset_item: Item
    unit_a: EquipmentUnit
    unit_b: EquipmentUnit
    accessory_item: Item


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Yield a PostgreSQL session wrapped in an outer transaction rolled back on teardown."""
    connection = engine.connect()
    outer_tx = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        outer_tx.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient bound to the isolated savepoint PostgreSQL session."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def tenant(db_session: Session) -> SeededTestTenant:
    """Provision isolated SER-E2E-TEST organization, 4 RBAC users, 1 ASSET (2 units), and 1 ACCESSORY."""
    org = Organization(code="SER-E2E-TEST", name="SER E2E Test Org", is_active=True)
    db_session.add(org)
    db_session.flush()

    role_specs = [
        ("ADMIN", "Admin User", "admin@e2e.ser.local"),
        ("SER_OPERATOR", "SER Operator", "operator@e2e.ser.local"),
        ("WORKSHOP_LEAD", "Workshop Lead", "workshop@e2e.ser.local"),
        ("PROJECT_VIEWER", "Project Viewer", "viewer@e2e.ser.local"),
    ]
    users: dict[str, User] = {}
    for role, full_name, email in role_specs:
        u = User(
            organization_id=org.id,
            full_name=full_name,
            email=email,
            role=role,
            is_active=True,
        )
        db_session.add(u)
        users[role] = u
    db_session.flush()

    admin_user = users["ADMIN"]

    # Serialized ASSET item with 2 AVAILABLE physical units
    asset_item = Item(
        organization_id=org.id,
        item_code="E2E-PUMP-6IN",
        description='6" Wellpoint Dewatering Pump (Test)',
        uom="UNIT",
        product_type="ASSET",
        category="Pumps",
        sub_category="Wellpoint",
        unit_price_aed=Decimal("15000.00"),
        is_serialized=True,
        is_active=True,
    )
    db_session.add(asset_item)

    # Bulk ACCESSORY item (starting at 0; Scenario 4 loads opening stock via API)
    accessory_item = Item(
        organization_id=org.id,
        item_code="E2E-HDPE-160",
        description="160mm HDPE Discharge Pipe (Test)",
        uom="MTR",
        product_type="ACCESSORY",
        category="Piping",
        sub_category="HDPE Pipe",
        unit_price_aed=Decimal("120.00"),
        is_serialized=False,
        is_active=True,
    )
    db_session.add(accessory_item)
    db_session.flush()

    unit_a = EquipmentUnit(
        organization_id=org.id,
        item_id=asset_item.id,
        serial_number="E2E-PMP-001",
        status="AVAILABLE",
        condition_status="GOOD",
        current_project_id=None,
    )
    unit_b = EquipmentUnit(
        organization_id=org.id,
        item_id=asset_item.id,
        serial_number="E2E-PMP-002",
        status="AVAILABLE",
        condition_status="GOOD",
        current_project_id=None,
    )
    db_session.add_all([unit_a, unit_b])
    db_session.flush()

    db_session.add_all(
        [
            StockBalance(
                organization_id=org.id,
                item_id=asset_item.id,
                ownership_source="SER",
                available_qty=Decimal("2.000"),
                in_use_qty=Decimal("0.000"),
                replenishment_qty=Decimal("0.000"),
                damaged_qty=Decimal("0.000"),
            ),
            StockBalance(
                organization_id=org.id,
                item_id=accessory_item.id,
                ownership_source="SER",
                available_qty=Decimal("0.000"),
                in_use_qty=Decimal("0.000"),
                replenishment_qty=Decimal("0.000"),
                damaged_qty=Decimal("0.000"),
            ),
            StockMovement(
                organization_id=org.id,
                item_id=asset_item.id,
                equipment_unit_id=unit_a.id,
                project_id=None,
                ownership_source="SER",
                movement_type="OPENING_STOCK",
                from_bucket="EXTERNAL",
                to_bucket="AVAILABLE",
                quantity=Decimal("1.000"),
                reference_type="OPENING_BALANCE",
                reference_number="E2E-SEED",
                notes="Seeded E2E unit A",
                created_by=admin_user.id,
            ),
            StockMovement(
                organization_id=org.id,
                item_id=asset_item.id,
                equipment_unit_id=unit_b.id,
                project_id=None,
                ownership_source="SER",
                movement_type="OPENING_STOCK",
                from_bucket="EXTERNAL",
                to_bucket="AVAILABLE",
                quantity=Decimal("1.000"),
                reference_type="OPENING_BALANCE",
                reference_number="E2E-SEED",
                notes="Seeded E2E unit B",
                created_by=admin_user.id,
            ),
        ]
    )
    db_session.commit()

    return SeededTestTenant(
        org_id=org.id,
        org_code=org.code,
        users=users,
        asset_item=asset_item,
        unit_a=unit_a,
        unit_b=unit_b,
        accessory_item=accessory_item,
    )


@pytest.fixture()
def as_role(tenant: SeededTestTenant):
    """Helper returning X-Dev-User-Email headers for any RBAC role in SER-E2E-TEST."""

    def _headers(role: str) -> dict[str, str]:
        return {"X-Dev-User-Email": tenant.users[role].email}

    return _headers


def assert_error(
    response: Any,
    *,
    status_code: int,
    error_code: str,
) -> dict[str, Any]:
    """Assert SDD-2 error envelope structure, HTTP status code, and error_code."""
    assert response.status_code == status_code, (
        f"Expected HTTP {status_code}, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "error" in body, f"Missing 'error' envelope in {body}"
    err = body["error"]
    assert err["error_code"] == error_code, (
        f"Expected error_code='{error_code}', got '{err.get('error_code')}': {err}"
    )
    assert err.get("trace_id"), "Missing trace_id in error envelope"
    assert "x-trace-id" in response.headers
    return err
