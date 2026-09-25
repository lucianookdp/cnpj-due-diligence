import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class BatchCheck(Base):
    """A user's list of CNPJs checked in one go (e.g. every supplier).

    Only the CNPJs travel to the server — the user's spreadsheet is read in
    the browser — and batches are deleted after BATCH_RETENTION_DAYS, so the
    table stays small no matter how long the app runs.
    """

    __tablename__ = "batch_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # processing | done | interrupted
    status: Mapped[str] = mapped_column(String(20), default="processing")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    items: Mapped[list["BatchCheckItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="BatchCheckItem.position"
    )


class BatchCheckItem(Base):
    """One CNPJ's outcome: the score and the rules that fired, not the full dossier."""

    __tablename__ = "batch_check_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("batch_checks.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    cnpj: Mapped[str] = mapped_column(String(14))
    # pending | done | not_found | error
    status: Mapped[str] = mapped_column(String(20), default="pending")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    razao_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    situacao_cadastral: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Labels of the rules that fired, e.g. ["Empresa aberta há menos de 6 meses"].
    flags: Mapped[list] = mapped_column(JSONB, default=list)

    batch: Mapped[BatchCheck] = relationship(back_populates="items")
