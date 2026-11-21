"""SQLAlchemy 2.0 ORM model for serialized physical equipment units (SDD-1 v1.0.0)."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EquipmentUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Individual serialized ASSET instance tracked by unique serial_number (Eqp Sl.No)."""

    __tablename__ = "equipment_units"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "serial_number",
            name="uq_equipment_units_org_serial",
        ),
        CheckConstraint(
            "status IN ('AVAILABLE', 'IN_USE', 'REPLENISHMENT', 'DAMAGED', 'RETIRED')",
            name=conv("ck_equipment_units_status"),
        ),
        CheckConstraint(
            "condition_status IN ('GOOD', 'NEEDS_SERVICE', 'DAMAGED')",
            name=conv("ck_equipment_units_condition_status"),
        ),
        CheckConstraint(
            "(status = 'IN_USE' AND current_project_id IS NOT NULL) "
            "OR (status <> 'IN_USE' AND current_project_id IS NULL)",
            name=conv("ck_equipment_units_project_custody"),
        ),
        Index("idx_equip_units_org_status", "organization_id", "status", "item_id"),
        Index(
            "idx_equip_units_current_project",
            "organization_id",
            "current_project_id",
            postgresql_where=text("current_project_id IS NOT NULL"),
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
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="AVAILABLE",
        server_default=text("'AVAILABLE'"),
    )
    condition_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="GOOD",
        server_default=text("'GOOD'"),
    )
    current_project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
