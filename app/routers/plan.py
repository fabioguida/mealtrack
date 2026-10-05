"""The meal plan, the eating schedule and the food preferences."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calc.nutrition import item_values
from app.db import get_db
from app.deps import ProfileRequired, current_user, templates
from app.models import MEAL_TYPES, EatingSchedule, Food, FoodPreference, Meal, MealItem, User
from app.plan_service import (
    CATEGORIES,
    SCHEMES,
    apply_scheme,
    current_plan,
    generate_plan,
    plan_days,
    plan_is_stale,
    preferences_for,
    schedule_for,
    template_dishes,
)
from app.routers.foods import visible_foods
from app.services import targets_for

router = APIRouter()

DAY_NAMES = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


# --- the plan ------------------------------------------------------------------

@router.get("/piano")
def piano(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = current_plan(db, user)
    _, skipped = template_dishes(db)
    return templates.TemplateResponse(
        request,
        "plan/show.html",
        {
            "plan": plan,
            "days": plan_days(plan) if plan else [],
            "stale": plan_is_stale(db, user, plan) if plan else False,
            "targets": targets_for(db, user, date.today()),
            "skipped": skipped,
            "today": date.today(),
            "schemes": SCHEMES,
            "has_schedule": db.scalar(select(EatingSchedule).where(EatingSchedule.user_id == user.id)) is not None,
        },
    )


@router.post("/piano/schema")
def schema(
    scheme: Annotated[str, Form()],
    weekend_out: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Pick an eating scheme (e.g. intermittent fasting), then generate the plan."""
    if scheme not in SCHEMES:
        raise HTTPException(404)
    apply_scheme(db, user, scheme, weekend_out=bool(weekend_out))
    if generate_plan(db, user, date.today(), weeks=2) is None:
        raise ProfileRequired()
    return RedirectResponse("/piano", status_code=303)


@router.post("/piano/rigenera")
def rigenera(db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = generate_plan(db, user, date.today(), weeks=2)
    if plan is None:
        raise ProfileRequired()
    return RedirectResponse("/piano", status_code=303)


@router.post("/piano/conferma")
def conferma(
    giorno: Annotated[str, Form()],
    pasto: Annotated[str, Form()],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Log the planned meal of (day, type) as a real meal, then open it to correct."""
    try:
        day = date.fromisoformat(giorno)
    except ValueError:
        raise HTTPException(404)
    plan = current_plan(db, user)
    if plan is None or pasto not in MEAL_TYPES:
        raise HTTPException(404)
    rows = [i for i in plan.items if i.date == day and i.meal_type == pasto]
    if not rows:
        raise HTTPException(404)
    sched = {r.meal_type: r for r in schedule_for(db, user).get(day.weekday(), [])}
    hhmm = (sched[pasto].time if pasto in sched and sched[pasto].time else "12:00")
    when = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time())
    meal = Meal(user_id=user.id, datetime=when, meal_type=pasto, input_method="plan")
    for r in rows:
        v = item_values(r.food, r.grams)
        meal.items.append(MealItem(food=r.food, grams=r.grams, kcal=v.kcal, protein_g=v.protein_g, carbs_g=v.carbs_g, fat_g=v.fat_g))
    db.add(meal)
    db.commit()
    return RedirectResponse(f"/pasti/{meal.id}/modifica", status_code=303)


# --- the eating schedule --------------------------------------------------------

@router.get("/orari")
def orari(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    schedule = schedule_for(db, user)
    grid = {dow: {r.meal_type: r for r in schedule.get(dow, [])} for dow in range(7)}
    return templates.TemplateResponse(
        request, "plan/schedule.html",
        {"grid": grid, "day_names": DAY_NAMES, "meal_types": MEAL_TYPES, "errors": []},
    )


@router.post("/orari")
async def salva_orari(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    form = await request.form()
    errors, rows = [], []
    for dow in range(7):
        total = 0.0
        for mt in MEAL_TYPES:
            if not form.get(f"eat_{dow}_{mt}"):
                continue
            try:
                share = float(form.get(f"share_{dow}_{mt}", "0") or 0) / 100
            except ValueError:
                share = -1
            time = (form.get(f"time_{dow}_{mt}") or "").strip() or None
            if time:
                try:
                    datetime.strptime(time, "%H:%M")
                except ValueError:
                    errors.append(f"{DAY_NAMES[dow]}, {mt}: orario non valido.")
            if not 0 < share <= 1:
                errors.append(f"{DAY_NAMES[dow]}, {mt}: quota non valida (1–100 %).")
            total += share
            rows.append(EatingSchedule(user_id=user.id, day_of_week=dow, meal_type=mt, time=time, share=share))
        if total > 1.0001:
            errors.append(f"{DAY_NAMES[dow]}: le quote superano il 100 %.")
    if errors:
        grid = {dow: {} for dow in range(7)}
        for r in rows:
            grid[r.day_of_week][r.meal_type] = r
        return templates.TemplateResponse(
            request, "plan/schedule.html",
            {"grid": grid, "day_names": DAY_NAMES, "meal_types": MEAL_TYPES, "errors": errors},
            status_code=422,
        )
    for old in db.scalars(select(EatingSchedule).where(EatingSchedule.user_id == user.id)):
        db.delete(old)
    db.flush()  # deletes first, or the new rows hit the unique constraint
    db.add_all(rows)
    db.commit()
    return RedirectResponse("/piano", status_code=303)


# --- the preferences -------------------------------------------------------------

def _pref_context(db, user):
    prefs = preferences_for(db, user)
    foods = db.scalars(
        select(FoodPreference).where(FoodPreference.user_id == user.id, FoodPreference.food_id.is_not(None))
    ).all()
    return {
        "categories": CATEGORIES,
        "cat_kind": {c: ("like" if c in prefs.like_categories else "avoid" if c in prefs.avoid_categories else "") for c in CATEGORIES},
        "food_prefs": foods,
    }


@router.get("/preferenze")
def preferenze(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return templates.TemplateResponse(request, "plan/preferences.html", _pref_context(db, user))


@router.post("/preferenze")
async def salva_preferenze(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    form = await request.form()
    for old in db.scalars(
        select(FoodPreference).where(FoodPreference.user_id == user.id, FoodPreference.category.is_not(None))
    ):
        db.delete(old)
    for c in CATEGORIES:
        kind = form.get(f"cat_{c}", "")
        if kind in ("like", "avoid"):
            db.add(FoodPreference(user_id=user.id, category=c, kind=kind))
    db.commit()
    return RedirectResponse("/preferenze", status_code=303)


@router.post("/preferenze/alimento/{food_id}/{kind}")
def pref_alimento(food_id: int, kind: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if kind not in ("like", "avoid") or db.scalar(visible_foods(user).where(Food.id == food_id)) is None:
        raise HTTPException(404)
    existing = db.scalar(
        select(FoodPreference).where(FoodPreference.user_id == user.id, FoodPreference.food_id == food_id)
    )
    if existing:
        existing.kind = kind
    else:
        db.add(FoodPreference(user_id=user.id, food_id=food_id, kind=kind))
    db.commit()
    return RedirectResponse("/preferenze", status_code=303)


@router.post("/preferenze/{pref_id}/elimina")
def elimina_pref(pref_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(FoodPreference).where(FoodPreference.id == pref_id, FoodPreference.user_id == user.id))
    if row is None:
        raise HTTPException(404)
    db.delete(row)
    db.commit()
    return RedirectResponse("/preferenze", status_code=303)
