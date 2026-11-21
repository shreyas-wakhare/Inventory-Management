"""Idempotent Material List importer for the SER Inventory Management System.

Imports the `Material List` sheet from the legacy Excel workbook into PostgreSQL
following locked SDD-1 (`docs/sdd-1-Database.md` Section 4.1) rules inside a
single atomic transaction.

Usage (from backend/):
    .\\.venv\\Scripts\\python.exe -m database.seeds.import_material_list
    .\\.venv\\Scripts\\python.exe -m database.seeds.import_material_list --file "path/to/file.xlsx"
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import openpyxl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 - ensure all ORM models are registered
from app.modules.equipment_units.models import EquipmentUnit
from app.modules.items.models import Item
from app.modules.stock_balances.models import StockBalance
from app.modules.stock_movements.models import StockMovement
from app.modules.users.models import Organization, User
from database.session import SessionLocal

DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "SER Inventory tracker Master - Oct 2026 R4.xlsx"
)

DEFAULT_ORG_CODE = "SER"
DEFAULT_ORG_NAME = "SER Department"
IMPORT_USER_EMAIL = "system.import@ser.local"
IMPORT_USER_NAME = "SER System Importer"
IMPORT_USER_ROLE = "ADMIN"

MISSING_SERIAL_MARKERS = {"", "-", "N/A", "NA", "NONE", "NIL"}
AUTO_SERIAL_NOTE = (
    "Auto-generated serial during legacy Material List import; verify physical tag"
)


@dataclass(frozen=True)
class NormalizedMaterialRow:
    """Sanitized Material List row ready for persistence."""

    row_number: int
    item_code: str
    serial_number: str | None
    description: str
    uom: str
    unit_price_aed: Decimal
    product_type: str
    is_serialized: bool
    sub_category: str | None
    category: str


@dataclass
class ImportStats:
    """Tracks created vs skipped records for idempotency auditing."""

    rows_read: int = 0
    items_created: int = 0
    items_existing: int = 0
    units_created: int = 0
    units_existing: int = 0
    units_auto_serialized: int = 0
    balances_created: int = 0
    balances_updated: int = 0
    movements_created: int = 0


def clean_str(value: Any) -> str:
    """Safely convert any Excel cell value to a trimmed string."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_uom(value: Any) -> str:
    """Trim whitespace and normalize UOM to uppercase (e.g., 'Pcs ' -> 'PCS')."""
    cleaned = clean_str(value).upper()
    return cleaned if cleaned else "NOS"


