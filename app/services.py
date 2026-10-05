"""Queries that several routers share: weight, targets, a day's meals and activity."""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.nutrition import Totals
from app.calc.targets import Targets, daily_targets, deficit_for, protein_g_per_kg_for
from app.models import Meal, MealItem, Profile, User, Weight, Workout


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
    pace = profile.pace
    return daily_targets(
        profile.sex,
        profile.age,
        profile.height_cm,
        weight,
        profile.activity,
        deficit_for(pace),
        protein_g_per_kg_for(pace),
    )


LIBRARY_SAMPLE = 5


def usual_grams(db: Session, user: User, food_id: int) -> float | None:
    """The personal library: the median of the user's last five portions of a
    food, or None if they never logged it. No model is trained (HANDOVER.md 4.3)."""
    grams = db.scalars(
        select(MealItem.grams)
        .join(Meal, Meal.id == MealItem.meal_id)
        .where(Meal.user_id == user.id, MealItem.food_id == food_id)
        .order_by(Meal.datetime.desc(), MealItem.id.desc())
        .limit(LIBRARY_SAMPLE)
    ).all()
    if not grams:
        return None
    s = sorted(grams)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def meal_type_for(when: datetime) -> str:
    """Default meal type from the hour of day."""
    h = when.hour
    return "colazione" if h < 11 else "pranzo" if h < 15 else "spezzafame" if h < 18 else "cena"


def day_meals(db: Session, user: User, day: date) -> list[Meal]:
    start = datetime.combine(day, datetime.min.time())
    return db.scalars(
        select(Meal)
        .options(selectinload(Meal.items))
        .where(
            Meal.user_id == user.id,
            Meal.datetime >= start,
            Meal.datetime < start + timedelta(days=1),
        )
        .order_by(Meal.datetime)
    ).all()


def meals_totals(meals: list[Meal]) -> Totals:
    total = Totals()
    for m in meals:
        for i in m.items:
            total = total + Totals(i.kcal, i.protein_g, i.carbs_g, i.fat_g)
    return total


def day_workouts(db: Session, user: User, day: date) -> list[Workout]:
    return db.scalars(
        select(Workout).where(Workout.user_id == user.id, Workout.date == day).order_by(Workout.id)
    ).all()


def activity_kcal(db: Session, user: User, day: date) -> float:
    return sum(w.kcal_burned for w in day_workouts(db, user, day))


def week_days(db: Session, user: User, end: date, days: int = 7) -> list[tuple[float | None, float]]:
    """(kcal eaten or None, kcal allowed) for the `days` days ending at `end`."""
    out = []
    for offset in range(days - 1, -1, -1):
        day = end - timedelta(days=offset)
        meals = day_meals(db, user, day)
        targets = targets_for(db, user, day)
        allowed = (targets.kcal if targets else 0.0) + activity_kcal(db, user, day)
        out.append((meals_totals(meals).kcal if meals else None, allowed))
    return out
