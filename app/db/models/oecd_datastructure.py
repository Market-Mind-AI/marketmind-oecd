import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OECDDatastructure(Base):
    __tablename__ = "oecd_datastructures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oecd_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oecd_requests.id"), nullable=False
    )
    dataflow_id: Mapped[str | None] = mapped_column(nullable=True)
    structure_id: Mapped[str | None] = mapped_column(nullable=True)
    dimension_id: Mapped[str | None] = mapped_column(nullable=True)
    dimension_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimension_position: Mapped[int | None] = mapped_column(nullable=True)
    code_id: Mapped[str | None] = mapped_column(nullable=True)
    code_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[assignment]
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_oecd_datastructures_dataflow_id", "dataflow_id"),
        Index("ix_oecd_datastructures_structure_id", "structure_id"),
        Index("ix_oecd_datastructures_dimension_id", "dimension_id"),
        Index("ix_oecd_datastructures_code_id", "code_id"),
    )
