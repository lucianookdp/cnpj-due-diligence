import uuid
from datetime import date, datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class RestrictiveListEntry(Base):
    """One sanctioned entity from a single restrictive list.

    (list_type, external_id) is the idempotency key for ingestion: re-running
    the ingestor updates existing rows in place rather than duplicating them.
    external_id is the source's own record id (the API's numeric `id` for
    CEIS/CNEP/CEPIM/leniência, the PDF row number for trabalho_escravo).
    """

    __tablename__ = "restrictive_list_entries"
    __table_args__ = (
        UniqueConstraint("list_type", "external_id", name="uq_restrictive_list_entry_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_type: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[str] = mapped_column(String(100))

    document: Mapped[str] = mapped_column(String(14), index=True)
    document_type: Mapped[str] = mapped_column(String(4))
    name: Mapped[str] = mapped_column(String(255))

    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sanction_start_date: Mapped[date | None] = mapped_column(nullable=True)
    sanction_end_date: Mapped[date | None] = mapped_column(nullable=True)

    raw_data: Mapped[dict] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
