"""Safe, idempotent CLI reset script restoring the `SER` org to its clean seeded baseline.

Designed strictly for local development / demo resets after manual Swagger or UI
testing. Refuses to execute in staging/production environments and guarantees
`trg_stock_movements_immutable` remains ENABLED even on error.

Usage (from backend/):
    .\\.venv\\Scripts\\python.exe database/seeds/reset_to_baseline.py --dry-run
    .\\.venv\\Scripts\\python.exe database/seeds/reset_to_baseline.py --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

# Allow direct invocation (`python database/seeds/reset_to_baseline.py`) as well as `-m`
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

from app.core.config import settings  # noqa: E402
from database.session import engine  # noqa: E402

TARGET_ORG_CODE = "SER"
EXPECTED_ITEMS = 148
EXPECTED_UNITS = 55
EXPECTED_BALANCES = 148
EXPECTED_MOVEMENTS = 55
PROTECTED_ENVS = {"production", "prod", "staging", "stage"}


def enforce_environment_guard(*, force_dev: bool) -> None:
    """Block execution in staging/production or non-development environments."""
    env_name = settings.APP_ENV.strip().lower()
    if env_name in PROTECTED_ENVS:
        raise RuntimeError(
            f"REFUSED: reset_to_baseline.py cannot run when APP_ENV='{settings.APP_ENV}'."
        )
    if env_name != "development" and not force_dev:
        raise RuntimeError(
            f"REFUSED: APP_ENV is '{settings.APP_ENV}' (expected 'development'). "
            "Pass --force-dev only for local non-production test environments."
        )


def _resolve_ser_org_id(conn: Connection) -> UUID:
    org_id = conn.execute(
        text("SELECT id FROM organizations WHERE code = :code"),
        {"code": TARGET_ORG_CODE},
    ).scalar_one_or_none()
    if org_id is None:
        raise RuntimeError(
            f"Organization '{TARGET_ORG_CODE}' not found. Run import_material_list.py first."
        )
    return org_id


def inspect_cleanup_plan(conn: Connection, org_id: UUID) -> dict[str, int]:
    """Compute exact counts of non-baseline rows scoped strictly to the SER organization."""
    plan: dict[str, int] = {}
    plan["reconciliation_records_to_delete"] = int(
        conn.execute(
            text("SELECT COUNT(*) FROM reconciliation_records WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["collection_order_lines_to_delete"] = int(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM collection_order_lines "
                "WHERE collection_order_id IN ("
                "  SELECT id FROM collection_orders WHERE organization_id = :org_id"
                ")"
            ),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["collection_orders_to_delete"] = int(
        conn.execute(
            text("SELECT COUNT(*) FROM collection_orders WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["delivery_order_lines_to_delete"] = int(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM delivery_order_lines "
                "WHERE delivery_order_id IN ("
                "  SELECT id FROM delivery_orders WHERE organization_id = :org_id"
                ")"
            ),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["delivery_orders_to_delete"] = int(
        conn.execute(
            text("SELECT COUNT(*) FROM delivery_orders WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["projects_to_delete"] = int(
        conn.execute(
            text("SELECT COUNT(*) FROM projects WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["stock_movements_to_delete"] = int(
        conn.execute(
            text(
                """
                WITH ranked_opening AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY equipment_unit_id
                            ORDER BY created_at ASC, id ASC
                        ) AS rn
                    FROM stock_movements
                    WHERE organization_id = :org_id
                      AND movement_type = 'OPENING_STOCK'
                      AND equipment_unit_id IS NOT NULL
                )
                SELECT COUNT(*)
                FROM stock_movements sm
                WHERE sm.organization_id = :org_id
                  AND (
                      sm.movement_type <> 'OPENING_STOCK'
                      OR sm.equipment_unit_id IS NULL
                      OR sm.id IN (SELECT id FROM ranked_opening WHERE rn > 1)
                  )
                """
            ),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["equipment_units_to_reset"] = int(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM equipment_units "
                "WHERE organization_id = :org_id "
                "  AND (status <> 'AVAILABLE' OR condition_status <> 'GOOD' "
                "       OR current_project_id IS NOT NULL OR notes IS NOT NULL)"
            ),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["non_ser_balances_to_delete"] = int(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM stock_balances "
                "WHERE organization_id = :org_id AND ownership_source <> 'SER'"
            ),
            {"org_id": org_id},
        ).scalar_one()
    )
    plan["ser_balances_to_resync"] = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM stock_balances sb
                WHERE sb.organization_id = :org_id
                  AND sb.ownership_source = 'SER'
                  AND (
                      sb.in_use_qty <> 0
                      OR sb.replenishment_qty <> 0
                      OR sb.damaged_qty <> 0
                      OR sb.available_qty <> COALESCE((
                          SELECT COUNT(*)::numeric(14, 3)
                          FROM equipment_units eu
                          WHERE eu.organization_id = sb.organization_id
                            AND eu.item_id = sb.item_id
                      ), 0)
                  )
                """
            ),
            {"org_id": org_id},
        ).scalar_one()
    )
    return plan


