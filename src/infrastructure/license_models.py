"""Server licensing persistence. Tokens remain authoritative over indexed metadata."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, JSON, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.models import Base, TimestampMixin


class FeatureLicenseGrantModel(TimestampMixin, Base):
    __tablename__ = "feature_license_grants"
    __table_args__ = (
        CheckConstraint("NOT active OR revoked_at IS NULL", name="ck_license_active_not_revoked"),
        CheckConstraint("issued_at >= 0 AND issued_at <= not_before AND not_before < expires_at AND expires_at <= 253402300799",
                        name="ck_license_dates"),
        Index("uq_feature_license_active_subject", "workspace_id", "user_id", unique=True,
              postgresql_where=text("active"), sqlite_where=text("active = 1")),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    license_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    installation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    not_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    features: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))


class LicenseClockStateModel(Base):
    __tablename__ = "license_clock_state"
    __table_args__ = (CheckConstraint("maximum_epoch BETWEEN 0 AND 253402300799", name="ck_license_clock_epoch"),)
    installation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    maximum_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
