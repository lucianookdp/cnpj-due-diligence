import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.partnership import Partnership


class Person(Base):
    """A sócio/administrador as disclosed by Receita Federal — never a standalone search target.

    Identity key (cpf_masked, nome) is best-effort: Receita masks the CPF, so two
    distinct people sharing a name and masking pattern can collide onto one row.
    Accepted given the source never exposes the full CPF.
    """

    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("cpf_masked", "nome", name="uq_people_cpf_masked_nome"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpf_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nome: Mapped[str] = mapped_column(String(255))
    faixa_etaria: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Opaque id from grafo.minhareceita.org, learned the first time a company this
    # person is linked to gets graph-expanded. Powers the reverse (person -> other
    # companies) lookup — Minha Receita/BrasilAPI's plain CNPJ endpoints can't do that.
    graph_ref_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    partnerships: Mapped[list["Partnership"]] = relationship(back_populates="person")
