"""Shared FastAPI dependencies and the Jinja environment."""

from datetime import date
from pathlib import Path

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import current_user  # noqa: F401  (re-exported for the routers)
from app.calc.targets import Targets
from app.db import get_db
from app.models import User
from app.services import targets_for

templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

_DAYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
_MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def fmt_num(value: float, decimals: int = 1) -> str:
    """519.4 → '519.4', 100.0 → '100'. Dot as decimal separator, as in inputs."""
    s = f"{value:.{decimals}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def fmt_date(value) -> str:
    """Short Italian date: 'lun 5 ott 2026'."""
    return f"{_DAYS[value.weekday()]} {value.day} {_MONTHS[value.month - 1]} {value.year}"


def fmt_datetime(value) -> str:
    """Short Italian date and time: 'lun 5 ott 2026, 13:30'."""
    return f"{fmt_date(value)}, {value:%H:%M}"


from app.measures import measures_for  # noqa: E402

templates.env.globals["measures"] = lambda food: measures_for(food.name, food.synonyms, food.category)
templates.env.filters["num"] = fmt_num
templates.env.filters["d"] = fmt_date
templates.env.filters["time"] = lambda value: f"{value:%H:%M}"
templates.env.filters["dt"] = fmt_datetime


class ProfileRequired(Exception):
    """Raised when targets are needed but the profile is not filled in yet."""


def current_targets(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Targets:
    targets = targets_for(db, user, date.today())
    if targets is None:
        raise ProfileRequired()
    return targets
