import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.partnership import Partnership


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True)

    razao_social: Mapped[str] = mapped_column(String(255))
    nome_fantasia: Mapped[str | None] = mapped_column(String(255), nullable=True)

    situacao_cadastral: Mapped[str] = mapped_column(String(50))
    situacao_cadastral_data: Mapped[date | None] = mapped_column(nullable=True)

    data_abertura: Mapped[date | None] = mapped_column(nullable=True)
    capital_social: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    natureza_juridica_codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    natureza_juridica_descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    porte: Mapped[str | None] = mapped_column(String(50), nullable=True)

    cnae_principal_codigo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cnae_principal_descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)

    logradouro: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complemento: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(255), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Normalized (cep + numero) so Phase 2's shared-address detection is a plain GROUP BY.
    address_key: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)

    source_provider: Mapped[str] = mapped_column(String(20))
    source_collected_at: Mapped[datetime] = mapped_column()
    raw_response: Mapped[dict] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    cnaes_secundarios: Mapped[list["CnaeSecundario"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    partnerships: Mapped[list["Partnership"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CnaeSecundario(Base):
    __tablename__ = "cnae_secundarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column(String(10))
    descricao: Mapped[str] = mapped_column(String(255))

    company: Mapped["Company"] = relationship(back_populates="cnaes_secundarios")
