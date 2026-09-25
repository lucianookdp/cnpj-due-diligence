from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FederalDebt(Base):
    """A company's federal debt being actively collected by PGFN, summed over
    its inscriptions. One row per company root (first 8 CNPJ digits), only
    above the build threshold, replaced wholesale each quarter — so the table
    stays a compact lookup, not a copy of PGFN's multi-gigabyte dataset.
    """

    __tablename__ = "federal_debts"

    cnpj_root: Mapped[str] = mapped_column(String(8), primary_key=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    inscriptions: Mapped[int] = mapped_column(Integer)
    judicial: Mapped[bool] = mapped_column(Boolean)
    # PGFN quarter the row came from, e.g. "2026_trimestre_02".
    reference: Mapped[str] = mapped_column(String(20))
