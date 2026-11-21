"""SQLAlchemy 2.0 ORM model for real-time bucketed stock balances (SDD-1 v1.0.0)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from database.base import Base, UUIDPrimaryKeyMixin


class StockBalance(UUIDPrimaryKeyMixin, Base):
    """Real-time bucketed stock quantities per (organization_id, item_id, ownership_source)."""

    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "item_id",
            "ownership_source",
            name="uq_stock_balances_org_item_source",
        ),
        CheckConstraint(
            "ownership_source IN ('SER', 'SUPPLIER', 'DWT')",
            name=conv("ck_stock_balances_ownership_source"),
        ),
        CheckConstraint(
            "available_qty >= 0 AND in_use_qty >= 0 "
            "AND replenishment_qty >= 0 AND damaged_qty >= 0",
            name=conv("ck_stock_balances_non_negative"),
        ),
        Index("idx_stock_balances_org_item", "organization_id", "item_id"),
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
    ownership_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SER",
        server_default=text("'SER'"),
    )
    available_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    in_use_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    replenishment_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    damaged_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
