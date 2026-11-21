"""SQLAlchemy 2.0 ORM model for the immutable stock_movements audit ledger (SDD-1 v1.0.0)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from database.base import Base, UUIDPrimaryKeyMixin


class StockMovement(UUIDPrimaryKeyMixin, Base):
    """Append-only immutable audit ledger recording every inventory bucket transition."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "ownership_source IN ('SER', 'SUPPLIER', 'DWT')",
            name=conv("ck_stock_movements_ownership_source"),
        ),
        CheckConstraint(
            "movement_type IN ("
            "'OPENING_STOCK', 'DO_DISPATCH', 'CO_RETURN_AVAILABLE', "
            "'CO_RETURN_REPLENISHMENT', 'CO_RETURN_DAMAGED', "
            "'REPLENISHMENT_COMPLETE', 'LOSS_WRITE_OFF', 'MANUAL_ADJUSTMENT'"
            ")",
            name=conv("ck_stock_movements_type"),
        ),
        CheckConstraint(
            "from_bucket IS NULL OR from_bucket IN "
            "('AVAILABLE', 'IN_USE', 'REPLENISHMENT', 'DAMAGED', 'EXTERNAL')",
            name=conv("ck_stock_movements_from_bucket"),
        ),
        CheckConstraint(
            "to_bucket IS NULL OR to_bucket IN "
            "('AVAILABLE', 'IN_USE', 'REPLENISHMENT', 'DAMAGED', 'RETIRED', 'LOST')",
            name=conv("ck_stock_movements_to_bucket"),
        ),
        CheckConstraint(
            "quantity > 0",
            name=conv("ck_stock_movements_quantity_positive"),
        ),
        CheckConstraint(
            "equipment_unit_id IS NULL OR quantity = 1",
            name=conv("ck_stock_movements_serialized_qty_one"),
        ),
        CheckConstraint(
            "reference_type IS NULL OR reference_type IN ("
            "'DELIVERY_ORDER', 'COLLECTION_ORDER', 'WORKSHOP_TICKET', "
            "'RECONCILIATION', 'OPENING_BALANCE', 'ADJUSTMENT'"
            ")",
            name=conv("ck_stock_movements_reference_type"),
        ),
        Index("idx_movements_org_item_time", "organization_id", "item_id", desc("created_at")),
        Index(
            "idx_movements_org_unit_time",
            "organization_id",
            "equipment_unit_id",
            desc("created_at"),
            postgresql_where=text("equipment_unit_id IS NOT NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    equipment_unit_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("equipment_units.id", ondelete="RESTRICT"),
        nullable=True,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ownership_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SER",
        server_default=text("'SER'"),
    )
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
