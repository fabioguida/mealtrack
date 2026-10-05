"""The daily balance: four bars and the day's meals. Home page of the app."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.balance import assess
from app.calc.nutrition import Totals
from app.calc.targets import Targets
from app.db import get_db
from app.deps import current_targets, current_user, templates
from app.models import Meal, User

router = APIRouter()


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


def day_totals(meals: list[Meal]) -> Totals:
    total = Totals()
    for m in meals:
        for i in m.items:
            total = total + Totals(i.kcal, i.protein_g, i.carbs_g, i.fat_g)
    return total


def _render(request: Request, db: Session, user: User, targets: Targets, day: date):
    meals = day_meals(db, user, day)
    ctx = {
        "day": day,
        "today": date.today(),
        "prev_day": day - timedelta(days=1),
        "next_day": day + timedelta(days=1),
        "meals": meals,
        "balance": assess(day_totals(meals), targets),
        "targets": targets,
    }
    # HTMX day navigation swaps only the balance block.
    name = "partials/balance.html" if request.headers.get("HX-Request") else "balance/day.html"
    return templates.TemplateResponse(request, name, ctx)


@router.get("/")
def oggi(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    targets: Targets = Depends(current_targets),
):
    return _render(request, db, user, targets, date.today())


@router.get("/giorno/{day}")
def giorno(
    request: Request,
    day: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    targets: Targets = Depends(current_targets),
):
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(404)
    return _render(request, db, user, targets, parsed)
