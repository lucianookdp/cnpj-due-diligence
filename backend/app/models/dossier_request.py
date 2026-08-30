import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class DossierRequest(Base):
    """One row per user query.

    expected_activity_description is captured now (Phase 1) even though it is
    only consumed by Phase 4's CNAE-mismatch rule, so that rule doesn't need a
    later migration.
    """

    __tablename__ = "dossier_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    root_cnpj: Mapped[str] = mapped_column(String(14), index=True)
    expected_activity_description: Mapped[str | None] = mapped_column(nullable=True)
    graph_depth: Mapped[int] = mapped_column(default=2)
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now())