def execute_baseline_reset(org_id: UUID) -> dict[str, int]:
    """Execute atomic baseline cleanup and guarantee immutability trigger stays ENABLED."""
    applied: dict[str, int] = {}
    conn = engine.connect()
    tx = conn.begin()
    try:
        applied["reconciliation_records_deleted"] = conn.execute(
            text("DELETE FROM reconciliation_records WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).rowcount

        applied["collection_order_lines_deleted"] = conn.execute(
            text(
                "DELETE FROM collection_order_lines "
                "WHERE collection_order_id IN ("
                "  SELECT id FROM collection_orders WHERE organization_id = :org_id"
                ")"
            ),
            {"org_id": org_id},
        ).rowcount

        applied["collection_orders_deleted"] = conn.execute(
            text("DELETE FROM collection_orders WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).rowcount

        applied["delivery_order_lines_deleted"] = conn.execute(
            text(
                "DELETE FROM delivery_order_lines "
                "WHERE delivery_order_id IN ("
                "  SELECT id FROM delivery_orders WHERE organization_id = :org_id"
                ")"
            ),
            {"org_id": org_id},
        ).rowcount

        applied["delivery_orders_deleted"] = conn.execute(
            text("DELETE FROM delivery_orders WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).rowcount

        # Clear equipment custody before deleting projects (ON DELETE RESTRICT)
        applied["equipment_units_reset"] = conn.execute(
            text(
                "UPDATE equipment_units "
                "SET status = 'AVAILABLE', condition_status = 'GOOD', "
                "    current_project_id = NULL, notes = NULL "
                "WHERE organization_id = :org_id"
            ),
            {"org_id": org_id},
        ).rowcount

        # Temporarily disable immutability trigger, prune non-baseline rows, re-enable immediately
        conn.execute(text("ALTER TABLE stock_movements DISABLE TRIGGER trg_stock_movements_immutable"))
        applied["stock_movements_deleted"] = conn.execute(
            text(
                """
                WITH ranked_opening AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY equipment_unit_id
                            ORDER BY created_at ASC, id ASC
                        ) AS rn
                    FROM stock_movements
                    WHERE organization_id = :org_id
                      AND movement_type = 'OPENING_STOCK'
                      AND equipment_unit_id IS NOT NULL
                )
                DELETE FROM stock_movements sm
                WHERE sm.organization_id = :org_id
                  AND (
                      sm.movement_type <> 'OPENING_STOCK'
                      OR sm.equipment_unit_id IS NULL
                      OR sm.id IN (SELECT id FROM ranked_opening WHERE rn > 1)
                  )
                """
            ),
            {"org_id": org_id},
        ).rowcount
        conn.execute(text("ALTER TABLE stock_movements ENABLE TRIGGER trg_stock_movements_immutable"))

        applied["projects_deleted"] = conn.execute(
            text("DELETE FROM projects WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).rowcount

        applied["non_ser_balances_deleted"] = conn.execute(
            text(
                "DELETE FROM stock_balances "
                "WHERE organization_id = :org_id AND ownership_source <> 'SER'"
            ),
            {"org_id": org_id},
        ).rowcount

        # Ensure every SER catalog item has a SER stock_balances row
        conn.execute(
            text(
                """
                INSERT INTO stock_balances (
                    organization_id, item_id, ownership_source,
                    available_qty, in_use_qty, replenishment_qty, damaged_qty
                )
                SELECT i.organization_id, i.id, 'SER', 0, 0, 0, 0
                FROM items i
                WHERE i.organization_id = :org_id
                ON CONFLICT (organization_id, item_id, ownership_source) DO NOTHING
                """
            ),
            {"org_id": org_id},
        )

        # Re-sync SER balances: 1.000 per serialized ASSET unit, 0.000 for ACCESSORY
        applied["ser_balances_resynced"] = conn.execute(
            text(
                """
                UPDATE stock_balances sb
                SET available_qty = COALESCE((
                        SELECT COUNT(*)::numeric(14, 3)
                        FROM equipment_units eu
                        WHERE eu.organization_id = sb.organization_id
                          AND eu.item_id = sb.item_id
                    ), 0),
                    in_use_qty = 0,
                    replenishment_qty = 0,
                    damaged_qty = 0
                WHERE sb.organization_id = :org_id
                  AND sb.ownership_source = 'SER'
                """
            ),
            {"org_id": org_id},
        ).rowcount

        tx.commit()
        return applied
    except Exception:
        tx.rollback()
        raise
    finally:
        conn.close()
        # Defensive guarantee: verify trigger is ENABLED in a fresh autocommit check
        with engine.begin() as verify_conn:
            tgenabled = verify_conn.execute(
                text(
                    "SELECT tgenabled FROM pg_trigger "
                    "WHERE tgname = 'trg_stock_movements_immutable'"
                )
            ).scalar_one_or_none()
            if tgenabled != "O":
                verify_conn.execute(
                    text("ALTER TABLE stock_movements ENABLE TRIGGER trg_stock_movements_immutable")
                )


def verify_and_print_summary(org_id: UUID) -> None:
    """Verify exact SER baseline invariants and render a structured summary table."""
    with engine.connect() as conn:
        items_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM items WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        asset_items = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM items "
                    "WHERE organization_id = :org_id AND product_type = 'ASSET'"
                ),
                {"org_id": org_id},
            ).scalar_one()
        )
        accessory_items = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM items "
                    "WHERE organization_id = :org_id AND product_type = 'ACCESSORY'"
                ),
                {"org_id": org_id},
            ).scalar_one()
        )
        units_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM equipment_units WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        units_available = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM equipment_units "
                    "WHERE organization_id = :org_id AND status = 'AVAILABLE' "
                    "  AND condition_status = 'GOOD' AND current_project_id IS NULL"
                ),
                {"org_id": org_id},
            ).scalar_one()
        )
        balances_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM stock_balances WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        avail_sum, in_use_sum, repl_sum, dmg_sum = conn.execute(
            text(
                "SELECT COALESCE(SUM(available_qty), 0), COALESCE(SUM(in_use_qty), 0), "
                "       COALESCE(SUM(replenishment_qty), 0), COALESCE(SUM(damaged_qty), 0) "
                "FROM stock_balances WHERE organization_id = :org_id"
            ),
            {"org_id": org_id},
        ).one()
        movements_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM stock_movements WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        movements_opening = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM stock_movements "
                    "WHERE organization_id = :org_id AND movement_type = 'OPENING_STOCK'"
                ),
                {"org_id": org_id},
            ).scalar_one()
        )
        projects_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM projects WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        dos_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM delivery_orders WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        cos_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM collection_orders WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        recons_total = int(
            conn.execute(
                text("SELECT COUNT(*) FROM reconciliation_records WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).scalar_one()
        )
        tgenabled = conn.execute(
            text(
                "SELECT tgenabled FROM pg_trigger "
                "WHERE tgname = 'trg_stock_movements_immutable'"
            )
        ).scalar_one()
        trigger_status = "ENABLED" if tgenabled == "O" else f"UNEXPECTED({tgenabled})"

    rows = [
        ("items", f"{items_total} (ASSET={asset_items}, ACCESSORY={accessory_items})", items_total == EXPECTED_ITEMS),
        ("equipment_units", f"{units_total} (AVAILABLE/GOOD={units_available})", units_total == EXPECTED_UNITS and units_available == EXPECTED_UNITS),
        ("stock_balances", f"{balances_total} (avail={avail_sum}, in_use={in_use_sum}, repl={repl_sum}, dmg={dmg_sum})", balances_total == EXPECTED_BALANCES and str(avail_sum) == "55.000" and str(in_use_sum) == "0.000" and str(repl_sum) == "0.000" and str(dmg_sum) == "0.000"),
        ("stock_movements", f"{movements_total} (OPENING_STOCK={movements_opening})", movements_total == EXPECTED_MOVEMENTS and movements_opening == EXPECTED_MOVEMENTS),
        ("projects", str(projects_total), projects_total == 0),
        ("delivery_orders", str(dos_total), dos_total == 0),
        ("collection_orders", str(cos_total), cos_total == 0),
        ("reconciliation_records", str(recons_total), recons_total == 0),
        ("trg_stock_movements_immutable", trigger_status, trigger_status == "ENABLED"),
    ]

    print("\n=== Post-Reset Baseline Verification (SER Organization) ===")
    print(f"{'Check':32s} | {'Observed Value':62s} | {'Status'}")
    print("-" * 106)
    all_ok = True
    for name, observed, ok in rows:
        all_ok = all_ok and ok
        print(f"{name:32s} | {observed:62s} | {'OK' if ok else 'MISMATCH'}")

    if not all_ok:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset the local SER organization in PostgreSQL back to its clean seeded baseline."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview counts of rows that would be deleted/reset without modifying the database.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt.",
    )
    parser.add_argument(
        "--force-dev",
        action="store_true",
        help="Allow running in a custom non-production APP_ENV (still blocked in staging/production).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    enforce_environment_guard(force_dev=args.force_dev)

    with engine.connect() as conn:
        org_id = _resolve_ser_org_id(conn)
        plan = inspect_cleanup_plan(conn, org_id)

    print(f"=== SER Baseline Reset Plan (APP_ENV={settings.APP_ENV}, org={TARGET_ORG_CODE}) ===")
    for key, count in plan.items():
        print(f"  {key:36s}: {count}")

    if args.dry_run:
        print("\n[DRY-RUN] No changes were committed to PostgreSQL.")
        verify_and_print_summary(org_id)
        return

    if not args.yes:
        reply = input(
            f"\nProceed with resetting organization '{TARGET_ORG_CODE}' to clean baseline? [y/N]: "
        ).strip().lower()
        if reply not in {"y", "yes"}:
            print("Aborted by user. No changes made.")
            return

    applied = execute_baseline_reset(org_id)
    print("\n=== Applied Reset Actions (Committed Atomically) ===")
    for key, count in applied.items():
        print(f"  {key:36s}: {count}")

    verify_and_print_summary(org_id)


if __name__ == "__main__":
    main()
