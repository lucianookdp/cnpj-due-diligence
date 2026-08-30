import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Alert(Base):
    """One detected change on a monitored company.

    Scoped to the company, not to a specific watcher: several users can watch
    the same CNPJ, and the event ("situação mudou") is a fact about the
    company, not about any one watchlist entry.
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    alert_type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(500))
    detected_at: Mapped[datetime] = mapped_column(server_default=func.now())
