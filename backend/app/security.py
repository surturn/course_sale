import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User

COOKIE_NAME = "access_token"
_hasher = PasswordHasher()  # argon2id by default


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not logged in")
    try:
        user_id = int(jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired, log in again")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Not logged in")
    return user


# ponytail: in-process limiter (per uvicorn worker). Enough to stop password guessing for a
# ~200-user store; move to Redis or the proxy if you run many workers or hosts.
_failures: dict[str, deque] = defaultdict(deque)


def _recent(key: str, window: float) -> deque:
    hits, cutoff = _failures[key], time.monotonic() - window
    while hits and hits[0] < cutoff:
        hits.popleft()
    return hits


def check_throttle(key: str, limit: int, window: float) -> None:
    hits = _recent(key, window)
    if not hits:
        _failures.pop(key, None)  # keep the map from growing with one-off keys
    elif len(hits) >= limit:
        raise HTTPException(429, "Too many attempts. Wait a few minutes and try again.")


def record_failure(key: str) -> None:
    _failures[key].append(time.monotonic())
