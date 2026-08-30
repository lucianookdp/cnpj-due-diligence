import uuid

from sqlalchemy.orm import Session

from app.models import WatchlistEntry


def list_for_user(db: Session, user_id: uuid.UUID) -> list[WatchlistEntry]:
    return (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.user_id == user_id)
        .order_by(WatchlistEntry.created_at.desc())
        .all()
    )


def get(db: Session, entry_id: uuid.UUID, user_id: uuid.UUID) -> WatchlistEntry | None:
    return (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.id == entry_id, WatchlistEntry.user_id == user_id)
        .one_or_none()
    )


def get_by_cnpj(db: Session, user_id: uuid.UUID, cnpj: str) -> WatchlistEntry | None:
    return (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.user_id == user_id, WatchlistEntry.cnpj == cnpj)
        .one_or_none()
    )


def create(db: Session, user_id: uuid.UUID, cnpj: str, label: str | None) -> WatchlistEntry:
    entry = WatchlistEntry(user_id=user_id, cnpj=cnpj, label=label)
    db.add(entry)
    db.commit()
    return entry


def delete(db: Session, entry: WatchlistEntry) -> None:
    db.delete(entry)
    db.commit()


def distinct_watched_cnpjs(db: Session) -> list[str]:
    return [row[0] for row in db.query(WatchlistEntry.cnpj).distinct().all()]
