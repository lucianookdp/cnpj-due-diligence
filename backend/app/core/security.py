from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

_ALGORITHM = "HS256"

# Fixed bcrypt hash of an arbitrary password, used only to burn the same CPU
# time a real check would take when no user exists — bcrypt.checkpw against a
# real hash isn't fast, so skipping it for unknown emails would let an
# attacker enumerate registered emails purely by response timing.
_DUMMY_HASH = "$2b$12$hJemxaWuyy7gQUjEsbSbYOIhjWD7MdUy9zLdgbe9Sj3OWwbBdXPaC"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password_timing_safe(password: str, hashed_password: str | None) -> bool:
    """Runs bcrypt.checkpw even when hashed_password is None (no such user).

    bcrypt.checkpw is deliberately slow; skipping it for unknown emails would
    make login responses measurably faster for emails that aren't registered,
    letting an attacker enumerate valid accounts by timing alone.
    """
    return bcrypt.checkpw(password.encode(), (hashed_password or _DUMMY_HASH).encode())


def create_access_token(user_id: str, secret_key: str, expires_minutes: int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> str | None:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
