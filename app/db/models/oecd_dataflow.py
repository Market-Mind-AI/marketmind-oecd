import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OECDDataflow(Base):
    __tablename__ = "oecd_dataflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oecd_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oecd_requests.id"), nullable=False
    )
    agency_id: Mapped[str | None] = mapped_column(nullable=True)
    dataflow_id: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(nullable=True)
    is_final: Mapped[bool | None] = mapped_column(nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_oecd_dataflows_dataflow_id", "dataflow_id"),
        Index("ix_oecd_dataflows_agency_id", "agency_id"),
    )
