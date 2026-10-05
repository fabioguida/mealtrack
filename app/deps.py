"""Shared FastAPI dependencies.

`current_user` is a placeholder until phase 4 (authentication): every request
acts as the seeded first user. Phase 4 replaces this function; routes keep
depending on it unchanged.
"""

from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

_DAYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
_MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def fmt_num(value: float, decimals: int = 1) -> str:
    """519.4 → '519.4', 100.0 → '100'. Dot as decimal separator, as in inputs."""
    s = f"{value:.{decimals}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def fmt_datetime(value) -> str:
    """Short Italian date: 'lun 5 ott 2026, 13:30'."""
    return (
        f"{_DAYS[value.weekday()]} {value.day} {_MONTHS[value.month - 1]} "
        f"{value.year}, {value:%H:%M}"
    )


templates.env.filters["num"] = fmt_num
templates.env.filters["dt"] = fmt_datetime


def current_user(db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).order_by(User.id).limit(1))
    if user is None:
        raise HTTPException(500, "Nessun utente: esegui scripts/init_db.py")
    return user
