import uuid

from sqlalchemy.orm import Session

from app.models import Alert


def create(db: Session, company_id: uuid.UUID, alert_type: str, message: str) -> Alert:
    alert = Alert(company_id=company_id, alert_type=alert_type, message=message)
    db.add(alert)
    db.flush()
    return alert


def list_for_company(db: Session, company_id: uuid.UUID) -> list[Alert]:
    return (
        db.query(Alert)
        .filter(Alert.company_id == company_id)
        .order_by(Alert.detected_at.desc())
        .all()
    )
