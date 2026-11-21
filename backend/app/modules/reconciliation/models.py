"""SQLAlchemy 2.0 ORM model for project/DO reconciliation records (SDD-1 v1.0.0)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from database.base import Base, UUIDPrimaryKeyMixin


class ReconciliationRecord(UUIDPrimaryKeyMixin, Base):
    """Outgoing vs. incoming + lost equalization record with stored generated variance_qty."""

    __tablename__ = "reconciliation_records"
    __table_args__ = (
        CheckConstraint(
            "outgoing_qty >= 0 AND incoming_qty >= 0 AND lost_qty >= 0",
            name=conv("ck_recon_qty_non_negative"),
        ),
        CheckConstraint(
            "incoming_qty + lost_qty <= outgoing_qty",
            name=conv("ck_recon_qty_bounds"),
        ),
        CheckConstraint(
            "reconciliation_status IN ('OPEN', 'EQUALIZED', 'DISCREPANCY', 'RESOLVED')",
            name=conv("ck_recon_status"),
        ),
        CheckConstraint(
            "(reconciliation_status = 'RESOLVED' AND resolved_by IS NOT NULL "
            "AND resolved_at IS NOT NULL) OR (reconciliation_status <> 'RESOLVED')",
            name=conv("ck_recon_resolved_audit"),
        ),
        Index("idx_recon_org_status", "organization_id", "reconciliation_status", "project_id"),
        Index(
            "uq_recon_serialized_unit",
            "organization_id",
            "delivery_order_id",
            "item_id",
            "equipment_unit_id",
            unique=True,
            postgresql_where=text("equipment_unit_id IS NOT NULL"),
        ),
        Index(
            "uq_recon_bulk_item",
            "organization_id",
            "delivery_order_id",
            "item_id",
            unique=True,
            postgresql_where=text("equipment_unit_id IS NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delivery_order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="RESTRICT"),
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
    outgoing_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    incoming_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    lost_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    variance_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        Computed("outgoing_qty - incoming_qty - lost_qty", persisted=True),
        nullable=False,
    )
    reconciliation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OPEN",
        server_default=text("'OPEN'"),
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
