"""End-to-end & edge-case integration test suite validating SDD-1 & SDD-2 invariants."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.conftest import SeededTestTenant, assert_error


def _create_project(
    client: TestClient,
    headers: dict[str, str],
    code: str,
    name: str,
) -> dict:
    resp = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"project_code": code, "project_name": name, "location": "Dubai"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _get_balance(
    client: TestClient,
    headers: dict[str, str],
    item_id: str,
    ownership_source: str = "SER",
) -> dict:
    resp = client.get(
        f"/api/v1/stock-balances?item_id={item_id}&ownership_source={ownership_source}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1, items
    return items[0]


# =============================================================================
# Auth, JWT Bearer & Multi-Tenant Isolation
# =============================================================================
def test_auth_jwt_login_refresh_and_tenant_isolation(
    client: TestClient,
    tenant: SeededTestTenant,
    as_role,
) -> None:
    # Real JWT login & refresh for SER-E2E-TEST ADMIN
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": tenant.users["ADMIN"].email,
            "password": "dev-password",
            "organization_code": tenant.org_code,
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    tokens = login_resp.json()["data"]
    assert tokens["token_type"] == "bearer"
    assert tokens["user"]["organization_code"] == "SER-E2E-TEST"

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    bearer_headers = {"Authorization": f"Bearer {refresh_resp.json()['data']['access_token']}"}

    me = client.get("/api/v1/auth/me", headers=bearer_headers)
    assert me.status_code == 200
    assert me.json()["data"]["organization_code"] == "SER-E2E-TEST"

    # Tenant isolation: SER-E2E-TEST only sees its own 2 items (never SER's 148 items)
    items_resp = client.get("/api/v1/items", headers=bearer_headers)
    assert items_resp.status_code == 200
    assert items_resp.json()["meta"]["total"] == 2

    units_resp = client.get("/api/v1/equipment-units", headers=as_role("PROJECT_VIEWER"))
    assert units_resp.status_code == 200
    assert units_resp.json()["meta"]["total"] == 2


# =============================================================================
# Scenario 1 — Happy Path Serialized Lifecycle
# AVAILABLE -> IN_USE -> REPLENISHMENT -> AVAILABLE
# =============================================================================
def test_scenario_1_serialized_happy_path_lifecycle(
    client: TestClient,
    tenant: SeededTestTenant,
    as_role,
) -> None:
    op = as_role("SER_OPERATOR")
    ws = as_role("WORKSHOP_LEAD")

    project = _create_project(client, op, "PRJ-E2E-001", "Marina Dewatering")
    unit_id = str(tenant.unit_a.id)
    item_id = str(tenant.asset_item.id)

    # 1. Create DRAFT DO (must NOT deduct stock yet)
    do_create = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-E2E-001",
            "project_id": project["id"],
            "lines": [
                {
                    "item_id": item_id,
                    "equipment_unit_id": unit_id,
                    "ownership_source": "SER",
                    "dispatched_qty": "1",
                }
            ],
        },
    )
    assert do_create.status_code == 201, do_create.text
    do_data = do_create.json()["data"]
    assert do_data["status"] == "DRAFT"
    do_line_id = do_data["lines"][0]["id"]

    bal_before = _get_balance(client, op, item_id)
    assert Decimal(bal_before["available_qty"]) == Decimal("2.000")
    assert Decimal(bal_before["in_use_qty"]) == Decimal("0.000")

    # 2. Dispatch DO (AVAILABLE -> IN_USE)
    do_dispatch = client.post(
        f"/api/v1/delivery-orders/{do_data['id']}/dispatch",
        headers=op,
        json={"remarks": "Dispatched to Marina Site"},
    )
    assert do_dispatch.status_code == 200, do_dispatch.text
    assert do_dispatch.json()["data"]["status"] == "DISPATCHED"

    unit_after_do = client.get(f"/api/v1/equipment-units/{unit_id}", headers=op).json()["data"]
    assert unit_after_do["status"] == "IN_USE"
    assert unit_after_do["current_project_id"] == project["id"]

    bal_after_do = _get_balance(client, op, item_id)
    assert Decimal(bal_after_do["available_qty"]) == Decimal("1.000")
    assert Decimal(bal_after_do["in_use_qty"]) == Decimal("1.000")

    recon_after_do = client.get(
        f"/api/v1/reconciliation?delivery_order_id={do_data['id']}", headers=op
    ).json()["items"]
    assert len(recon_after_do) == 1
    assert Decimal(recon_after_do[0]["outgoing_qty"]) == Decimal("1.000")
    assert Decimal(recon_after_do[0]["incoming_qty"]) == Decimal("0.000")
    assert Decimal(recon_after_do[0]["variance_qty"]) == Decimal("1.000")
    assert recon_after_do[0]["reconciliation_status"] == "OPEN"

    # 3. Create DRAFT CO routing to REPLENISHMENT & receive it
    co_create = client.post(
        "/api/v1/collection-orders",
        headers=op,
        json={
            "co_number": "CO-E2E-001",
            "project_id": project["id"],
            "delivery_order_id": do_data["id"],
            "lines": [
                {
                    "delivery_order_line_id": do_line_id,
                    "item_id": item_id,
                    "equipment_unit_id": unit_id,
                    "ownership_source": "SER",
                    "returned_qty": "1",
                    "post_return_bucket": "REPLENISHMENT",
                    "condition_notes": "Requires impeller seal service",
                }
            ],
        },
    )
    assert co_create.status_code == 201, co_create.text
    co_id = co_create.json()["data"]["id"]

    co_receive = client.post(f"/api/v1/collection-orders/{co_id}/receive", headers=op, json={})
    assert co_receive.status_code == 200, co_receive.text
    assert co_receive.json()["data"]["status"] == "RECEIVED"

    unit_after_co = client.get(f"/api/v1/equipment-units/{unit_id}", headers=op).json()["data"]
    assert unit_after_co["status"] == "REPLENISHMENT"
    assert unit_after_co["condition_status"] == "NEEDS_SERVICE"
    assert unit_after_co["current_project_id"] is None

    bal_after_co = _get_balance(client, op, item_id)
    assert Decimal(bal_after_co["available_qty"]) == Decimal("1.000")
    assert Decimal(bal_after_co["in_use_qty"]) == Decimal("0.000")
    assert Decimal(bal_after_co["replenishment_qty"]) == Decimal("1.000")

    recon_after_co = client.get(
        f"/api/v1/reconciliation?delivery_order_id={do_data['id']}", headers=op
    ).json()["items"][0]
    assert Decimal(recon_after_co["incoming_qty"]) == Decimal("1.000")
    assert Decimal(recon_after_co["variance_qty"]) == Decimal("0.000")
    assert recon_after_co["reconciliation_status"] == "EQUALIZED"

    do_after_co = client.get(f"/api/v1/delivery-orders/{do_data['id']}", headers=op).json()["data"]
    assert do_after_co["status"] == "CLOSED"

    # 4. Verify unit appears in Workshop Replenishment queue
    ws_units = client.get("/api/v1/workshop/replenishment/units", headers=ws).json()["items"]
    assert any(u["id"] == unit_id for u in ws_units)
    ws_bals = client.get("/api/v1/workshop/replenishment/balances", headers=ws).json()["items"]
    assert any(b["item_id"] == item_id and Decimal(b["replenishment_qty"]) == Decimal("1.000") for b in ws_bals)

    # 5. Complete replenishment as WORKSHOP_LEAD (REPLENISHMENT -> AVAILABLE)
    ws_complete = client.post(
        "/api/v1/workshop/replenishment/complete",
        headers=ws,
        json={
            "item_id": item_id,
            "equipment_unit_id": unit_id,
            "ownership_source": "SER",
            "quantity": "1",
            "workshop_ticket_ref": "WS-2026-009",
            "notes": "Impeller replaced and pressure tested",
        },
    )
    assert ws_complete.status_code == 200, ws_complete.text
    assert Decimal(ws_complete.json()["data"]["remaining_replenishment_qty"]) == Decimal("0.000")
    assert Decimal(ws_complete.json()["data"]["new_available_qty"]) == Decimal("2.000")

    unit_final = client.get(f"/api/v1/equipment-units/{unit_id}", headers=op).json()["data"]
    assert unit_final["status"] == "AVAILABLE"
    assert unit_final["condition_status"] == "GOOD"

    # 6. Verify chronological movement timeline
    mvs = client.get(f"/api/v1/equipment-units/{unit_id}/movements", headers=op).json()["items"]
    # Endpoint returns newest first; reverse to assert chronological order
    mv_types_chronological = [m["movement_type"] for m in reversed(mvs)]
    assert mv_types_chronological == [
        "OPENING_STOCK",
        "DO_DISPATCH",
        "CO_RETURN_REPLENISHMENT",
        "REPLENISHMENT_COMPLETE",
    ]


# =============================================================================
# Scenario 2 — Pre-Dispatch Replenishment Lock & Availability Hard Gates (409)
# =============================================================================
def test_scenario_2_pre_dispatch_replenishment_lock_and_availability_gates(
    client: TestClient,
    tenant: SeededTestTenant,
    as_role,
) -> None:
    admin = as_role("ADMIN")
    op = as_role("SER_OPERATOR")

    project = _create_project(client, op, "PRJ-E2E-002", "Lock Gate Site")
    unit_a_id = str(tenant.unit_a.id)
    unit_b_id = str(tenant.unit_b.id)
    asset_id = str(tenant.asset_item.id)
    acc_id = str(tenant.accessory_item.id)

    # Put unit_a into REPLENISHMENT (via DO -> CO to REPLENISHMENT)
    do1 = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-LOCK-001",
            "project_id": project["id"],
            "lines": [{"item_id": asset_id, "equipment_unit_id": unit_a_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/delivery-orders/{do1['id']}/dispatch", headers=op, json={}).status_code == 200

    # 2a. Attempt to dispatch unit_a while IN_USE -> 409 UNIT_NOT_AVAILABLE
    do_in_use = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-LOCK-INUSE",
            "project_id": project["id"],
            "lines": [{"item_id": asset_id, "equipment_unit_id": unit_a_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do_in_use['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="UNIT_NOT_AVAILABLE",
    )

    # Return unit_a to REPLENISHMENT
    co1 = client.post(
        "/api/v1/collection-orders",
        headers=op,
        json={
            "co_number": "CO-LOCK-001",
            "project_id": project["id"],
            "delivery_order_id": do1["id"],
            "lines": [
                {
                    "delivery_order_line_id": do1["lines"][0]["id"],
                    "item_id": asset_id,
                    "equipment_unit_id": unit_a_id,
                    "returned_qty": "1",
                    "post_return_bucket": "REPLENISHMENT",
                }
            ],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/collection-orders/{co1['id']}/receive", headers=op, json={}).status_code == 200

    # 2b. Attempt to dispatch unit_a while in REPLENISHMENT -> 409 UNIT_LOCKED_IN_REPLENISHMENT
    do_repl = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-LOCK-REPL",
            "project_id": project["id"],
            "lines": [{"item_id": asset_id, "equipment_unit_id": unit_a_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do_repl['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="UNIT_LOCKED_IN_REPLENISHMENT",
    )

    # Move unit_b to DAMAGED via admin manual adjustment & attempt dispatch -> 409 UNIT_NOT_AVAILABLE
    adj_resp = client.post(
        "/api/v1/stock-balances/adjustments",
        headers=admin,
        json={
            "item_id": asset_id,
            "equipment_unit_id": unit_b_id,
            "ownership_source": "SER",
            "from_bucket": "AVAILABLE",
            "to_bucket": "DAMAGED",
            "quantity": "1",
            "notes": "Motor casing cracked in yard inspection",
        },
    )
    assert adj_resp.status_code == 200, adj_resp.text

    do_dmg = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-LOCK-DMG",
            "project_id": project["id"],
            "lines": [{"item_id": asset_id, "equipment_unit_id": unit_b_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do_dmg['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="UNIT_NOT_AVAILABLE",
    )

    # 2c. Bulk accessory: seed 5 AVAILABLE, move 3 to REPLENISHMENT & 1 to DAMAGED -> only 1 AVAILABLE
    assert client.post(
        "/api/v1/stock-balances/opening-stock",
        headers=admin,
        json={"item_id": acc_id, "ownership_source": "SER", "quantity": "5"},
    ).status_code == 201
    assert client.post(
        "/api/v1/stock-balances/adjustments",
        headers=admin,
        json={
            "item_id": acc_id,
            "ownership_source": "SER",
            "from_bucket": "AVAILABLE",
            "to_bucket": "REPLENISHMENT",
            "quantity": "3",
            "notes": "Pipe flange re-welding in workshop",
        },
    ).status_code == 200
    assert client.post(
        "/api/v1/stock-balances/adjustments",
        headers=admin,
        json={
            "item_id": acc_id,
            "ownership_source": "SER",
            "from_bucket": "AVAILABLE",
            "to_bucket": "DAMAGED",
            "quantity": "1",
            "notes": "Damaged HDPE section",
        },
    ).status_code == 200

    # Try dispatching 2 (even though total=5 across buckets, available=1) -> 409 INSUFFICIENT_STOCK
    do_bulk = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-LOCK-BULK",
            "project_id": project["id"],
            "lines": [{"item_id": acc_id, "dispatched_qty": "2"}],
        },
    ).json()["data"]
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do_bulk['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="INSUFFICIENT_STOCK",
    )

    # 2d. Dispatch targeting COMPLETED or CLOSED project -> 409 PROJECT_NOT_ACTIVE
    proj_comp = _create_project(client, op, "PRJ-E2E-COMP", "Completed Site")
    do_comp = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-COMP-PROJ",
            "project_id": proj_comp["id"],
            "lines": [{"item_id": acc_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert client.patch(
        f"/api/v1/projects/{proj_comp['id']}",
        headers=op,
        json={"status": "COMPLETED"},
    ).status_code == 200
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do_comp['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="PROJECT_NOT_ACTIVE",
    )

    proj_closed = _create_project(client, op, "PRJ-E2E-CLSD", "Closed Site")
    do_closed = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-CLSD-PROJ",
            "project_id": proj_closed["id"],
            "lines": [{"item_id": acc_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert client.patch(
        f"/api/v1/projects/{proj_closed['id']}",
        headers=op,
        json={"status": "CLOSED"},
    ).status_code == 200
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do_closed['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="PROJECT_NOT_ACTIVE",
    )


# =============================================================================
# Scenario 3 — Order State Machine & Return Bounds Edge Cases
# =============================================================================
def test_scenario_3_order_state_machine_and_return_bounds(
    client: TestClient,
    tenant: SeededTestTenant,
    as_role,
) -> None:
    admin = as_role("ADMIN")
    op = as_role("SER_OPERATOR")

    proj_a = _create_project(client, op, "PRJ-E2E-3A", "Site Alpha")
    proj_b = _create_project(client, op, "PRJ-E2E-3B", "Site Beta")
    asset_id = str(tenant.asset_item.id)
    unit_a_id = str(tenant.unit_a.id)
    acc_id = str(tenant.accessory_item.id)

    # Seed bulk stock = 10
    assert client.post(
        "/api/v1/stock-balances/opening-stock",
        headers=admin,
        json={"item_id": acc_id, "ownership_source": "SER", "quantity": "10"},
    ).status_code == 201

    # 3a. Validation errors on serialized DO lines (missing unit_id or qty != 1) -> 422 DOMAIN_VALIDATION_ERROR
    assert_error(
        client.post(
            "/api/v1/delivery-orders",
            headers=op,
            json={
                "do_number": "DO-BAD-NOSN",
                "project_id": proj_a["id"],
                "lines": [{"item_id": asset_id, "dispatched_qty": "1"}],
            },
        ),
        status_code=422,
        error_code="DOMAIN_VALIDATION_ERROR",
    )
    assert_error(
        client.post(
            "/api/v1/delivery-orders",
            headers=op,
            json={
                "do_number": "DO-BAD-QTY2",
                "project_id": proj_a["id"],
                "lines": [
                    {
                        "item_id": asset_id,
                        "equipment_unit_id": unit_a_id,
                        "dispatched_qty": "2",
                    }
                ],
            },
        ),
        status_code=422,
        error_code="DOMAIN_VALIDATION_ERROR",
    )

    # Create and dispatch valid DO with 1 serialized unit + 5 bulk pipes to proj_a
    do = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-SM-001",
            "project_id": proj_a["id"],
            "lines": [
                {"item_id": asset_id, "equipment_unit_id": unit_a_id, "dispatched_qty": "1"},
                {"item_id": acc_id, "dispatched_qty": "5"},
            ],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/delivery-orders/{do['id']}/dispatch", headers=op, json={}).status_code == 200
    bulk_line_id = next(ln["id"] for ln in do["lines"] if ln["item_id"] == acc_id)

    # 3b. Edit, cancel, or double-dispatch a DISPATCHED DO -> 409 INVALID_STATE_TRANSITION
    assert_error(
        client.patch(f"/api/v1/delivery-orders/{do['id']}", headers=op, json={"remarks": "mutate"}),
        status_code=409,
        error_code="INVALID_STATE_TRANSITION",
    )
    assert_error(
        client.post(
            f"/api/v1/delivery-orders/{do['id']}/cancel",
            headers=op,
            json={"reason": "Too late"},
        ),
        status_code=409,
        error_code="INVALID_STATE_TRANSITION",
    )
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do['id']}/dispatch", headers=op, json={}),
        status_code=409,
        error_code="INVALID_STATE_TRANSITION",
    )

    # 3c. Returning unit_a against proj_b (where it is NOT deployed) -> 409 UNIT_NOT_AT_PROJECT
    co_wrong_proj = client.post(
        "/api/v1/collection-orders",
        headers=op,
        json={
            "co_number": "CO-WRONG-PRJ",
            "project_id": proj_b["id"],
            "lines": [
                {
                    "item_id": asset_id,
                    "equipment_unit_id": unit_a_id,
                    "returned_qty": "1",
                    "post_return_bucket": "AVAILABLE",
                }
            ],
        },
    ).json()["data"]
    assert_error(
        client.post(f"/api/v1/collection-orders/{co_wrong_proj['id']}/receive", headers=op, json={}),
        status_code=409,
        error_code="UNIT_NOT_AT_PROJECT",
    )

    # 3d. Receive CO #1 returning 3 of 5 bulk pipes, then verify edit/cancel/double-receive blocked
    co1 = client.post(
        "/api/v1/collection-orders",
        headers=op,
        json={
            "co_number": "CO-SM-001",
            "project_id": proj_a["id"],
            "delivery_order_id": do["id"],
            "lines": [
                {
                    "delivery_order_line_id": bulk_line_id,
                    "item_id": acc_id,
                    "returned_qty": "3",
                    "post_return_bucket": "AVAILABLE",
                }
            ],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/collection-orders/{co1['id']}/receive", headers=op, json={}).status_code == 200

    assert_error(
        client.patch(f"/api/v1/collection-orders/{co1['id']}", headers=op, json={"remarks": "edit"}),
        status_code=409,
        error_code="INVALID_STATE_TRANSITION",
    )
    assert_error(
        client.post(
            f"/api/v1/collection-orders/{co1['id']}/cancel",
            headers=op,
            json={"reason": "Cannot cancel received"},
        ),
        status_code=409,
        error_code="INVALID_STATE_TRANSITION",
    )
    assert_error(
        client.post(f"/api/v1/collection-orders/{co1['id']}/receive", headers=op, json={}),
        status_code=409,
        error_code="INVALID_STATE_TRANSITION",
    )

    # 3e. Over-returning across multiple COs: 3 already returned of 5, try returning 3 more -> 409 RECONCILIATION_BOUNDS_EXCEEDED
    co_over = client.post(
        "/api/v1/collection-orders",
        headers=op,
        json={
            "co_number": "CO-SM-OVER",
            "project_id": proj_a["id"],
            "delivery_order_id": do["id"],
            "lines": [
                {
                    "delivery_order_line_id": bulk_line_id,
                    "item_id": acc_id,
                    "returned_qty": "3",
                    "post_return_bucket": "AVAILABLE",
                }
            ],
        },
    ).json()["data"]
    assert_error(
        client.post(f"/api/v1/collection-orders/{co_over['id']}/receive", headers=op, json={}),
        status_code=409,
        error_code="RECONCILIATION_BOUNDS_EXCEEDED",
    )


# =============================================================================
# Scenario 4 — Bulk Partial Returns, Discrepancy Flagging & Loss Write-Off
# =============================================================================
def test_scenario_4_bulk_partial_return_discrepancy_and_loss_write_off(
    client: TestClient,
    tenant: SeededTestTenant,
    as_role,
) -> None:
    admin = as_role("ADMIN")
    op = as_role("SER_OPERATOR")

    project = _create_project(client, op, "PRJ-E2E-004", "Bulk Reconciliation Site")
    acc_id = str(tenant.accessory_item.id)

    # 1. Load opening stock = 10
    open_resp = client.post(
        "/api/v1/stock-balances/opening-stock",
        headers=admin,
        json={"item_id": acc_id, "ownership_source": "SER", "quantity": "10"},
    )
    assert open_resp.status_code == 201, open_resp.text

    # 2. Dispatch 6 -> available=4, in_use=6, DO.status='DISPATCHED'
    do = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-BULK-004",
            "project_id": project["id"],
            "lines": [{"item_id": acc_id, "dispatched_qty": "6"}],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/delivery-orders/{do['id']}/dispatch", headers=op, json={}).status_code == 200
    bal = _get_balance(client, op, acc_id)
    assert Decimal(bal["available_qty"]) == Decimal("4.000")
    assert Decimal(bal["in_use_qty"]) == Decimal("6.000")

    # 3. Partial CO #1 returning 4 to AVAILABLE -> DO.status='PARTIALLY_RETURNED', variance=2, status='OPEN'
    co1 = client.post(
        "/api/v1/collection-orders",
        headers=op,
        json={
            "co_number": "CO-BULK-004",
            "project_id": project["id"],
            "delivery_order_id": do["id"],
            "lines": [
                {
                    "delivery_order_line_id": do["lines"][0]["id"],
                    "item_id": acc_id,
                    "returned_qty": "4",
                    "post_return_bucket": "AVAILABLE",
                }
            ],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/collection-orders/{co1['id']}/receive", headers=op, json={}).status_code == 200

    do_after_partial = client.get(f"/api/v1/delivery-orders/{do['id']}", headers=op).json()["data"]
    assert do_after_partial["status"] == "PARTIALLY_RETURNED"

    recon = client.get(
        f"/api/v1/reconciliation?delivery_order_id={do['id']}", headers=op
    ).json()["items"][0]
    recon_id = recon["id"]
    assert Decimal(recon["variance_qty"]) == Decimal("2.000")
    assert recon["reconciliation_status"] == "OPEN"

    # 4. Flag discrepancy -> status='DISCREPANCY'
    flag_resp = client.post(
        f"/api/v1/reconciliation/{recon_id}/flag-discrepancy",
        headers=op,
        json={"notes": "2m of HDPE pipe missing on site count"},
    )
    assert flag_resp.status_code == 200, flag_resp.text
    assert flag_resp.json()["data"]["reconciliation_status"] == "DISCREPANCY"

    # 5. Attempt write_off_qty=3 (> variance=2) -> 409 RECONCILIATION_BOUNDS_EXCEEDED
    assert_error(
        client.post(
            f"/api/v1/reconciliation/{recon_id}/write-off",
            headers=admin,
            json={
                "write_off_qty": "3",
                "ownership_source": "SER",
                "notes": "Over write-off test",
            },
        ),
        status_code=409,
        error_code="RECONCILIATION_BOUNDS_EXCEEDED",
    )

    # 6. Execute write_off_qty=2 as ADMIN
    wo_resp = client.post(
        f"/api/v1/reconciliation/{recon_id}/write-off",
        headers=admin,
        json={
            "write_off_qty": "2",
            "ownership_source": "SER",
            "notes": "Confirmed lost during trench backfill; back-charged to site",
        },
    )
    assert wo_resp.status_code == 200, wo_resp.text
    wo_data = wo_resp.json()["data"]
    assert Decimal(wo_data["lost_qty"]) == Decimal("2.000")
    assert Decimal(wo_data["variance_qty"]) == Decimal("0.000")
    assert wo_data["reconciliation_status"] == "RESOLVED"
    assert wo_data["resolved_by"] == str(tenant.users["ADMIN"].id)
    assert wo_data["resolved_at"] is not None

    bal_final = _get_balance(client, op, acc_id)
    assert Decimal(bal_final["available_qty"]) == Decimal("8.000")
    assert Decimal(bal_final["in_use_qty"]) == Decimal("0.000")

    do_final = client.get(f"/api/v1/delivery-orders/{do['id']}", headers=op).json()["data"]
    assert do_final["status"] == "CLOSED"

    loss_mvs = client.get(
        f"/api/v1/stock-movements?item_id={acc_id}&movement_type=LOSS_WRITE_OFF",
        headers=op,
    ).json()["items"]
    assert len(loss_mvs) == 1
    assert Decimal(loss_mvs[0]["quantity"]) == Decimal("2.000")
    assert loss_mvs[0]["from_bucket"] == "IN_USE"
    assert loss_mvs[0]["to_bucket"] == "LOST"


# =============================================================================
# Scenario 5 — Project Closure Guard, RBAC Matrix, Ledger Immutability & Analytics
# =============================================================================
def test_scenario_5_closure_guard_rbac_immutability_and_analytics(
    client: TestClient,
    db_session: Session,
    tenant: SeededTestTenant,
    as_role,
) -> None:
    admin = as_role("ADMIN")
    op = as_role("SER_OPERATOR")
    ws = as_role("WORKSHOP_LEAD")
    viewer = as_role("PROJECT_VIEWER")

    project = _create_project(client, op, "PRJ-E2E-005", "RBAC & Analytics Site")
    asset_id = str(tenant.asset_item.id)
    unit_a_id = str(tenant.unit_a.id)
    acc_id = str(tenant.accessory_item.id)

    # Dispatch 1 serialized pump to project
    do = client.post(
        "/api/v1/delivery-orders",
        headers=op,
        json={
            "do_number": "DO-RBAC-005",
            "project_id": project["id"],
            "lines": [{"item_id": asset_id, "equipment_unit_id": unit_a_id, "dispatched_qty": "1"}],
        },
    ).json()["data"]
    assert client.post(f"/api/v1/delivery-orders/{do['id']}/dispatch", headers=op, json={}).status_code == 200

    # 5a. Project Closure Guard while unit is IN_USE -> 409 PROJECT_HAS_ACTIVE_EQUIPMENT
    assert_error(
        client.patch(
            f"/api/v1/projects/{project['id']}",
            headers=admin,
            json={"status": "CLOSED"},
        ),
        status_code=409,
        error_code="PROJECT_HAS_ACTIVE_EQUIPMENT",
    )

    # 5b. RBAC denials (403 INSUFFICIENT_ROLE)
    # PROJECT_VIEWER blocked from creating DO, dispatching DO, creating CO, receiving CO, completing replenishment
    assert_error(
        client.post(
            "/api/v1/delivery-orders",
            headers=viewer,
            json={
                "do_number": "DO-VIEWER-DENY",
                "project_id": project["id"],
                "lines": [{"item_id": acc_id, "dispatched_qty": "1"}],
            },
        ),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )
    assert_error(
        client.post(f"/api/v1/delivery-orders/{do['id']}/dispatch", headers=viewer, json={}),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )
    assert_error(
        client.post(
            "/api/v1/collection-orders",
            headers=viewer,
            json={
                "co_number": "CO-VIEWER-DENY",
                "project_id": project["id"],
                "lines": [
                    {
                        "item_id": asset_id,
                        "equipment_unit_id": unit_a_id,
                        "returned_qty": "1",
                        "post_return_bucket": "AVAILABLE",
                    }
                ],
            },
        ),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )
    assert_error(
        client.post(
            "/api/v1/workshop/replenishment/complete",
            headers=viewer,
            json={"item_id": asset_id, "equipment_unit_id": unit_a_id, "quantity": "1"},
        ),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )

    # SER_OPERATOR blocked from workshop complete, opening-stock, and reconciliation write-off
    assert_error(
        client.post(
            "/api/v1/workshop/replenishment/complete",
            headers=op,
            json={"item_id": asset_id, "equipment_unit_id": unit_a_id, "quantity": "1"},
        ),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )
    assert_error(
        client.post(
            "/api/v1/stock-balances/opening-stock",
            headers=op,
            json={"item_id": acc_id, "quantity": "5"},
        ),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )
    recon_id = client.get(
        f"/api/v1/reconciliation?delivery_order_id={do['id']}", headers=op
    ).json()["items"][0]["id"]
    assert_error(
        client.post(
            f"/api/v1/reconciliation/{recon_id}/write-off",
            headers=op,
            json={"write_off_qty": "1", "notes": "Unauthorized operator write-off"},
        ),
        status_code=403,
        error_code="INSUFFICIENT_ROLE",
    )

    # 5c. Ledger immutability trigger (trg_stock_movements_immutable)
    with pytest.raises(DBAPIError, match="immutable append-only ledger"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE stock_movements SET notes = 'tampered' "
                    "WHERE organization_id = :org_id"
                ),
                {"org_id": tenant.org_id},
            )

    with pytest.raises(DBAPIError, match="immutable append-only ledger"):
        with db_session.begin_nested():
            db_session.execute(
                text("DELETE FROM stock_movements WHERE organization_id = :org_id"),
                {"org_id": tenant.org_id},
            )

    # 5d. Analytics endpoints accurately reflect SER-E2E-TEST transactions
    # (1 unit AVAILABLE @ 15,000 AED, 1 unit IN_USE @ 15,000 AED -> utilization 50%)
    kpi = client.get("/api/v1/analytics/kpi-summary", headers=viewer).json()["data"]
    assert kpi["catalog"]["total_items"] == 2
    assert kpi["catalog"]["asset_skus"] == 1
    assert kpi["catalog"]["accessory_skus"] == 1
    assert kpi["catalog"]["total_serialized_units"] == 2
    assert kpi["buckets"]["available"]["units"] == 1
    assert kpi["buckets"]["in_use"]["units"] == 1
    assert Decimal(kpi["buckets"]["in_use"]["value_aed"]) == Decimal("15000.00")
    assert kpi["utilization_rate_pct"] == 50.0
    assert kpi["active_projects_count"] == 1

    dist = client.get(
        "/api/v1/analytics/stock-distribution?group_by=category", headers=viewer
    ).json()["data"]
    pumps_row = next(s for s in dist["series"] if s["label"] == "Pumps")
    assert Decimal(pumps_row["available_qty"]) == Decimal("1.000")
    assert Decimal(pumps_row["in_use_qty"]) == Decimal("1.000")
    assert Decimal(pumps_row["total_value_aed"]) == Decimal("30000.00")

    proj_util = client.get("/api/v1/analytics/project-utilization", headers=viewer).json()["data"]
    assert len(proj_util["projects"]) == 1
    assert proj_util["projects"][0]["project_code"] == "PRJ-E2E-005"
    assert proj_util["projects"][0]["deployed_units_count"] == 1
    assert Decimal(proj_util["projects"][0]["deployed_value_aed"]) == Decimal("15000.00")

    trends = client.get(
        "/api/v1/analytics/movement-trends?granularity=day", headers=viewer
    ).json()["data"]
    total_dispatched_in_trends = sum(Decimal(p["dispatched_qty"]) for p in trends["points"])
    assert total_dispatched_in_trends == Decimal("1.000")

    recon_health = client.get("/api/v1/analytics/reconciliation-health", headers=viewer).json()["data"]
    open_bucket = next(b for b in recon_health["breakdown"] if b["status"] == "OPEN")
    assert open_bucket["record_count"] == 1
    assert Decimal(open_bucket["total_variance_qty"]) == Decimal("1.000")
    assert Decimal(open_bucket["total_variance_value_aed"]) == Decimal("15000.00")
    assert recon_health["equalization_rate_pct"] == 0.0

    # Quick sanity check that WORKSHOP_LEAD can read analytics & movements
    assert client.get("/api/v1/analytics/kpi-summary", headers=ws).status_code == 200
