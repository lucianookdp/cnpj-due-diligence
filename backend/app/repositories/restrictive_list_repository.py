from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import RestrictiveListEntry


@dataclass
class RawRestrictiveListEntry:
    list_type: str
    external_id: str
    document: str
    document_type: str
    name: str
    reason: str | None
    source_org: str | None
    sanction_start_date: date | None
    sanction_end_date: date | None
    raw_data: dict


def upsert_entry(db: Session, entry: RawRestrictiveListEntry) -> RestrictiveListEntry:
    row = (
        db.query(RestrictiveListEntry)
        .filter(
            RestrictiveListEntry.list_type == entry.list_type,
            RestrictiveListEntry.external_id == entry.external_id,
        )
        .one_or_none()
    )
    if row is None:
        row = RestrictiveListEntry(list_type=entry.list_type, external_id=entry.external_id)
        db.add(row)

    row.document = entry.document
    row.document_type = entry.document_type
    row.name = entry.name
    row.reason = entry.reason
    row.source_org = entry.source_org
    row.sanction_start_date = entry.sanction_start_date
    row.sanction_end_date = entry.sanction_end_date
    row.raw_data = entry.raw_data
    db.flush()
    return row


def find_by_document(db: Session, document: str) -> list[RestrictiveListEntry]:
    return db.query(RestrictiveListEntry).filter(RestrictiveListEntry.document == document).all()
