"""Presets: recurring meals saved with their quantities."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.nutrition import meal_totals
from app.db import get_db
from app.deps import current_user, templates
from app.models import Food, MealPreset, MealPresetItem, User
from app.routers.foods import visible_foods

router = APIRouter(prefix="/preset")


def user_presets(db: Session, user: User) -> list[MealPreset]:
    return db.scalars(
        select(MealPreset)
        .options(selectinload(MealPreset.items).selectinload(MealPresetItem.food))
        .where(MealPreset.user_id == user.id)
        .order_by(MealPreset.name)
    ).all()


def _own(db: Session, user: User, preset_id: int) -> MealPreset:
    preset = db.scalar(
        select(MealPreset)
        .options(selectinload(MealPreset.items).selectinload(MealPresetItem.food))
        .where(MealPreset.id == preset_id, MealPreset.user_id == user.id)
    )
    if preset is None:
        raise HTTPException(404)
    return preset


def _parse_items(db, user, food_ids, grams):
    errors = []
    if len(food_ids) != len(grams):
        return [], ["Dati del modulo non validi."]
    foods = {f.id: f for f in db.scalars(visible_foods(user).where(Food.id.in_(food_ids)))}
    items = []
    for food_id, g in zip(food_ids, grams):
        food = foods.get(food_id)
        if food is None:
            errors.append("Alimento non trovato.")
        elif g <= 0:
            errors.append(f"Grammi non validi per {food.label}.")
        else:
            items.append((food, g))
    if not items and not errors:
        errors.append("Aggiungi almeno un alimento.")
    return items, errors


def _form(request, preset, name, items, errors, status=200):
    return templates.TemplateResponse(
        request,
        "presets/form.html",
        {"preset": preset, "name": name, "items": items, "totals": meal_totals(items), "errors": errors},
        status_code=status,
    )


@router.get("")
def elenco(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    presets = user_presets(db, user)
    rows = [(p, meal_totals([(i.food, i.grams) for i in p.items])) for p in presets]
    return templates.TemplateResponse(request, "presets/list.html", {"rows": rows})


@router.get("/nuovo")
def nuovo(request: Request, user: User = Depends(current_user)):
    return _form(request, None, "", [], [])


def _handle(request, db, user, preset, name, food_id, grams):
    errors = []
    name = name.strip()
    if not name:
        errors.append("Dai un nome al preset.")
    items, item_errors = _parse_items(db, user, food_id, grams)
    errors += item_errors
    if errors:
        return _form(request, preset, name, items, errors, 422)
    if preset is None:
        preset = MealPreset(user_id=user.id)
        db.add(preset)
    preset.name = name[:120]
    preset.items.clear()
    for food, g in items:
        preset.items.append(MealPresetItem(food=food, grams=g))
    db.commit()
    return RedirectResponse("/preset", status_code=303)


@router.post("")
def crea(
    request: Request,
    name: Annotated[str, Form()],
    food_id: Annotated[list[int], Form()] = [],
    grams: Annotated[list[float], Form()] = [],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return _handle(request, db, user, None, name, food_id, grams)


@router.get("/{preset_id}/modifica")
def modifica(request: Request, preset_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    preset = _own(db, user, preset_id)
    return _form(request, preset, preset.name, [(i.food, i.grams) for i in preset.items], [])


@router.post("/{preset_id}")
def aggiorna(
    request: Request,
    preset_id: int,
    name: Annotated[str, Form()],
    food_id: Annotated[list[int], Form()] = [],
    grams: Annotated[list[float], Form()] = [],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    preset = _own(db, user, preset_id)
    return _handle(request, db, user, preset, name, food_id, grams)


@router.post("/{preset_id}/elimina")
def elimina(preset_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    preset = _own(db, user, preset_id)
    db.delete(preset)
    db.commit()
    return RedirectResponse("/preset", status_code=303)
