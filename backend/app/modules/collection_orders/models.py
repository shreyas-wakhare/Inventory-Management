"""SQLAlchemy 2.0 ORM models for incoming Collection Orders and lines (SDD-1 v1.0.0)."""

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


class CollectionOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Header table for incoming Collection Orders (CO) returned from project sites."""

    __tablename__ = "collection_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "co_number", name="uq_collection_orders_org_co_number"),
        CheckConstraint(
            "status IN ('DRAFT', 'RECEIVED', 'CANCELLED')",
            name=conv("ck_collection_orders_status"),
        ),
        Index("idx_co_org_project", "organization_id", "project_id", desc("collection_date")),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    co_number: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delivery_order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    collection_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
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

    lines: Mapped[list["CollectionOrderLine"]] = relationship(
        back_populates="collection_order",
        cascade="all, delete-orphan",
    )


class CollectionOrderLine(UUIDPrimaryKeyMixin, Base):
    """Line-level return receipts specifying target post_return_bucket."""

    __tablename__ = "collection_order_lines"
    __table_args__ = (
        CheckConstraint(
            "ownership_source IN ('SER', 'SUPPLIER', 'DWT')",
            name=conv("ck_co_lines_ownership_source"),
        ),
        CheckConstraint(
            "returned_qty > 0",
            name=conv("ck_co_lines_returned_positive"),
        ),
        CheckConstraint(
            "post_return_bucket IN ('AVAILABLE', 'REPLENISHMENT', 'DAMAGED')",
            name=conv("ck_co_lines_post_return_bucket"),
        ),
        CheckConstraint(
            "equipment_unit_id IS NULL OR returned_qty = 1",
            name=conv("ck_co_lines_serialized_qty_one"),
        ),
        Index("idx_co_lines_collection_order_id", "collection_order_id"),
        Index(
            "idx_co_lines_do_line_id",
            "delivery_order_line_id",
            postgresql_where=text("delivery_order_line_id IS NOT NULL"),
        ),
        Index(
            "uq_co_lines_co_unit",
            "collection_order_id",
            "equipment_unit_id",
            unique=True,
            postgresql_where=text("equipment_unit_id IS NOT NULL"),
        ),
    )

    collection_order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("collection_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    delivery_order_line_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_order_lines.id", ondelete="RESTRICT"),
        nullable=True,
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
    returned_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    post_return_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    collection_order: Mapped["CollectionOrder"] = relationship(back_populates="lines")
