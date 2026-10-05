"""Password hashing (argon2) and the signed session cookie."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import COOKIE_SECURE, SECRET_KEY, SESSION_DAYS
from app.db import get_db
from app.models import User

COOKIE = "session"
_hasher = PasswordHasher()
_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="session")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def make_session(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def read_session(token: str | None) -> int | None:
    if not token:
        return None
    try:
        return int(_serializer.loads(token, max_age=SESSION_DAYS * 86400)["uid"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


def set_session(response: Response, user: User) -> None:
    response.set_cookie(
        COOKIE,
        make_session(user.id),
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE)


class LoginRequired(Exception):
    """Raised by `current_user`; the app turns it into a redirect to /accedi."""


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = read_session(request.cookies.get(COOKIE))
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise LoginRequired()
    request.state.user = user
    return user
