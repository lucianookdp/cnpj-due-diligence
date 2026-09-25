import csv
import gzip
import io
import re

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import FederalDebt

# A real quarter has hundreds of thousands of companies. A summary far below
# this is a broken download, and importing it would silently clear the table.
MIN_ROWS = 1_000
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024
_ROOT = re.compile(r"^\d{8}$")
_BATCH = 5_000


class InvalidSummaryError(Exception):
    pass


def parse_summary(gz_bytes: bytes) -> tuple[str, list[dict]]:
    """The reference line and validated rows of a pgfn_file summary."""
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(gz_bytes)) as fh:
            # Read one byte past the cap: a small upload must not be allowed
            # to inflate into gigabytes of memory.
            raw = fh.read(MAX_DECOMPRESSED_BYTES + 1)
        text = raw.decode("utf-8")
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        raise InvalidSummaryError("arquivo não é um resumo gzip válido") from exc
    if len(raw) > MAX_DECOMPRESSED_BYTES:
        raise InvalidSummaryError("resumo grande demais")
    lines = text.splitlines()
    if not lines or not re.fullmatch(r"# \d{4}_trimestre_\d{2}", lines[0]):
        raise InvalidSummaryError("referência ausente")
    reference = lines[0][2:]
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])))
    rows = []
    for record in reader:
        root = record.get("cnpj_root", "")
        try:
            amount = int(record["amount_cents"])
            count = int(record["inscriptions"])
            judicial_flag = record["judicial"]
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidSummaryError(f"linha inválida: {record}") from exc
        if not _ROOT.match(root) or amount < 0 or count < 1 or judicial_flag not in ("0", "1"):
            raise InvalidSummaryError(f"linha inválida: {record}")
        rows.append(
            {
                "cnpj_root": root,
                "amount_cents": amount,
                "inscriptions": count,
                "judicial": judicial_flag == "1",
                "reference": reference,
            }
        )
    if len(rows) < MIN_ROWS:
        raise InvalidSummaryError(f"só {len(rows)} empresas; esperado pelo menos {MIN_ROWS}")
    return reference, rows


def replace_all(db: Session, rows: list[dict]) -> int:
    """Swaps the whole table in one transaction: readers see the old quarter
    or the new one, never a half-loaded mix."""
    db.execute(delete(FederalDebt))
    for start in range(0, len(rows), _BATCH):
        db.execute(FederalDebt.__table__.insert(), rows[start : start + _BATCH])
    db.commit()
    return len(rows)


def status(db: Session) -> dict:
    reference = db.execute(select(FederalDebt.reference).limit(1)).scalar()
    companies = db.execute(select(func.count()).select_from(FederalDebt)).scalar_one()
    return {"reference": reference, "companies": companies}