def normalize_price(value: Any) -> Decimal:
    """Parse Unit Price AED safely to non-negative NUMERIC(12, 2); defaults to 0.00."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
    else:
        raw = clean_str(value).upper().replace("AED", "").replace(",", "").strip()
        if not raw or raw in {"-", "N/A", "NA"}:
            return Decimal("0.00")
        try:
            amount = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid Unit Price AED value: {value!r}") from exc

    if amount < 0:
        raise ValueError(f"Negative Unit Price AED is not permitted: {value!r}")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_product_type(value: Any, row_number: int) -> tuple[str, bool]:
    """Map Excel Product Type ('Asset' / 'Accessories') to SDD-1 enum and serialization flag."""
    raw = clean_str(value).upper()
    if raw == "ASSET":
        return "ASSET", True
    if raw in {"ACCESSORY", "ACCESSORIES"}:
        return "ACCESSORY", False
    raise ValueError(f"Row {row_number}: unsupported Product Type {value!r}")


def load_material_list_rows(excel_path: Path) -> list[NormalizedMaterialRow]:
    """Read and normalize all non-empty rows from the `Material List` sheet."""
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel workbook not found: {excel_path}")

    workbook = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    try:
        sheet_name = next(
            (name for name in workbook.sheetnames if name.strip().lower() == "material list"),
            None,
        )
        if sheet_name is None:
            raise ValueError(
                f"Sheet 'Material List' not found in {excel_path.name}. "
                f"Available sheets: {workbook.sheetnames}"
            )

        worksheet = workbook[sheet_name]
        raw_rows = list(worksheet.iter_rows(values_only=True))
    finally:
        workbook.close()

    if not raw_rows:
        return []

    headers = [clean_str(cell) for cell in raw_rows[0]]
    col_index = {header: idx for idx, header in enumerate(headers)}

    required_columns = [
        "Item Code",
        "Eqp Sl.No",
        "Description",
        "Uom",
        "Unit Price AED",
        "Product Type",
        "Sub Category",
        "Category",
    ]
    missing_cols = [col for col in required_columns if col not in col_index]
    if missing_cols:
        raise ValueError(f"Missing expected Material List columns: {missing_cols}")

    normalized: list[NormalizedMaterialRow] = []

    for row_number, raw_row in enumerate(raw_rows[1:], start=2):
        if not any(cell is not None and str(cell).strip() != "" for cell in raw_row):
            continue

        def get_cell(col_name: str) -> Any:
            idx = col_index[col_name]
            return raw_row[idx] if idx < len(raw_row) else None

        item_code = clean_str(get_cell("Item Code")).upper()
        if not item_code:
            raise ValueError(f"Row {row_number}: Item Code cannot be blank")

        description = clean_str(get_cell("Description"))
        if not description:
            raise ValueError(f"Row {row_number} ({item_code}): Description cannot be blank")

        category = clean_str(get_cell("Category"))
        if not category:
            raise ValueError(f"Row {row_number} ({item_code}): Category cannot be blank")

        sub_cat_raw = clean_str(get_cell("Sub Category"))
        sub_category = sub_cat_raw if sub_cat_raw else None

        product_type, is_serialized = normalize_product_type(get_cell("Product Type"), row_number)
        uom = normalize_uom(get_cell("Uom"))
        unit_price_aed = normalize_price(get_cell("Unit Price AED"))

        raw_serial = clean_str(get_cell("Eqp Sl.No"))
        serial_number: str | None = None
        if is_serialized and raw_serial.upper() not in MISSING_SERIAL_MARKERS:
            serial_number = raw_serial

        normalized.append(
            NormalizedMaterialRow(
                row_number=row_number,
                item_code=item_code,
                serial_number=serial_number,
                description=description,
                uom=uom,
                unit_price_aed=unit_price_aed,
                product_type=product_type,
                is_serialized=is_serialized,
                sub_category=sub_category,
                category=category,
            )
        )

    return normalized


def ensure_default_org_and_user(db: Session) -> tuple[Organization, User]:
    """Idempotently ensure default SER organization and system ADMIN import user exist."""
    org = db.scalar(select(Organization).where(Organization.code == DEFAULT_ORG_CODE))
    if org is None:
        org = Organization(code=DEFAULT_ORG_CODE, name=DEFAULT_ORG_NAME, is_active=True)
        db.add(org)
        db.flush()

    user = db.scalar(
        select(User).where(
            User.organization_id == org.id,
            User.email == IMPORT_USER_EMAIL,
        )
    )
    if user is None:
        user = User(
            organization_id=org.id,
            full_name=IMPORT_USER_NAME,
            email=IMPORT_USER_EMAIL,
            role=IMPORT_USER_ROLE,
            is_active=True,
        )
        db.add(user)
        db.flush()

    return org, user


def import_material_list(excel_path: Path) -> ImportStats:
    """Import Material List sheet into PostgreSQL inside a single atomic transaction."""
    rows = load_material_list_rows(excel_path)
    stats = ImportStats(rows_read=len(rows))

    with SessionLocal() as db:
        with db.begin():
            org, import_user = ensure_default_org_and_user(db)

            # 1. Load existing catalog items for this organization
            existing_items: dict[str, Item] = {
                item.item_code: item
                for item in db.scalars(
                    select(Item).where(Item.organization_id == org.id)
                ).all()
            }

            # 2. Deduplicate and upsert items by (organization_id, item_code)
            seen_codes: set[str] = set()
            for row in rows:
                if row.item_code in seen_codes:
                    existing_item = existing_items[row.item_code]
                    if existing_item.product_type != row.product_type:
                        raise ValueError(
                            f"Row {row.row_number}: conflicting product_type for "
                            f"{row.item_code} ({existing_item.product_type} vs {row.product_type})"
                        )
                    continue

                seen_codes.add(row.item_code)
                if row.item_code in existing_items:
                    stats.items_existing += 1
                    continue

                new_item = Item(
                    organization_id=org.id,
                    item_code=row.item_code,
                    description=row.description,
                    uom=row.uom,
                    product_type=row.product_type,
                    category=row.category,
                    sub_category=row.sub_category,
                    unit_price_aed=row.unit_price_aed,
                    is_serialized=row.is_serialized,
                    is_active=True,
                )
                db.add(new_item)
                existing_items[row.item_code] = new_item
                stats.items_created += 1

            db.flush()

            # 3. Load existing equipment units & stock balances for idempotency
            existing_units_by_serial: dict[str, EquipmentUnit] = {
                unit.serial_number: unit
                for unit in db.scalars(
                    select(EquipmentUnit).where(EquipmentUnit.organization_id == org.id)
                ).all()
            }
            existing_balances_by_item_id: dict[Any, StockBalance] = {
                bal.item_id: bal
                for bal in db.scalars(
                    select(StockBalance).where(
                        StockBalance.organization_id == org.id,
                        StockBalance.ownership_source == "SER",
                    )
                ).all()
            }

            # 4. Insert serialized ASSET units and record OPENING_STOCK movements
            auto_serial_seq: dict[str, int] = defaultdict(int)
            newly_added_units_per_item: dict[Any, int] = defaultdict(int)

            for row in rows:
                if not row.is_serialized:
                    continue

                item = existing_items[row.item_code]
                unit_note: str | None = None
                serial = row.serial_number

                if serial is None:
                    auto_serial_seq[row.item_code] += 1
                    serial = f"AUTO-{row.item_code}-{auto_serial_seq[row.item_code]:03d}"
                    unit_note = AUTO_SERIAL_NOTE

                if serial in existing_units_by_serial:
                    stats.units_existing += 1
                    continue

                unit = EquipmentUnit(
                    organization_id=org.id,
                    item_id=item.id,
                    serial_number=serial,
                    status="AVAILABLE",
                    condition_status="GOOD",
                    current_project_id=None,
                    notes=unit_note,
                )
                db.add(unit)
                db.flush()  # Populate unit.id for stock_movements FK

                existing_units_by_serial[serial] = unit
                newly_added_units_per_item[item.id] += 1
                stats.units_created += 1
                if unit_note is not None:
                    stats.units_auto_serialized += 1

                movement = StockMovement(
                    organization_id=org.id,
                    item_id=item.id,
                    equipment_unit_id=unit.id,
                    project_id=None,
                    ownership_source="SER",
                    movement_type="OPENING_STOCK",
                    from_bucket="EXTERNAL",
                    to_bucket="AVAILABLE",
                    quantity=Decimal("1"),
                    reference_type="OPENING_BALANCE",
                    reference_number="MATERIAL-LIST-IMPORT",
                    notes=f"Initial Material List import ({excel_path.name})",
                    created_by=import_user.id,
                )
                db.add(movement)
                stats.movements_created += 1

            # 5. Seed/sync stock_balances for ASSET items & initialize zero balances for ACCESSORY
            for item_code in sorted(seen_codes):
                item = existing_items[item_code]
                balance = existing_balances_by_item_id.get(item.id)

                if item.is_serialized:
                    added_units = newly_added_units_per_item.get(item.id, 0)
                    if balance is None:
                        balance = StockBalance(
                            organization_id=org.id,
                            item_id=item.id,
                            ownership_source="SER",
                            available_qty=Decimal(added_units),
                            in_use_qty=Decimal("0"),
                            replenishment_qty=Decimal("0"),
                            damaged_qty=Decimal("0"),
                        )
                        db.add(balance)
                        existing_balances_by_item_id[item.id] = balance
                        stats.balances_created += 1
                    elif added_units > 0:
                        balance.available_qty += Decimal(added_units)
                        stats.balances_updated += 1
                else:
                    if balance is None:
                        balance = StockBalance(
                            organization_id=org.id,
                            item_id=item.id,
                            ownership_source="SER",
                            available_qty=Decimal("0"),
                            in_use_qty=Decimal("0"),
                            replenishment_qty=Decimal("0"),
                            damaged_qty=Decimal("0"),
                        )
                        db.add(balance)
                        existing_balances_by_item_id[item.id] = balance
                        stats.balances_created += 1

    return stats


def print_database_summary(stats: ImportStats) -> None:
    """Query PostgreSQL for live verification counts and print an import report."""
    with SessionLocal() as db:
        org_count = db.scalar(select(func.count()).select_from(Organization)) or 0
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        total_items = db.scalar(select(func.count()).select_from(Item)) or 0
        asset_items = (
            db.scalar(select(func.count()).select_from(Item).where(Item.product_type == "ASSET"))
            or 0
        )
        accessory_items = (
            db.scalar(
                select(func.count()).select_from(Item).where(Item.product_type == "ACCESSORY")
            )
            or 0
        )
        unit_count = db.scalar(select(func.count()).select_from(EquipmentUnit)) or 0
        balance_count = db.scalar(select(func.count()).select_from(StockBalance)) or 0
        total_available_qty = (
            db.scalar(select(func.coalesce(func.sum(StockBalance.available_qty), 0))) or 0
        )
        movement_count = db.scalar(select(func.count()).select_from(StockMovement)) or 0
        uom_rows = db.execute(
            select(Item.uom, func.count(Item.id)).group_by(Item.uom).order_by(Item.uom)
        ).all()

    print("=== Material List Import Run Stats ===")
    print(f"Rows read from sheet      : {stats.rows_read}")
    print(f"Items created / existing  : {stats.items_created} / {stats.items_existing}")
    print(f"Units created / existing  : {stats.units_created} / {stats.units_existing}")
    print(f"Units auto-serialized     : {stats.units_auto_serialized}")
    print(f"Balances created / updated: {stats.balances_created} / {stats.balances_updated}")
    print(f"Movements created         : {stats.movements_created}")
    print("\n=== Live PostgreSQL Verification Counts ===")
    print(f"organizations             : {org_count}")
    print(f"users                     : {user_count}")
    print(f"items                     : {total_items} (ASSET: {asset_items}, ACCESSORY: {accessory_items})")
    print(f"equipment_units           : {unit_count}")
    print(f"stock_balances            : {balance_count} (sum available_qty: {total_available_qty})")
    print(f"stock_movements           : {movement_count}")
    print(f"Normalized UOMs           : {dict(uom_rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the Material List sheet into PostgreSQL idempotently."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_EXCEL_PATH,
        help="Path to the Excel workbook containing the Material List sheet.",
    )
    args = parser.parse_args()
    stats = import_material_list(args.file)
    print_database_summary(stats)


if __name__ == "__main__":
    main()

