from sqlalchemy.orm import Session

from app.models import DossierRequest


def create(
    db: Session, root_cnpj: str, expected_activity_description: str | None
) -> DossierRequest:
    row = DossierRequest(
        root_cnpj=root_cnpj, expected_activity_description=expected_activity_description
    )
    db.add(row)
    db.commit()
    return row
