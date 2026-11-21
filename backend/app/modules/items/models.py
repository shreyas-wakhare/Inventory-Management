"""SQLAlchemy 2.0 ORM model for the unified equipment & accessory catalog (SDD-1 v1.0.0)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Item(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Master catalog for serialized ASSET equipment and bulk ACCESSORY materials."""

    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("organization_id", "item_code", name="uq_items_org_code"),
        CheckConstraint(
            "product_type IN ('ASSET', 'ACCESSORY')",
            name=conv("ck_items_product_type"),
        ),
        CheckConstraint(
            "unit_price_aed >= 0",
            name=conv("ck_items_unit_price_non_negative"),
        ),
        CheckConstraint(
            "(product_type = 'ASSET' AND is_serialized = TRUE) "
            "OR (product_type = 'ACCESSORY' AND is_serialized = FALSE)",
            name=conv("ck_items_serialization_consistency"),
        ),
        Index("idx_items_org_code", "organization_id", "item_code"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    uom: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="NOS",
        server_default=text("'NOS'"),
    )
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_price_aed: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    is_serialized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
