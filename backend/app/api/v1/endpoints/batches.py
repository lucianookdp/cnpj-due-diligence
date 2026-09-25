import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.models import BatchCheck, User
from app.schemas.batch import BatchCheckCreate, BatchCheckItemOut, BatchCheckOut
from app.services import batch_check

router = APIRouter()


def _to_out(batch: BatchCheck) -> BatchCheckOut:
    return BatchCheckOut(
        id=batch.id,
        status=batch.status,
        created_at=batch.created_at,
        items=[
            BatchCheckItemOut(
                cnpj=i.cnpj,
                status=i.status,
                score=i.score,
                razao_social=i.razao_social,
                situacao_cadastral=i.situacao_cadastral,
                flags=i.flags or [],
            )
            for i in batch.items
        ],
    )


@router.post(
    "/batches",
    response_model=BatchCheckOut,
    status_code=202,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
)
def create_batch(
    body: BatchCheckCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BatchCheckOut:
    cnpjs = batch_check.clean_cnpjs(body.cnpjs)
    if not cnpjs:
        raise HTTPException(status_code=422, detail="Nenhum CNPJ válido na lista")
    try:
        batch = batch_check.create_batch(db, current_user.id, cnpjs)
    except batch_check.BatchLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    background_tasks.add_task(batch_check.process_batch, batch.id, settings)
    return _to_out(batch)


@router.get("/batches", response_model=list[BatchCheckOut])
def list_batches(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BatchCheckOut]:
    batches = (
        db.query(BatchCheck)
        .filter(BatchCheck.user_id == current_user.id)
        .order_by(BatchCheck.created_at.desc())
        .limit(10)
        .all()
    )
    for batch in batches:
        batch_check.close_if_stalled(db, batch)
    return [_to_out(b) for b in batches]


@router.get("/batches/{batch_id}", response_model=BatchCheckOut)
def read_batch(
    batch_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchCheckOut:
    batch = db.get(BatchCheck, batch_id)
    # Someone else's batch answers exactly like a missing one.
    if batch is None or batch.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Checagem não encontrada")
    batch_check.close_if_stalled(db, batch)
    return _to_out(batch)
