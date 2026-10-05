"""The progress summary that goes into the emails (and could go on a page)."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calc.trend import WeekTrend, weekly_trend
from app.models import Meal, User, Weight
from app.plan_service import current_plan, plan_days
from app.services import activity_kcal, day_meals, meals_totals, targets_for, week_days

STREAK_MILESTONES = (3, 7, 14, 30)
WEIGHT_MILESTONES_KG = (1.0, 2.0, 5.0)


@dataclass(frozen=True)
class DayLine:
    day: date
    eaten_kcal: float | None   # None = nothing logged
    allowed_kcal: float
    protein_g: float
    protein_target_g: float


@dataclass
class ProgressSummary:
    day: date                      # the day reported (today, for the evening mail)
    lines: list[DayLine]           # last 7 days ending at `day`
    trend: WeekTrend
    streak: int                    # consecutive logged days ending at `day`
    days_since_log: int            # 0 = logged today; large = long away
    weights: list[tuple[date, float]] = field(default_factory=list)  # last five weigh-ins
    first_weight: tuple[date, float] | None = None
    tomorrow_meals: list[dict] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)   # phrase keys reached today

    @property
    def today(self) -> DayLine:
        return self.lines[-1]

    @property
    def weight_delta(self) -> float | None:
        if len(self.weights) < 2:
            return None
        return self.weights[-1][1] - self.weights[0][1]

    @property
    def situation(self) -> str:
        """on_target | over | under | no_log, for today's opening line."""
        t = self.today
        if t.eaten_kcal is None:
            return "no_log"
        if t.eaten_kcal > t.allowed_kcal * 1.05:
            return "over"
        if t.eaten_kcal < t.allowed_kcal * 0.80:
            return "under"
        return "on_target"


def streak_days(db: Session, user: User, day: date, limit: int = 60) -> int:
    n = 0
    while n < limit and day_meals(db, user, day - timedelta(days=n)):
        n += 1
    return n


def days_since_last_log(db: Session, user: User, day: date, limit: int = 60) -> int:
    """0 = logged on `day`. A user who has never logged anything is new, not away: 0."""
    end = datetime.combine(day + timedelta(days=1), datetime.min.time())
    last = db.scalar(select(Meal.datetime).where(Meal.user_id == user.id, Meal.datetime < end).order_by(Meal.datetime.desc()).limit(1))
    if last is None:
        return 0
    return min(limit, (day - last.date()).days)


def _milestones(day: date, streak: int, weights: list[Weight], first: Weight | None, trend: WeekTrend, lines: list[DayLine]) -> list[str]:
    out = []
    if streak in STREAK_MILESTONES:
        out.append(f"streak_{streak}")
    # Weight thresholds crossed by a weigh-in made today.
    if first is not None and len(weights) >= 2 and weights[-1].date == day:
        loss_now = first.kg - weights[-1].kg
        loss_before = first.kg - weights[-2].kg
        for kg in WEIGHT_MILESTONES_KG:
            if loss_before < kg <= loss_now:
                out.append(f"weight_{int(kg)}")
    if trend.verdict == "in_linea" and all(l.eaten_kcal is not None for l in lines):
        out.append("week_in_line")
    return out


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
    recent = list(reversed(db.scalars(
        select(Weight).where(Weight.user_id == user.id, Weight.date <= day).order_by(Weight.date.desc()).limit(5)
    ).all()))
    first = db.scalar(select(Weight).where(Weight.user_id == user.id).order_by(Weight.date).limit(1))
    plan = current_plan(db, user)
    tomorrow = day + timedelta(days=1)
    tomorrow_meals = next((d["meals"] for d in plan_days(plan) if d["day"] == tomorrow), []) if plan else []
    trend = weekly_trend(week_days(db, user, day))
    streak = streak_days(db, user, day)
    return ProgressSummary(
        day=day,
        lines=lines,
        trend=trend,
        streak=streak,
        days_since_log=days_since_last_log(db, user, day),
        weights=[(w.date, w.kg) for w in recent],
        first_weight=(first.date, first.kg) if first else None,
        tomorrow_meals=tomorrow_meals,
        milestones=_milestones(day, streak, recent, first, trend, lines),
    )
