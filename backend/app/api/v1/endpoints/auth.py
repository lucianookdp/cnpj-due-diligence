from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, hash_password, verify_password_timing_safe
from app.repositories import user_repository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut

router = APIRouter()


@router.post(
    "/auth/register",
    response_model=TokenOut,
    status_code=201,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    if user_repository.get_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    user = user_repository.create(db, payload.email, hash_password(payload.password))
    token = create_access_token(
        str(user.id), settings.secret_key, settings.access_token_expire_minutes
    )
    return TokenOut(access_token=token)


@router.post(
    "/auth/login",
    response_model=TokenOut,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))],
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    user = user_repository.get_by_email(db, payload.email)
    password_ok = verify_password_timing_safe(
        payload.password, user.hashed_password if user else None
    )
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token = create_access_token(
        str(user.id), settings.secret_key, settings.access_token_expire_minutes
    )
    return TokenOut(access_token=token)
