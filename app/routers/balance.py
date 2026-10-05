"""The daily balance: four bars, the day's meals, activity and the weekly trend."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.calc.activity import MET_TABLE
from app.calc.balance import assess
from app.calc.trend import weekly_trend
from app.db import get_db
from app.deps import ProfileRequired, current_user, templates
from app.models import User
from app.mood import mood_for
from app.phrases import phrase
from app.plan_service import suggestions_for
from app.routers.presets import user_presets
from app.services import day_meals, day_workouts, meals_totals, targets_for, week_days

router = APIRouter()


def _render(request: Request, db: Session, user: User, day: date):
    targets = targets_for(db, user, day)
    if targets is None:
        raise ProfileRequired()
    meals = day_meals(db, user, day)
    workouts = day_workouts(db, user, day)
    extra = sum(w.kcal_burned for w in workouts)
    today = date.today()
    ctx = {
        # The mascot, the line and the milestones belong to today; other days just show the numbers.
        "mood": mood_for(db, user, day) if day == today else None,
        "empty_line": phrase("empty_today" if day == today else "empty_past", f"{day}:{user.id}"),
        "day": day,
        "today": today,
        "prev_day": day - timedelta(days=1),
        "next_day": day + timedelta(days=1),
        "meals": meals,
        "workouts": workouts,
        "activity_kcal": extra,
        "met": MET_TABLE,
        "balance": assess(meals_totals(meals), targets, extra_kcal=extra),
        "targets": targets,
        "trend": weekly_trend(week_days(db, user, day)),
        "presets": user_presets(db, user),
        "suggestions": suggestions_for(db, user, day, {m.meal_type for m in meals}),
    }
    # HTMX day navigation swaps only the balance block.
    name = "partials/balance.html" if request.headers.get("HX-Request") else "balance/day.html"
    return templates.TemplateResponse(request, name, ctx)


@router.get("/")
def oggi(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _render(request, db, user, date.today())


@router.get("/giorno/{day}")
def giorno(
    request: Request, day: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(404)
    return _render(request, db, user, parsed)
