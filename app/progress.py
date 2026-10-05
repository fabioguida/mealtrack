"""The progress summary that goes into the emails (and could go on a page)."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calc.trend import WeekTrend, weekly_trend
from app.models import User, Weight
from app.plan_service import current_plan, plan_days
from app.services import activity_kcal, day_meals, meals_totals, targets_for, week_days


@dataclass(frozen=True)
class DayLine:
    day: date
    eaten_kcal: float | None   # None = nothing logged
    allowed_kcal: float
    protein_g: float
    protein_target_g: float


@dataclass
class ProgressSummary:
    day: date                      # the day reported (yesterday, for the evening mail)
    lines: list[DayLine]           # last 7 days ending at `day`
    trend: WeekTrend
    streak: int                    # consecutive logged days ending at `day`
    weights: list[tuple[date, float]] = field(default_factory=list)  # last five weigh-ins
    tomorrow_meals: list[dict] = field(default_factory=list)

    @property
    def today(self) -> DayLine:
        return self.lines[-1]

    @property
    def weight_delta(self) -> float | None:
        if len(self.weights) < 2:
            return None
        return self.weights[-1][1] - self.weights[0][1]


def streak_days(db: Session, user: User, day: date, limit: int = 60) -> int:
    n = 0
    while n < limit and day_meals(db, user, day - timedelta(days=n)):
        n += 1
    return n


def progress_for(db: Session, user: User, day: date) -> ProgressSummary | None:
    targets = targets_for(db, user, day)
    if targets is None:
        return None
    lines = []
    for offset in range(6, -1, -1):
        d = day - timedelta(days=offset)
        meals = day_meals(db, user, d)
        t = targets_for(db, user, d) or targets
        totals = meals_totals(meals)
        lines.append(DayLine(d, totals.kcal if meals else None, t.kcal + activity_kcal(db, user, d), totals.protein_g, t.protein_g))
    weights = db.scalars(
        select(Weight).where(Weight.user_id == user.id).order_by(Weight.date.desc()).limit(5)
    ).all()
    plan = current_plan(db, user)
    tomorrow = day + timedelta(days=1)
    tomorrow_meals = next((d["meals"] for d in plan_days(plan) if d["day"] == tomorrow), []) if plan else []
    return ProgressSummary(
        day=day,
        lines=lines,
        trend=weekly_trend(week_days(db, user, day)),
        streak=streak_days(db, user, day),
        weights=[(w.date, w.kg) for w in reversed(weights)],
        tomorrow_meals=tomorrow_meals,
    )
