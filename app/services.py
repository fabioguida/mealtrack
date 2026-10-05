"""Queries that several routers share: current weight and daily targets."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calc.targets import Targets, daily_targets
from app.models import Profile, User, Weight


def current_weight(db: Session, user: User, day: date | None = None) -> float | None:
    """The latest weigh-in on or before `day` (default: the latest ever)."""
    stmt = select(Weight).where(Weight.user_id == user.id)
    if day is not None:
        stmt = stmt.where(Weight.date <= day)
    row = db.scalar(stmt.order_by(Weight.date.desc()).limit(1))
    if row is None and day is not None:
        # Nothing before that day: fall back to the earliest weigh-in.
        row = db.scalar(
            select(Weight).where(Weight.user_id == user.id).order_by(Weight.date).limit(1)
        )
    return row.kg if row else None


def targets_for(db: Session, user: User, day: date | None = None) -> Targets | None:
    """Daily targets for `day`, or None until the profile and a weight exist."""
    profile = db.get(Profile, user.id)
    weight = current_weight(db, user, day)
    if profile is None or weight is None:
        return None
    deficit = profile.deficit_kcal if profile.goal == "dimagrire" else 0.0
    return daily_targets(
        profile.sex,
        profile.age,
        profile.height_cm,
        weight,
        profile.activity,
        deficit,
        profile.protein_g_per_kg,
    )
