import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.person import Person


class Partnership(Base):
    """Edge: person -> company (a QSA entry).

    first_seen_at/ended_at accumulate history across sync runs so Phase 4's
    "QSA changed more than twice in 12 months" rule can be computed later
    without a separate audit table.
    """

    __tablename__ = "partnerships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    qualificacao: Mapped[str | None] = mapped_column(String(255), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    person: Mapped["Person"] = relationship(back_populates="partnerships")
    company: Mapped["Company"] = relationship(back_populates="partnerships")


class CompanyPartnership(Base):
    """Edge: company -> company, i.e. one PJ holding equity/qualification in another."""

    __tablename__ = "company_partnerships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    object_company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    qualificacao: Mapped[str | None] = mapped_column(String(255), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
