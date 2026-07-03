import uuid
from datetime import datetime

from sqlalchemy import Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OECDIndicatorCatalog(Base):
    __tablename__ = "oecd_indicators_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator_code: Mapped[str] = mapped_column(nullable=False)
    indicator_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(nullable=False)
    expected_unit: Mapped[str | None] = mapped_column(nullable=True)
    marketmind_dimension: Mapped[str | None] = mapped_column(nullable=True)
    dataflow_id: Mapped[str | None] = mapped_column(nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_oecd_indicators_catalog_indicator_code", "indicator_code"),
        Index("ix_oecd_indicators_catalog_category", "category"),
        Index("ix_oecd_indicators_catalog_marketmind_dimension", "marketmind_dimension"),
        Index("ix_oecd_indicators_catalog_is_active", "is_active"),
    )
