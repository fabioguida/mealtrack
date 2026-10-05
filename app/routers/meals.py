"""Manual meal entry: list, create, view, edit, delete, plus HTMX partials."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.nutrition import item_values, meal_totals
from app.db import get_db
from app.deps import current_user, templates
from app.models import INPUT_METHODS, MEAL_TYPES, Food, Meal, MealItem, User
from app.routers.foods import visible_foods

router = APIRouter(prefix="/pasti")


def _own_meal(db: Session, user: User, meal_id: int) -> Meal:
    meal = db.scalar(
        select(Meal)
        .options(selectinload(Meal.items).selectinload(MealItem.food))
        .where(Meal.id == meal_id, Meal.user_id == user.id)
    )
    if meal is None:
        raise HTTPException(404)
    return meal


def _parse_items(
    db: Session, user: User, food_ids: list[int], grams: list[float]
) -> tuple[list[tuple[Food, float]], list[str]]:
    """Pair the form's parallel lists into (food, grams); collect errors."""
    errors: list[str] = []
    if len(food_ids) != len(grams):
        errors.append("Dati del modulo non validi.")
        return [], errors
    foods = {
        f.id: f
        for f in db.scalars(visible_foods(user).where(Food.id.in_(food_ids)))
    }
    items: list[tuple[Food, float]] = []
    for food_id, g in zip(food_ids, grams):
        food = foods.get(food_id)
        if food is None:
            errors.append("Alimento non trovato.")
            continue
        if g <= 0:
            errors.append(f"Grammi non validi per {food.name}.")
            continue
        items.append((food, g))
    if not items and not errors:
        errors.append("Aggiungi almeno un alimento.")
    return items, errors


def _form_context(meal: Meal | None, items, errors, meal_type, when):
    return {
        "meal": meal,
        "items": items,
        "totals": meal_totals(items),
        "errors": errors,
        "meal_types": MEAL_TYPES,
        "meal_type": meal_type,
        "when": when,
    }


@router.get("")
def elenco(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    meals = db.scalars(
        select(Meal)
        .options(selectinload(Meal.items))
        .where(Meal.user_id == user.id)
        .order_by(Meal.datetime.desc())
        .limit(50)
    ).all()
    return templates.TemplateResponse(request, "meals/list.html", {"meals": meals})


@router.get("/nuovo")
def nuovo(request: Request, giorno: str | None = None, user: User = Depends(current_user)):
    now = datetime.now().replace(second=0, microsecond=0)
    if giorno:
        # Coming from the balance page of another day: keep that day, current time.
        try:
            now = datetime.combine(date.fromisoformat(giorno), now.time())
        except ValueError:
            pass
    ctx = _form_context(None, [], [], "pranzo", now)
    return templates.TemplateResponse(request, "meals/form.html", ctx)


@router.get("/riga")
def riga(
    request: Request,
    food_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """One new item row for the form (HTMX, appended to #righe)."""
    food = db.scalar(visible_foods(user).where(Food.id == food_id))
    if food is None:
        raise HTTPException(404)
    return templates.TemplateResponse(
        request, "partials/item_row.html", {"food": food, "grams": 100}
    )


@router.post("/totali")
def totali(
    request: Request,
    food_id: Annotated[list[int], Form()] = [],
    grams: Annotated[list[float], Form()] = [],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Running totals for the form's current rows (HTMX, swapped into #totali)."""
    items, _ = _parse_items(db, user, food_id, grams)
    return templates.TemplateResponse(
        request, "partials/totals.html", {"totals": meal_totals(items)}
    )


def _save(
    db: Session,
    user: User,
    meal: Meal | None,
    when: datetime,
    meal_type: str,
    items: list[tuple[Food, float]],
) -> Meal:
    if meal is None:
        meal = Meal(user_id=user.id, input_method="manual")
        db.add(meal)
    meal.datetime = when
    meal.meal_type = meal_type
    meal.items.clear()
    for food, g in items:
        v = item_values(food, g)
        meal.items.append(
            MealItem(
                food=food,
                grams=g,
                kcal=v.kcal,
                protein_g=v.protein_g,
                carbs_g=v.carbs_g,
                fat_g=v.fat_g,
            )
        )
    db.commit()
    return meal


def _handle_form(request, db, user, meal, when_s, meal_type, food_id, grams):
    errors: list[str] = []
    try:
        when = datetime.fromisoformat(when_s)
    except ValueError:
        when = datetime.now().replace(second=0, microsecond=0)
        errors.append("Data e ora non valide.")
    if meal_type not in MEAL_TYPES:
        errors.append("Tipo di pasto non valido.")
    items, item_errors = _parse_items(db, user, food_id, grams)
    errors += item_errors
    if errors:
        ctx = _form_context(meal, items, errors, meal_type, when)
        return templates.TemplateResponse(
            request, "meals/form.html", ctx, status_code=422
        )
    saved = _save(db, user, meal, when, meal_type, items)
    return RedirectResponse(f"/pasti/{saved.id}", status_code=303)


@router.post("")
def crea(
    request: Request,
    when: Annotated[str, Form()],
    meal_type: Annotated[str, Form()],
    food_id: Annotated[list[int], Form()] = [],
    grams: Annotated[list[float], Form()] = [],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return _handle_form(request, db, user, None, when, meal_type, food_id, grams)


@router.get("/{meal_id}")
def vedi(
    request: Request,
    meal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = _own_meal(db, user, meal_id)
    totals = meal_totals([(i.food, i.grams) for i in meal.items])
    return templates.TemplateResponse(
        request, "meals/view.html", {"meal": meal, "totals": totals}
    )


@router.get("/{meal_id}/modifica")
def modifica(
    request: Request,
    meal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = _own_meal(db, user, meal_id)
    items = [(i.food, i.grams) for i in meal.items]
    ctx = _form_context(meal, items, [], meal.meal_type, meal.datetime)
    return templates.TemplateResponse(request, "meals/form.html", ctx)


@router.post("/{meal_id}")
def aggiorna(
    request: Request,
    meal_id: int,
    when: Annotated[str, Form()],
    meal_type: Annotated[str, Form()],
    food_id: Annotated[list[int], Form()] = [],
    grams: Annotated[list[float], Form()] = [],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = _own_meal(db, user, meal_id)
    return _handle_form(request, db, user, meal, when, meal_type, food_id, grams)


@router.post("/{meal_id}/elimina")
def elimina(
    meal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = _own_meal(db, user, meal_id)
    db.delete(meal)
    db.commit()
    return RedirectResponse("/pasti", status_code=303)
