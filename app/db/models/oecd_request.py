import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OECDRequest(Base):
    __tablename__ = "oecd_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(nullable=True)
    dataflow_id: Mapped[str | None] = mapped_column(nullable=True)
    structure_id: Mapped[str | None] = mapped_column(nullable=True)
    country: Mapped[str | None] = mapped_column(nullable=True)
    indicator_code: Mapped[str | None] = mapped_column(nullable=True)
    start_period: Mapped[str | None] = mapped_column(nullable=True)
    end_period: Mapped[str | None] = mapped_column(nullable=True)
    query_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    ingestion_run: Mapped["IngestionRun"] = relationship(back_populates="oecd_requests")  # type: ignore[name-defined]  # noqa: F821

    __table_args__ = (
        Index("ix_oecd_requests_ingestion_run_id", "ingestion_run_id"),
        Index("ix_oecd_requests_endpoint", "endpoint"),
        Index("ix_oecd_requests_dataset_id", "dataset_id"),
        Index("ix_oecd_requests_dataflow_id", "dataflow_id"),
        Index("ix_oecd_requests_country", "country"),
        Index("ix_oecd_requests_indicator_code", "indicator_code"),
    )
