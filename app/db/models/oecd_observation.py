import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OECDObservation(Base):
    __tablename__ = "oecd_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oecd_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oecd_requests.id"), nullable=False
    )
    dataset_id: Mapped[str | None] = mapped_column(nullable=True)
    dataflow_id: Mapped[str | None] = mapped_column(nullable=True)
    country: Mapped[str] = mapped_column(nullable=False)
    indicator_code: Mapped[str] = mapped_column(nullable=False)
    indicator_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    measure: Mapped[str | None] = mapped_column(nullable=True)
    unit: Mapped[str | None] = mapped_column(nullable=True)
    frequency: Mapped[str | None] = mapped_column(nullable=True)
    time_period: Mapped[str] = mapped_column(nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_oecd_observations_oecd_request_id", "oecd_request_id"),
        Index("ix_oecd_observations_dataset_id", "dataset_id"),
        Index("ix_oecd_observations_dataflow_id", "dataflow_id"),
        Index("ix_oecd_observations_country", "country"),
        Index("ix_oecd_observations_indicator_code", "indicator_code"),
        Index("ix_oecd_observations_time_period", "time_period"),
        Index("ix_oecd_observations_series", "country", "indicator_code", "time_period"),
    )
