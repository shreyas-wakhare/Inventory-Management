"""SQLAlchemy 2.0 ORM models for outgoing Delivery Orders and lines (SDD-1 v1.0.0)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import conv

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeliveryOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Header table for outgoing Delivery Orders (DO) to project sites."""

    __tablename__ = "delivery_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "do_number", name="uq_delivery_orders_org_do_number"),
        CheckConstraint(
            "status IN ('DRAFT', 'DISPATCHED', 'PARTIALLY_RETURNED', 'CLOSED', 'CANCELLED')",
            name=conv("ck_delivery_orders_status"),
        ),
        Index("idx_do_org_project", "organization_id", "project_id", desc("dispatch_date")),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    do_number: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dispatch_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    lines: Mapped[list["DeliveryOrderLine"]] = relationship(
        back_populates="delivery_order",
        cascade="all, delete-orphan",
    )


class DeliveryOrderLine(UUIDPrimaryKeyMixin, Base):
    """Line-level items and serialized equipment units dispatched on a DO."""

    __tablename__ = "delivery_order_lines"
    __table_args__ = (
        CheckConstraint(
            "ownership_source IN ('SER', 'SUPPLIER', 'DWT')",
            name=conv("ck_do_lines_ownership_source"),
        ),
        CheckConstraint(
            "dispatched_qty > 0",
            name=conv("ck_do_lines_dispatched_positive"),
        ),
        CheckConstraint(
            "returned_qty >= 0 AND lost_qty >= 0",
            name=conv("ck_do_lines_returned_lost_non_negative"),
        ),
        CheckConstraint(
            "returned_qty + lost_qty <= dispatched_qty",
            name=conv("ck_do_lines_return_loss_bound"),
        ),
        CheckConstraint(
            "equipment_unit_id IS NULL OR dispatched_qty = 1",
            name=conv("ck_do_lines_serialized_qty_one"),
        ),
        Index("idx_do_lines_delivery_order_id", "delivery_order_id"),
        Index(
            "uq_do_lines_do_unit",
            "delivery_order_id",
            "equipment_unit_id",
            unique=True,
            postgresql_where=text("equipment_unit_id IS NOT NULL"),
        ),
    )

    delivery_order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="CASCADE"),
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
    ownership_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SER",
        server_default=text("'SER'"),
    )
    dispatched_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    returned_qty: Mapped[Decimal] = mapped_column(
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    delivery_order: Mapped["DeliveryOrder"] = relationship(back_populates="lines")
